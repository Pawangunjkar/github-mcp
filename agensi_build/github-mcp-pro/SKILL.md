---
name: github-devops-actions-pro
version: 1.1.0
author: Pawan Gunjkar
description: Dual-mode GitHub Actions CI/CD orchestration for pipeline authoring, artifact verification, failure triage, and environment promotion.
---

# GitHub DevOps Actions Pro

Use `pawangunjkar-github-mcp` as the CI/CD control plane for the enterprise lifecycle suite. Sessions are selected with `session_name` (default `default`). The server reconnects that session from the credential cache or `GITHUB_TOKEN`. Tools do not take a token argument except `github_connect` and `github_save_credentials`.

Run `scripts/verify_env.py` before the first call. Classic PAT scopes for this playbook are `repo` and `workflow`.

Downstream hand-off names:

- Artifact bytes and digests go to `artifact-registry-mcp` (Nexus or Artifactory) or stay on GHCR / ECR / ACR / GAR when the workflow already pushed them.
- Cluster rollout details go to `k8s-mcp` (OpenShift, EKS, AKS, or GKE).
- Post-deploy verification goes to `observability-mcp` (Prometheus, Grafana, Tempo) using the git SHA and image tag.

## Workflow 1: Zero-to-CI Pipeline Authoring

1. Audit the stack with `github_get_repo`, `github_list_languages`, and `github_get_tree` on the build files (`pyproject.toml`, `pom.xml`, `package.json`, `go.mod`, `Dockerfile`).
2. Call `github_check_ci_secrets_and_variables` for the repository and the target environment (`staging` or `production`). Compare names with the checklist below. Secret output is existence only.
3. Call `github_generate_action_pipeline` with `commit=false` first.
   - `language`: `python`, `node`, `java`, `go`, `dotnet`, or `generic`
   - `build_tool`: the matching tool (`pip`, `poetry`, `uv`, `npm`, `yarn`, `pnpm`, `maven`, `gradle`, `go`, `dotnet`, `make`)
   - `artifact_target`: `github_packages`, `nexus`, `artifactory`, or `ecr_acr_gar`
   - `deploy_target`: `openshift`, `eks`, `aks`, `gke`, or `none`
   - `registry_cloud`: `ecr`, `acr`, or `gar` only when the artifact target is `ecr_acr_gar`
4. Show the preview and the required secret and variable names to the operator.
5. Commit only after the operator agrees: `commit=true` and `confirm=true`. The file is `.github/workflows/<name>.yml`.

## Workflow 2: Autonomous PR Review -> GitHub Actions Build -> Artifact Verification

1. Read the pull request with `github_get_pr` and `github_list_pr_files`.
2. Confirm the workflow file exists with `github_list_workflows` or `github_get_file`.
3. Re-check secrets and variables with `github_check_ci_secrets_and_variables` before dispatch.
4. Dispatch with `github_trigger_workflow` (`workflow_id` is the filename, `ref` is the PR head or `main`). Ask the operator before dispatching a production ref. This tool is mutating and is not confirmation-gated in the schema.
5. Poll with `github_list_workflow_runs` (capture `run_id`) and `github_get_workflow_run`.
6. On success, call `github_get_run_artifacts_metadata`. Record artifact id, size, SHA256 digest, expiration, and the git SHA from the run. Do not download the zip into the conversation and do not forward the GitHub token.

## Workflow 3: GitHub Actions Failure Root-Cause Triage & Auto-Fix

1. Detect a failed run with `github_list_workflow_runs` (`status=failure`) or `github_get_workflow_run`.
2. Call `github_get_failed_job_logs` with that `run_id`. Use the returned step name and the short excerpt only. Do not call `github_get_run_logs` to paste an archive into context.
3. Correlate the excerpt to a file with `github_get_file` or `github_search_code`. Propose a code or workflow patch. Apply it with `github_update_file` or a pull request only after the operator accepts the diff.
4. Re-run failed jobs with `github_rerun_failed_jobs` and `confirm=true`. Use `github_rerun_workflow` only when every job must start over, and ask the operator first.

## Workflow 4: Environment Gate Promotion & Downstream Hand-off

1. Call `github_get_pending_deployments` for the `run_id` when the run is waiting on `staging` or `production`.
2. Show environment id, wait timer, and whether the current user can approve. Stop for a human decision.
3. Approve or reject with `github_review_Pending_deployment` and `confirm=true`. Pass `environment_name` (`staging` or `production`) and `state` (`approved` or `rejected`).
4. After approval, read `github_get_run_artifacts_metadata` and the run SHA.
   - Hand the image tag and artifact SHA to `artifact-registry-mcp` when the registry is Nexus or Artifactory and the cluster pull will happen outside this workflow.
   - Hand the image ref and namespace to `k8s-mcp` when the workflow's deploy job is not the system of record for the rollout.
5. Verify the rollout in `observability-mcp` with the same git SHA: Prometheus error rate, Grafana dashboard, and Tempo traces for the new version. Do not mark the promotion complete until those signals are clean.

## Strict Safety Guardrails

`session_name` never carries the token. Confirmation-gated tools do nothing until `confirm=true`.

### Read-only Actions tools

- `github_list_workflows`
- `github_list_workflow_runs`
- `github_get_workflow_run`
- `github_get_run_logs`
- `github_get_failed_job_logs`
- `github_get_run_artifacts_metadata`
- `github_get_pending_deployments`
- `github_check_ci_secrets_and_variables`
- `github_generate_action_pipeline` when `commit` is false (preview only)

### Confirmation-gated tools

- `github_generate_action_pipeline` when `commit=true` (also requires `confirm=true`)
- `github_rerun_failed_jobs` (`confirm=true`)
- `github_review_Pending_deployment` (`confirm=true`)

### Mutating tools that are not schema-gated

Ask the operator before calling these against a shared or production repository:

- `github_trigger_workflow`
- `github_cancel_workflow_run`
- `github_rerun_workflow` (reruns every job, not only failures)

### Rules that always apply

- Never print, store, or invent secret values. `github_check_ci_secrets_and_variables` returns secret names only. Variable values that look like tokens are redacted.
- Never embed a personal access token, cloud key, or registry password in a generated workflow. The generator references `${{ secrets.NAME }}` and `${{ vars.NAME }}`.
- Do not approve a production environment gate without an explicit human confirmation in the same turn.
- Pass artifact name, SHA256, and git SHA downstream. Do not pass `GITHUB_TOKEN` to `k8s-mcp`, `artifact-registry-mcp`, or `observability-mcp`.
- Prefer `github_get_failed_job_logs` over full logs so the context window stays small.
