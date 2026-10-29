"""
GitHub Actions tools, including the full CI/CD pipeline suite.

Tools return the same plain-text status style as the rest of github-mcp.
Mutating pipeline operations stay confirmation-gated via confirm=true.
"""

import base64
from typing import Annotated, Literal
from urllib.parse import quote

from pydantic import Field

from actions_ci import extract_failure_excerpt, redact_variable_value, render_ci_pipeline

_SESSION = (
    "Named GitHub session created by github_connect. Defaults to 'default'. "
    "If that session is not in memory, the client reconnects it from the credential "
    "cache or GITHUB_TOKEN. This tool does not accept a token argument."
)
_OWNER = "Repository owner (user or organization login), without the repository name."
_REPO = "Repository name, without the owner."


def register_actions_tools(mcp, github) -> None:
    """Register Actions workflow tools on the shared FastMCP instance."""

    def _paged(path: str, key: str, session_name: str):
        items: list = []
        for page in range(1, 11):
            data, error = github.get(
                path,
                session_name=session_name,
                params={"per_page": 100, "page": page},
            )
            if error:
                return items, error
            if isinstance(data, list):
                batch = data
            elif isinstance(data, dict):
                batch = list(data.get(key) or [])
            else:
                return items, f"❌ Unexpected response from {path}"
            items.extend(batch)
            if len(batch) < 100:
                break
        return items, None

    def _size(num: object) -> str:
        try:
            size = int(num or 0)
        except (TypeError, ValueError):
            return str(num)
        if size < 1024:
            return f"{size} bytes"
        if size < 1024 * 1024:
            return f"{size} bytes ({size / 1024:.1f} KiB)"
        return f"{size} bytes ({size / 1024 / 1024:.1f} MiB)"

    def _checklist(draft) -> str:
        lines = ["Required secret names (existence only — values are never read):"]
        if draft.secrets:
            lines.extend(f"  • {name}" for name in draft.secrets)
        else:
            lines.append("  • (none beyond the automatic GITHUB_TOKEN)")
        lines.append("Required Actions variable names:")
        if draft.variables:
            lines.extend(f"  • {name}" for name in draft.variables)
        else:
            lines.append("  • (none)")
        lines.append("Check them with github_check_ci_secrets_and_variables before dispatch.")
        return "\n".join(lines)

    @mcp.tool()
    def github_list_workflows(
        owner: Annotated[str, Field(description=_OWNER)],
        repo: Annotated[str, Field(description=_REPO)],
        session_name: Annotated[str, Field(description=_SESSION)] = "default",
    ) -> str:
        """
        List GitHub Actions workflows in a repository.

        Purpose & When to Use:
            Use this to discover workflow ids and filenames before
            github_trigger_workflow. Use github_generate_action_pipeline when the
            repository does not have a pipeline yet. Use github_get_tree only when
            you need the whole file tree, not just Actions.

        Side Effects & Auth:
            Read-only. Does not change the repository or start a run.
            Requires session_name (default 'default'), which selects the cached
            PAT. Classic scopes: repo. Fine-grained: Actions read.

        Parameter Constraints:
            owner and repo form the GitHub slug. session_name is a session label,
            not a token.
        """
        data, error = github.get(
            f"/repos/{owner}/{repo}/actions/workflows",
            session_name=session_name,
        )
        if error:
            return error

        workflows = data.get("workflows", [])
        if not workflows:
            return f"⚡ No workflows found in '{owner}/{repo}'."

        lines = [f"⚡ Workflows in '{owner}/{repo}' ({len(workflows)}):\n"]
        for wf in workflows:
            state = wf.get("state", "unknown")
            icon = "🟢" if state == "active" else "⛔"
            lines.append(
                f"  {icon} {wf.get('name', '?')}  (ID: {wf.get('id', '?')})\n"
                f"     File: {wf.get('path', '?')} | State: {state}"
            )
        return "\n".join(lines)

    @mcp.tool()
    def github_trigger_workflow(
        owner: Annotated[str, Field(description=_OWNER)],
        repo: Annotated[str, Field(description=_REPO)],
        workflow_id: Annotated[str, Field(description="Workflow id or file name, for example 'ci-cd.yml' or '123456'.")],
        ref: Annotated[str, Field(description="Branch, tag, or full ref to run on. Defaults to main.")] = "main",
        inputs: Annotated[str, Field(description="workflow_dispatch inputs as a JSON object string. Empty means no inputs.")] = "",
        session_name: Annotated[str, Field(description=_SESSION)] = "default",
    ) -> str:
        """
        Dispatch a workflow that already defines workflow_dispatch.

        Purpose & When to Use:
            Use this after a pipeline exists and preflight secrets have been
            checked. Use github_generate_action_pipeline to create the workflow
            file first. Use github_list_workflow_runs to watch the run afterwards.
            This is not a confirmation-gated tool; ask the operator before
            dispatching against a production ref.

        Side Effects & Auth:
            Mutating. Starts a workflow run. Not confirmation-gated in the schema.
            Requires session_name. Classic scopes: repo and workflow.
            Fine-grained: Actions write.

        Parameter Constraints:
            inputs must be a JSON object string or empty. ref defaults to main.
            workflow_id is either a numeric id or a workflow filename.
        """
        import json

        payload: dict = {"ref": ref}
        if inputs:
            try:
                payload["inputs"] = json.loads(inputs)
            except json.JSONDecodeError:
                return f"❌ Invalid JSON inputs: {inputs}"

        _, error = github.post(
            f"/repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches",
            json_data=payload,
            session_name=session_name,
        )
        if error:
            return error
        extra = f"\n  Inputs: {inputs}" if inputs else ""
        return f"✅ Workflow '{workflow_id}' triggered on ref '{ref}'.{extra}"

    @mcp.tool()
    def github_list_workflow_runs(
        owner: Annotated[str, Field(description=_OWNER)],
        repo: Annotated[str, Field(description=_REPO)],
        workflow_id: Annotated[str, Field(description="Workflow id or filename. Empty lists runs for every workflow.")] = "",
        status: Annotated[str, Field(description="Filter: completed, in_progress, queued, success, failure, or empty for all.")] = "",
        branch: Annotated[str, Field(description="Branch name filter. Empty does not filter by branch.")] = "",
        max_results: Annotated[int, Field(description="Maximum runs to return. Clamped to 1..100. Default 20.")] = 20,
        session_name: Annotated[str, Field(description=_SESSION)] = "default",
    ) -> str:
        """
        List recent workflow runs, including the run id needed by later tools.

        Purpose & When to Use:
            Use this to find a run_id before github_get_workflow_run,
            github_get_failed_job_logs, github_get_run_artifacts_metadata, or
            github_get_pending_deployments. Use github_get_workflow_run when you
            already know the id.

        Side Effects & Auth:
            Read-only. Requires session_name. Classic scope: repo.
            Fine-grained: Actions read.

        Parameter Constraints:
            max_results is capped at 100. status and branch are optional filters.
            workflow_id empty means every workflow in the repository.
        """
        limit = max(1, min(int(max_results), 100))
        params: dict = {"per_page": limit}
        if status:
            params["status"] = status
        if branch:
            params["branch"] = branch
        path = (
            f"/repos/{owner}/{repo}/actions/workflows/{workflow_id}/runs"
            if workflow_id
            else f"/repos/{owner}/{repo}/actions/runs"
        )
        data, error = github.get(path, params=params, session_name=session_name)
        if error:
            return error

        runs = data.get("workflow_runs", [])[:limit]
        if not runs:
            return "⚡ No workflow runs found."

        icon_map = {
            "success": "🟢",
            "failure": "🔴",
            "cancelled": "⚫",
            "in_progress": "🔵",
            "queued": "⏳",
            "skipped": "⬜",
        }
        lines = [f"⚡ Workflow Runs ({len(runs)}):\n"]
        for run in runs:
            conclusion = run.get("conclusion") or run.get("status") or "unknown"
            icon = icon_map.get(conclusion, "❓")
            created = (run.get("created_at") or "")[:10]
            lines.append(
                f"  {icon} run_id={run.get('id', '?')} #{run.get('run_number', '?')}: "
                f"{run.get('name', '?')} — {conclusion}\n"
                f"     Branch: {run.get('head_branch', '?')} | {created}"
            )
        return "\n".join(lines)

    @mcp.tool()
    def github_get_workflow_run(
        owner: Annotated[str, Field(description=_OWNER)],
        repo: Annotated[str, Field(description=_REPO)],
        run_id: Annotated[int, Field(description="Numeric workflow run id from github_list_workflow_runs.")],
        session_name: Annotated[str, Field(description=_SESSION)] = "default",
    ) -> str:
        """
        Get status, conclusion, branch, event, and URL for one workflow run.

        Purpose & When to Use:
            Use this to monitor a run after github_trigger_workflow. If conclusion
            is failure, switch to github_get_failed_job_logs instead of downloading
            the full log archive. If the run is waiting on an environment, use
            github_get_pending_deployments.

        Side Effects & Auth:
            Read-only. Requires session_name. Classic scope: repo.
            Fine-grained: Actions read.

        Parameter Constraints:
            run_id is the numeric Actions run id, not the display run number.
        """
        data, error = github.get(
            f"/repos/{owner}/{repo}/actions/runs/{run_id}",
            session_name=session_name,
        )
        if error:
            return error

        conclusion = data.get("conclusion") or data.get("status") or "unknown"
        icon_map = {"success": "🟢", "failure": "🔴", "cancelled": "⚫", "in_progress": "🔵"}
        icon = icon_map.get(conclusion, "❓")
        lines = [
            f"{icon} Workflow Run #{data.get('run_number', '?')}: {data.get('name', '?')}\n",
            f"  • Run ID: {data.get('id', run_id)}",
            f"  • Status: {data.get('status', '?')}",
            f"  • Conclusion: {conclusion}",
            f"  • Branch: {data.get('head_branch', '?')}",
            f"  • SHA: {(data.get('head_sha') or '')[:12]}",
            f"  • Event: {data.get('event', '?')}",
            f"  • Created: {(data.get('created_at') or '')[:19]}",
            f"  • Updated: {(data.get('updated_at') or '')[:19]}",
            f"  • URL: {data.get('html_url', 'N/A')}",
        ]
        actor = data.get("actor") or {}
        if actor:
            lines.append(f"  • Triggered by: @{actor.get('login', '?')}")
        return "\n".join(lines)

    @mcp.tool()
    def github_get_run_logs(
        owner: Annotated[str, Field(description=_OWNER)],
        repo: Annotated[str, Field(description=_REPO)],
        run_id: Annotated[int, Field(description="Numeric workflow run id.")],
        session_name: Annotated[str, Field(description=_SESSION)] = "default",
    ) -> str:
        """
        Locate the log archive for a workflow run without pasting the full log.

        Purpose & When to Use:
            Use github_get_failed_job_logs when a run failed and you need the
            failing step plus a short stack excerpt. Use this tool only when you
            need the archive location for a human, not when an agent should read
            the log. The full zip is not returned.

        Side Effects & Auth:
            Read-only. Requires session_name. Classic scope: repo.
            Fine-grained: Actions read.

        Parameter Constraints:
            run_id is the numeric Actions run id.
        """
        data, error = github.get(
            f"/repos/{owner}/{repo}/actions/runs/{run_id}/logs",
            session_name=session_name,
            raw=True,
        )
        if error or not data or str(data).startswith("PK"):
            return (
                f"📜 Logs for run_id={run_id} are an archive, not an inline excerpt.\n"
                f"  https://github.com/{owner}/{repo}/actions/runs/{run_id}\n\n"
                "Use github_get_failed_job_logs for the failing step name and a short error excerpt."
            )
        text = str(data)
        if len(text) > 1500:
            text = text[:1500] + "\n… [truncated — use github_get_failed_job_logs for a focused excerpt]"
        return f"📜 Logs for run_id={run_id}:\n\n{text}"

    @mcp.tool()
    def github_cancel_workflow_run(
        owner: Annotated[str, Field(description=_OWNER)],
        repo: Annotated[str, Field(description=_REPO)],
        run_id: Annotated[int, Field(description="Numeric id of the in-progress workflow run to cancel.")],
        session_name: Annotated[str, Field(description=_SESSION)] = "default",
    ) -> str:
        """
        Cancel an in-progress workflow run.

        Purpose & When to Use:
            Use this to stop a run that is still queued or in progress.
            Use github_rerun_failed_jobs after a completed failure. Ask the
            operator before cancelling a production deployment run.

        Side Effects & Auth:
            Mutating. Cancels the run. Not confirmation-gated in the schema.
            Requires session_name. Classic scopes: repo and workflow.
            Fine-grained: Actions write.

        Parameter Constraints:
            run_id must refer to a run that GitHub still allows to be cancelled.
        """
        _, error = github.post(
            f"/repos/{owner}/{repo}/actions/runs/{run_id}/cancel",
            session_name=session_name,
        )
        if error:
            return error
        return f"✅ Workflow run #{run_id} cancelled."

    @mcp.tool()
    def github_rerun_workflow(
        owner: Annotated[str, Field(description=_OWNER)],
        repo: Annotated[str, Field(description=_REPO)],
        run_id: Annotated[int, Field(description="Numeric id of the workflow run to rerun from the start.")],
        session_name: Annotated[str, Field(description=_SESSION)] = "default",
    ) -> str:
        """
        Rerun every job in a workflow run.

        Purpose & When to Use:
            Use github_rerun_failed_jobs when only failed jobs should run again.
            Use this tool when the whole run, including previously successful jobs,
            must start over. Ask the operator before rerunning a production run.

        Side Effects & Auth:
            Mutating. Restarts all jobs. Not confirmation-gated in the schema.
            Requires session_name. Classic scopes: repo and workflow.
            Fine-grained: Actions write.

        Parameter Constraints:
            run_id is the numeric Actions run id. This endpoint reruns all jobs,
            not only failures.
        """
        _, error = github.post(
            f"/repos/{owner}/{repo}/actions/runs/{run_id}/rerun",
            session_name=session_name,
        )
        if error:
            return error
        return (
            f"✅ Workflow run #{run_id} re-triggered (all jobs).\n"
            "Use github_rerun_failed_jobs with confirm=true to rerun only failed jobs."
        )

    @mcp.tool()
    def github_generate_action_pipeline(
        owner: Annotated[str, Field(description=_OWNER)],
        repo: Annotated[str, Field(description=_REPO)],
        language: Annotated[
            Literal["python", "node", "java", "go", "dotnet", "generic"],
            Field(description="Source language used to choose setup and test steps."),
        ],
        build_tool: Annotated[
            str,
            Field(
                description=(
                    "Build tool paired with language. python: pip, poetry, uv. "
                    "node: npm, yarn, pnpm. java: maven, gradle. go: go. "
                    "dotnet: dotnet. generic: make. Empty selects the language default."
                )
            ),
        ] = "",
        artifact_target: Annotated[
            Literal["github_packages", "nexus", "artifactory", "ecr_acr_gar"],
            Field(description="Registry that receives the built package or image."),
        ] = "github_packages",
        deploy_target: Annotated[
            Literal["openshift", "eks", "aks", "gke", "none"],
            Field(description="Cluster family for the deploy job. 'none' publishes only."),
        ] = "none",
        name: Annotated[
            str,
            Field(description="Workflow file stem. Written as .github/workflows/<name>.yml. Default ci-cd."),
        ] = "ci-cd",
        environment: Annotated[
            str,
            Field(description="GitHub environment gate used on push. Letters, numbers, '_' or '-'. Default production."),
        ] = "production",
        registry_cloud: Annotated[
            Literal["ecr", "acr", "gar"],
            Field(description="Cloud registry used only when artifact_target is ecr_acr_gar. Default ecr."),
        ] = "ecr",
        branch: Annotated[str, Field(description="Branch that receives the workflow commit. Empty uses the default branch.")] = "",
        commit: Annotated[bool, Field(description="When true, commit the workflow file. When false, return a preview only.")] = False,
        confirm: Annotated[bool, Field(description="Must be true together with commit=true. Defaults to false so the file is not written.")] = False,
        message: Annotated[str, Field(description="Commit message used when commit=true. Empty uses a generated message.")] = "",
        session_name: Annotated[str, Field(description=_SESSION)] = "default",
    ) -> str:
        """
        Generate a .github/workflows pipeline and optionally commit it.

        Purpose & When to Use:
            Use this for zero-to-CI authoring after github_list_languages and
            github_check_ci_secrets_and_variables. The file targets GitHub
            Packages, Nexus, Artifactory, or ECR/ACR/GAR, and can deploy to
            OpenShift, EKS, AKS, or GKE. Use github_trigger_workflow only after
            the file exists on the branch. Do not use this to edit application code.

        Side Effects & Auth:
            Read-only while commit is false.
            Mutating and confirmation-gated when commit=true: confirm must also
            be true, and the tool then creates or updates the workflow file.
            Requires session_name. Classic scopes: repo (contents write to commit)
            and workflow. Fine-grained: Contents write and Actions read.
            Secret values are never embedded; the YAML references ${{ secrets.* }}.

        Parameter Constraints:
            language, artifact_target, deploy_target, and registry_cloud are enums.
            build_tool must match the language. name is a single file stem.
            environment is a GitHub environment name. confirm defaults to false.
        """
        try:
            draft = render_ci_pipeline(
                language=language,
                build_tool=build_tool,
                artifact_target=artifact_target,
                deploy_target=deploy_target,
                name=name,
                environment=environment,
                registry_cloud=registry_cloud,
            )
        except ValueError as exc:
            return f"❌ {exc}"

        image = draft.image_ref or "(language package or Actions artifact — no container image)"
        header = (
            f"🧩 Pipeline for {owner}/{repo}\n"
            f"  • File: {draft.path}\n"
            f"  • Image ref: {image}\n"
            f"  • Mode: {'container publish' if draft.container_mode else 'package publish'}\n\n"
            f"{_checklist(draft)}\n\n"
            f"----- {draft.path} -----\n{draft.yaml_text}"
        )
        if not commit:
            return header + "\nRead-only preview. Pass commit=true and confirm=true to commit this file."
        if not confirm:
            return (
                header
                + "\n⚠️ Confirmation required. Re-call with commit=true and confirm=true to write the file."
            )

        commit_message = message.strip() or f"ci: add {draft.filename} pipeline"
        params = {"ref": branch} if branch else None
        existing, error = github.get(
            f"/repos/{owner}/{repo}/contents/{draft.path}",
            session_name=session_name,
            params=params,
        )
        encoded = base64.b64encode(draft.yaml_text.encode("utf-8")).decode("utf-8")
        payload: dict = {"message": commit_message, "content": encoded}
        if branch:
            payload["branch"] = branch

        if error and "404" not in error:
            return error
        if not error and isinstance(existing, dict):
            current = existing.get("content") or ""
            try:
                decoded = base64.b64decode("".join(current.split())).decode("utf-8")
            except Exception:
                decoded = ""
            if decoded.replace("\r\n", "\n") == draft.yaml_text.replace("\r\n", "\n"):
                return f"✅ {draft.path} is already up to date on {owner}/{repo}. No commit created.\n\n{_checklist(draft)}"
            payload["sha"] = existing.get("sha")

        data, put_error = github.put(
            f"/repos/{owner}/{repo}/contents/{draft.path}",
            json_data=payload,
            session_name=session_name,
        )
        if put_error:
            return put_error
        commit_info = (data or {}).get("commit") or {}
        sha = (commit_info.get("sha") or "")[:7]
        return (
            f"✅ Committed {draft.path} to {owner}/{repo}.\n"
            f"  • Commit: {sha or '?'}\n"
            f"  • Message: {commit_message}\n"
            f"  • Branch: {branch or 'default'}\n\n"
            f"{_checklist(draft)}"
        )

    @mcp.tool()
    def github_get_failed_job_logs(
        owner: Annotated[str, Field(description=_OWNER)],
        repo: Annotated[str, Field(description=_REPO)],
        run_id: Annotated[int, Field(description="Numeric workflow run id whose failed jobs should be inspected.")],
        max_lines: Annotated[int, Field(description="Maximum excerpt lines per failed job. Clamped to 1..80. Default 40.")] = 40,
        session_name: Annotated[str, Field(description=_SESSION)] = "default",
    ) -> str:
        """
        Return the failing step name and a short error excerpt for a run.

        Purpose & When to Use:
            Use this after github_get_workflow_run reports conclusion=failure.
            It lists jobs, keeps steps whose conclusion is failure, downloads that
            job's plain-text log, and returns only the relevant lines. Use
            github_get_run_logs if you only need the archive link. Use
            github_get_file or github_search_code afterwards to open the cited path.

        Side Effects & Auth:
            Read-only. Requires session_name. Classic scope: repo.
            Fine-grained: Actions read. The full log is not returned.

        Parameter Constraints:
            run_id is the numeric Actions run id. max_lines is clamped to 1..80.
        """
        jobs, error = _paged(
            f"/repos/{owner}/{repo}/actions/runs/{run_id}/jobs",
            "jobs",
            session_name,
        )
        if error and not jobs:
            return error

        failed = []
        for job in jobs:
            steps = job.get("steps") or []
            bad_steps = [step for step in steps if step.get("conclusion") == "failure"]
            if job.get("conclusion") == "failure" or bad_steps:
                failed.append((job, bad_steps))

        if not failed:
            suffix = f"\n{error}" if error else ""
            return f"✅ No failed jobs or steps found for run_id={run_id}.{suffix}"

        limit = max(1, min(int(max_lines), 80))
        lines = [f"🔴 Failed jobs for run_id={run_id} in {owner}/{repo} ({len(failed)}):\n"]
        for job, bad_steps in failed[:5]:
            job_id = job.get("id")
            lines.append(
                f"Job: {job.get('name', '?')} (job_id={job_id}) — conclusion={job.get('conclusion')}"
            )
            if bad_steps:
                lines.append("Failing steps:")
                for step in bad_steps:
                    lines.append(f"  • {step.get('name', '?')} (step {step.get('number', '?')})")
            else:
                lines.append("Failing steps: job failed before a step was marked failure.")
            log_text, log_error = github.get(
                f"/repos/{owner}/{repo}/actions/jobs/{job_id}/logs",
                session_name=session_name,
                raw=True,
            )
            if log_error or not log_text:
                lines.append(f"Log excerpt unavailable: {log_error or 'empty log'}")
            else:
                excerpt = extract_failure_excerpt(
                    str(log_text),
                    [step.get("name", "") for step in bad_steps],
                    limit,
                )
                lines.append("Relevant log lines:")
                lines.extend(f"  {row}" for row in excerpt)
            if job.get("html_url"):
                lines.append(f"Job URL: {job.get('html_url')}")
            lines.append("")
        if len(failed) > 5:
            lines.append(f"… {len(failed) - 5} additional failed job(s) omitted.")
        return "\n".join(lines).rstrip()

    @mcp.tool()
    def github_rerun_failed_jobs(
        owner: Annotated[str, Field(description=_OWNER)],
        repo: Annotated[str, Field(description=_REPO)],
        run_id: Annotated[int, Field(description="Numeric workflow run id whose failed jobs should be rerun.")],
        confirm: Annotated[bool, Field(description="Must be true to call the rerun-failed-jobs API. Defaults to false.")] = False,
        session_name: Annotated[str, Field(description=_SESSION)] = "default",
    ) -> str:
        """
        Rerun only the failed jobs in a workflow run.

        Purpose & When to Use:
            Use this after github_get_failed_job_logs and a code or workflow fix
            has been pushed. Use github_rerun_workflow when every job must start
            over, including jobs that already succeeded.

        Side Effects & Auth:
            Mutating and confirmation-gated. The POST to
            /actions/runs/{run_id}/rerun-failed-jobs runs only when confirm=true.
            Requires session_name. Classic scopes: repo and workflow.
            Fine-grained: Actions write.

        Parameter Constraints:
            confirm defaults to false. run_id is the numeric Actions run id.
        """
        if not confirm:
            return (
                "⚠️ Confirmation required before rerunning failed jobs.\n"
                f"  • Repository: {owner}/{repo}\n"
                f"  • run_id: {run_id}\n"
                "Re-call github_rerun_failed_jobs with confirm=true to continue."
            )
        _, error = github.post(
            f"/repos/{owner}/{repo}/actions/runs/{run_id}/rerun-failed-jobs",
            session_name=session_name,
        )
        if error:
            return error
        return f"✅ Failed jobs for run_id={run_id} were re-queued."

    @mcp.tool()
    def github_get_run_artifacts_metadata(
        owner: Annotated[str, Field(description=_OWNER)],
        repo: Annotated[str, Field(description=_REPO)],
        run_id: Annotated[int, Field(description="Numeric workflow run id whose artifacts should be listed.")],
        session_name: Annotated[str, Field(description=_SESSION)] = "default",
    ) -> str:
        """
        List artifact id, size, digest, expiration, and download URL for a run.

        Purpose & When to Use:
            Use this after a successful build to prove an artifact was uploaded
            before handing the digest or git SHA to artifact-registry-mcp or
            k8s-mcp. Use github_get_workflow_run for status, not files.
            This tool does not download artifact bytes.

        Side Effects & Auth:
            Read-only. Requires session_name. Classic scope: repo.
            Fine-grained: Actions read. Download URLs still require the caller's
            token; pass the digest and name downstream, not the token.

        Parameter Constraints:
            run_id is the numeric Actions run id. Expired artifacts are listed
            with their expired flag so callers can ignore them.
        """
        artifacts, error = _paged(
            f"/repos/{owner}/{repo}/actions/runs/{run_id}/artifacts",
            "artifacts",
            session_name,
        )
        if error and not artifacts:
            return error
        if not artifacts:
            return f"📦 No artifacts for run_id={run_id}."

        lines = [f"📦 Artifacts for run_id={run_id} ({len(artifacts)}):\n"]
        for item in artifacts:
            digest = item.get("digest") or "(not provided by this API response)"
            lines.append(
                f"  • {item.get('name', '?')}\n"
                f"    ID: {item.get('id', '?')}\n"
                f"    Size: {_size(item.get('size_in_bytes'))}\n"
                f"    SHA256: {digest}\n"
                f"    Expires: {item.get('expires_at') or '?'}\n"
                f"    Expired: {item.get('expired', False)}\n"
                f"    Download URL: {item.get('archive_download_url') or 'n/a'}"
            )
        lines.append(
            "\nHand the artifact name, SHA256, and git SHA to artifact-registry-mcp or k8s-mcp. Do not forward the token."
        )
        return "\n".join(lines)

    @mcp.tool()
    def github_get_pending_deployments(
        owner: Annotated[str, Field(description=_OWNER)],
        repo: Annotated[str, Field(description=_REPO)],
        run_id: Annotated[int, Field(description="Numeric workflow run id to inspect for environment gates.")],
        session_name: Annotated[str, Field(description=_SESSION)] = "default",
    ) -> str:
        """
        List environment deployment gates waiting for review on a run.

        Purpose & When to Use:
            Use this when a run is waiting on staging or production. Approve or
            reject with github_review_Pending_deployment after a person confirms.
            Use github_get_workflow_run first if you do not yet know the run is waiting.

        Side Effects & Auth:
            Read-only. Requires session_name. Classic scope: repo.
            Fine-grained: Actions read.

        Parameter Constraints:
            run_id is the numeric Actions run id. An empty list means no gate is waiting.
        """
        data, error = github.get(
            f"/repos/{owner}/{repo}/actions/runs/{run_id}/pending_deployments",
            session_name=session_name,
        )
        if error:
            return error
        pending = data if isinstance(data, list) else (data or {}).get("pending_deployments") or []
        if not pending:
            return f"✅ No pending environment deployments for run_id={run_id}."

        lines = [f"🚧 Pending deployments for run_id={run_id} ({len(pending)}):\n"]
        for item in pending:
            env = item.get("environment") or {}
            reviewers = item.get("reviewers") or []
            names = []
            for reviewer in reviewers:
                who = reviewer.get("reviewer") or reviewer
                login = who.get("login") or who.get("name") or who.get("slug")
                if login:
                    names.append(f"@{login}")
            lines.append(
                f"  • {env.get('name', '?')} (environment_id={env.get('id', '?')})\n"
                f"    Wait timer (minutes): {item.get('wait_timer', 0)}\n"
                f"    Current user can approve: {item.get('current_user_can_approve', False)}\n"
                f"    Reviewers: {', '.join(names) if names else '(none listed)'}"
            )
        lines.append(
            "\nAsk the operator, then call github_review_Pending_deployment with confirm=true."
        )
        return "\n".join(lines)

    @mcp.tool()
    def github_review_Pending_deployment(
        owner: Annotated[str, Field(description=_OWNER)],
        repo: Annotated[str, Field(description=_REPO)],
        run_id: Annotated[int, Field(description="Numeric workflow run id that has a pending environment gate.")],
        state: Annotated[
            Literal["approved", "rejected"],
            Field(description="Review decision sent to GitHub. approved continues the deploy; rejected stops it."),
        ],
        environment_name: Annotated[
            str,
            Field(description="Environment name to review, such as staging or production. Empty if environment_ids is set."),
        ] = "",
        environment_ids: Annotated[
            str,
            Field(description="Comma-separated GitHub environment ids. Empty resolves environment_name, or the only pending gate."),
        ] = "",
        comment: Annotated[str, Field(description="Review comment stored on the deployment. Empty uses a short default comment.")] = "",
        confirm: Annotated[bool, Field(description="Must be true to approve or reject the gate. Defaults to false.")] = False,
        session_name: Annotated[str, Field(description=_SESSION)] = "default",
    ) -> str:
        """
        Approve or reject a pending Actions environment deployment.

        Purpose & When to Use:
            Use this after github_get_pending_deployments and after a person has
            confirmed the promotion. This is the gate between a built artifact and
            the staging or production environment. After approval, hand the image
            tag and SHA to k8s-mcp or artifact-registry-mcp and check traces with
            observability-mcp. Do not use this to change cluster objects directly.

        Side Effects & Auth:
            Mutating and confirmation-gated. The review POST runs only when
            confirm=true. Requires session_name. Classic scopes: repo and workflow.
            Fine-grained: Actions write. The caller must be an environment reviewer.

        Parameter Constraints:
            state is approved or rejected. Provide environment_name or
            environment_ids. If neither is set and exactly one gate is pending,
            that gate is used. confirm defaults to false.
        """
        data, error = github.get(
            f"/repos/{owner}/{repo}/actions/runs/{run_id}/pending_deployments",
            session_name=session_name,
        )
        if error:
            return error
        pending = data if isinstance(data, list) else []
        ids: list[int] = []
        if environment_ids.strip():
            for part in environment_ids.split(","):
                part = part.strip()
                if not part.isdigit():
                    return f"❌ environment_ids must be comma-separated integers, got '{part}'."
                ids.append(int(part))
        elif environment_name.strip():
            wanted = environment_name.strip()
            for item in pending:
                env = item.get("environment") or {}
                if env.get("name") == wanted and env.get("id") is not None:
                    ids.append(int(env["id"]))
            if not ids:
                return f"❌ No pending deployment named '{wanted}' on run_id={run_id}."
        elif len(pending) == 1:
            env = pending[0].get("environment") or {}
            if env.get("id") is None:
                return "❌ The pending deployment did not include an environment id."
            ids.append(int(env["id"]))
        else:
            return "❌ Provide environment_name or environment_ids. More than one gate is pending."

        names = []
        for item in pending:
            env = item.get("environment") or {}
            if env.get("id") in ids:
                names.append(f"{env.get('name', '?')} ({env.get('id')})")
        target = ", ".join(names) if names else ", ".join(str(i) for i in ids)
        if not confirm:
            return (
                "⚠️ Confirmation required before reviewing a deployment gate.\n"
                f"  • Repository: {owner}/{repo}\n"
                f"  • run_id: {run_id}\n"
                f"  • Decision: {state}\n"
                f"  • Environments: {target}\n"
                "Re-call github_review_Pending_deployment with confirm=true to continue."
            )

        payload = {
            "environment_ids": ids,
            "state": state,
            "comment": comment.strip() or f"{state} via github-mcp",
        }
        _, post_error = github.post(
            f"/repos/{owner}/{repo}/actions/runs/{run_id}/pending_deployments",
            json_data=payload,
            session_name=session_name,
        )
        if post_error:
            return post_error
        verb = "Approved" if state == "approved" else "Rejected"
        return f"✅ {verb} deployment gate for run_id={run_id}: {target}."

    @mcp.tool()
    def github_check_ci_secrets_and_variables(
        owner: Annotated[str, Field(description=_OWNER)],
        repo: Annotated[str, Field(description=_REPO)],
        environment: Annotated[
            str,
            Field(description="Environment name to include. Empty lists repository scope plus every environment (capped)."),
        ] = "",
        session_name: Annotated[str, Field(description=_SESSION)] = "default",
    ) -> str:
        """
        List variable names and values, and secret names only, for CI preflight.

        Purpose & When to Use:
            Use this before github_generate_action_pipeline commits a workflow or
            before github_trigger_workflow. Compare the names with the checklist
            from the pipeline generator. Use github_list_workflows if you need
            files rather than settings. Secret values are never requested or shown.

        Side Effects & Auth:
            Read-only. Requires session_name. Classic scope: repo.
            Fine-grained: Actions variables read, and secrets metadata read.
            Variable values that look like tokens are redacted.

        Parameter Constraints:
            environment empty includes the repository and up to 20 environments.
            A named environment limits the environment section to that name.
            Secret output is existence only (name plus created/updated timestamps).
        """
        lines = [f"🔐 CI preflight for {owner}/{repo}\n"]

        variables, var_error = _paged(
            f"/repos/{owner}/{repo}/actions/variables",
            "variables",
            session_name,
        )
        secrets, secret_error = _paged(
            f"/repos/{owner}/{repo}/actions/secrets",
            "secrets",
            session_name,
        )
        lines.append("Repository variables:")
        if var_error and not variables:
            lines.append(f"  • {var_error}")
        elif not variables:
            lines.append("  • (none)")
        else:
            for item in variables:
                lines.append(f"  • {item.get('name', '?')} = {redact_variable_value(item.get('value'))}")

        lines.append("Repository secrets (names only):")
        if secret_error and not secrets:
            lines.append(f"  • {secret_error}")
        elif not secrets:
            lines.append("  • (none)")
        else:
            for item in secrets:
                created = (item.get("created_at") or "")[:10]
                lines.append(f"  • {item.get('name', '?')} — present (created {created or '?'})")

        env_names: list[str] = []
        if environment.strip():
            env_names = [environment.strip()]
        else:
            envs, env_error = _paged(
                f"/repos/{owner}/{repo}/environments",
                "environments",
                session_name,
            )
            if env_error and not envs:
                lines.append(f"\nEnvironments: {env_error}")
            else:
                env_names = [item.get("name", "") for item in envs if item.get("name")][:20]
                if len(envs) > 20:
                    lines.append("\nEnvironment list truncated to 20.")

        for env_name in env_names:
            safe = quote(env_name, safe="")
            lines.append(f"\nEnvironment {env_name}:")
            env_vars, env_var_error = _paged(
                f"/repos/{owner}/{repo}/environments/{safe}/variables",
                "variables",
                session_name,
            )
            env_secrets, env_secret_error = _paged(
                f"/repos/{owner}/{repo}/environments/{safe}/secrets",
                "secrets",
                session_name,
            )
            lines.append("  Variables:")
            if env_var_error and not env_vars:
                lines.append(f"    • {env_var_error}")
            elif not env_vars:
                lines.append("    • (none)")
            else:
                for item in env_vars:
                    lines.append(
                        f"    • {item.get('name', '?')} = {redact_variable_value(item.get('value'))}"
                    )
            lines.append("  Secrets (names only):")
            if env_secret_error and not env_secrets:
                lines.append(f"    • {env_secret_error}")
            elif not env_secrets:
                lines.append("    • (none)")
            else:
                for item in env_secrets:
                    lines.append(f"    • {item.get('name', '?')} — present")

        lines.append(
            "\nSecret values are not available through this tool. Create missing names in the GitHub UI before dispatch."
        )
        return "\n".join(lines)
