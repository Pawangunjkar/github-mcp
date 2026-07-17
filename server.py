"""
GitHub MCP Server — Main Entry Point.

Author: Pawan Gunjkar (pawangunjkar@gamil.com)

A comprehensive MCP server providing 73 tools across 12 categories
for managing GitHub via AI assistants.

Usage:
    uv run server.py                # Run via stdio (for Cursor/Claude Desktop)
    uv run mcp dev server.py        # Run with MCP Inspector (for testing)
"""

import sys
import json
import base64
from mcp.server.fastmcp import FastMCP

from github_client import GitHubClient
from credential_store import CredentialStore

# ============================================================
# Initialize MCP Server
# ============================================================

mcp = FastMCP(
    "github",
    instructions=(
        "GitHub MCP Server — Manage GitHub repositories, PRs, issues, actions, and more via REST API. "
        "Use github_connect to establish a session first (or set GITHUB_TOKEN env var). "
        "Provides 73 tools across 12 categories: repos, branches, files, PRs, issues, "
        "actions, releases, users/orgs, search, gists, webhooks, and notifications. "
        "Supports both SSH and HTTPS protocols for clone/push URLs."
    ),
)

# Global GitHub client instance
_credential_store = CredentialStore()
_github = GitHubClient(credential_store=_credential_store)

# Auto-connect if env vars are set
_env_creds = _credential_store.get_from_env()
if _env_creds:
    print(f"Auto-connecting to GitHub from environment variables...", file=sys.stderr)
    _github.connect(
        session_name="default",
        token=_env_creds.token,
        api_url=_env_creds.api_url,
        protocol=_env_creds.protocol,
        timeout=_env_creds.timeout,
    )


# ============================================================
# CATEGORY 1: Connection & Authentication (4 tools)
# ============================================================

@mcp.tool()
def github_connect(
    token: str,
    api_url: str = "https://api.github.com",
    protocol: str = "ssh",
    timeout: int = 30,
    session_name: str = "default",
) -> str:
    """
    Connect to GitHub API with a Personal Access Token.

    Credentials are automatically cached for future reconnection.

    Args:
        token: GitHub Personal Access Token (generate at https://github.com/settings/tokens)
        api_url: GitHub API URL (default: https://api.github.com, change for GitHub Enterprise)
        protocol: Preferred clone/push protocol — 'ssh' or 'https' (default: ssh)
        timeout: Request timeout in seconds (default: 30)
        session_name: Name for this session (default: 'default')
    """
    return _github.connect(
        session_name=session_name,
        token=token,
        api_url=api_url,
        protocol=protocol,
        timeout=timeout,
    )


@mcp.tool()
def github_disconnect(session_name: str = "default") -> str:
    """
    Disconnect a GitHub session.

    Args:
        session_name: Name of the session to disconnect (default: 'default')
    """
    return _github.disconnect(session_name)


@mcp.tool()
def github_status(session_name: str = "default") -> str:
    """
    Show connection status, authenticated user info, and API rate limits.

    Args:
        session_name: Session to check (default: 'default')
    """
    sessions = _github.list_sessions()
    if not sessions:
        return (
            "📡 No active GitHub sessions.\n\n"
            "Use github_connect to create a session:\n"
            "  github_connect(token='ghp_xxxxxxxxxxxx')"
        )

    lines = ["📡 Active GitHub Sessions:\n"]
    for s in sessions:
        lines.append(
            f"  🟢 {s['session_name']}: @{s['username']} ({s['name']})\n"
            f"     API: {s['api_url']} | Protocol: {s['protocol'].upper()}\n"
            f"     Uptime: {s['uptime']} | Requests: {s['requests']}"
        )

    # Fetch rate limit details
    data, error = _github.get("/rate_limit", session_name=session_name)
    if data and not error:
        core = data.get("resources", {}).get("core", {})
        search = data.get("resources", {}).get("search", {})
        lines.append(f"\n📊 Rate Limits:")
        lines.append(f"  • Core: {core.get('remaining', '?')}/{core.get('limit', '?')}")
        lines.append(f"  • Search: {search.get('remaining', '?')}/{search.get('limit', '?')}")

        reset_ts = core.get("reset")
        if reset_ts:
            import datetime
            reset_time = datetime.datetime.fromtimestamp(reset_ts)
            lines.append(f"  • Resets at: {reset_time.strftime('%H:%M:%S')}")

    return "\n".join(lines)


@mcp.tool()
def github_save_credentials(
    session_name: str,
    token: str,
    api_url: str = "https://api.github.com",
    protocol: str = "ssh",
) -> str:
    """
    Save GitHub credentials to disk cache for future use.

    Args:
        session_name: Name to save credentials under
        token: GitHub Personal Access Token
        api_url: GitHub API URL
        protocol: Preferred clone protocol — 'ssh' or 'https'
    """
    _credential_store.save_credentials(
        session_name=session_name,
        token=token,
        api_url=api_url,
        protocol=protocol,
    )
    masked = token[:4] + "****" + token[-4:] if len(token) > 8 else "****"
    return f"✅ Credentials saved for session '{session_name}' (token: {masked})"


# ============================================================
# CATEGORY 2: Repository Management (10 tools)
# ============================================================

@mcp.tool()
def github_list_repos(
    owner: str = "",
    repo_type: str = "all",
    sort: str = "updated",
    max_results: int = 30,
    session_name: str = "default",
) -> str:
    """
    List repositories for the authenticated user or a specific user/org.

    Args:
        owner: Username or org name (empty = authenticated user's repos)
        repo_type: Filter — 'all', 'owner', 'public', 'private', 'member' (default: all)
        sort: Sort by — 'updated', 'created', 'pushed', 'full_name' (default: updated)
        max_results: Maximum number of repos to return (default: 30)
        session_name: GitHub session to use
    """
    params = {"type": repo_type, "sort": sort, "per_page": min(max_results, 100)}

    if owner:
        path = f"/users/{owner}/repos"
    else:
        path = "/user/repos"

    data, error = _github.get_paginated(path, session_name=session_name, params=params, max_items=max_results)
    if error:
        return error

    if not data:
        return "📋 No repositories found."

    lines = [f"📋 Repositories ({len(data)}):\n"]
    for repo in data:
        visibility = "🔒" if repo.get("private") else "🌐"
        stars = repo.get("stargazers_count", 0)
        forks = repo.get("forks_count", 0)
        lang = repo.get("language", "")
        lang_str = f" [{lang}]" if lang else ""

        lines.append(
            f"  {visibility} {repo['full_name']}{lang_str}\n"
            f"     ⭐ {stars}  🍴 {forks}  Updated: {repo.get('updated_at', '?')[:10]}"
        )
        desc = repo.get("description")
        if desc:
            lines.append(f"     {desc[:100]}")

    return "\n".join(lines)


@mcp.tool()
def github_get_repo(owner: str, repo: str, session_name: str = "default") -> str:
    """
    Get detailed information about a specific repository.

    Shows stars, forks, languages, default branch, license, and more.

    Args:
        owner: Repository owner (user or org)
        repo: Repository name
        session_name: GitHub session to use
    """
    data, error = _github.get(f"/repos/{owner}/{repo}", session_name=session_name)
    if error:
        return error

    visibility = "🔒 Private" if data.get("private") else "🌐 Public"
    fork_info = " (Fork)" if data.get("fork") else ""
    archived = " 📦 ARCHIVED" if data.get("archived") else ""

    lines = [f"📦 {data['full_name']}{fork_info}{archived}\n"]
    lines.append(f"  • Visibility: {visibility}")
    desc = data.get("description")
    if desc:
        lines.append(f"  • Description: {desc}")
    lines.append(f"  • Default Branch: {data.get('default_branch', 'main')}")
    lines.append(f"  • Language: {data.get('language', 'N/A')}")

    license_info = data.get("license")
    if license_info:
        lines.append(f"  • License: {license_info.get('spdx_id', license_info.get('name', 'N/A'))}")

    lines.append(f"\n📊 Stats:")
    lines.append(f"  • ⭐ Stars: {data.get('stargazers_count', 0)}")
    lines.append(f"  • 🍴 Forks: {data.get('forks_count', 0)}")
    lines.append(f"  • 👁️ Watchers: {data.get('watchers_count', 0)}")
    lines.append(f"  • 🐛 Open Issues: {data.get('open_issues_count', 0)}")
    lines.append(f"  • 📏 Size: {data.get('size', 0)} KB")

    lines.append(f"\n🔗 URLs:")
    lines.append(f"  • Web: {data.get('html_url', 'N/A')}")
    lines.append(f"  • SSH: {data.get('ssh_url', 'N/A')}")
    lines.append(f"  • HTTPS: {data.get('clone_url', 'N/A')}")

    lines.append(f"\n📅 Dates:")
    lines.append(f"  • Created: {data.get('created_at', '?')[:10]}")
    lines.append(f"  • Updated: {data.get('updated_at', '?')[:10]}")
    lines.append(f"  • Pushed: {data.get('pushed_at', '?')[:10]}")

    topics = data.get("topics", [])
    if topics:
        lines.append(f"\n🏷️ Topics: {', '.join(topics)}")

    return "\n".join(lines)


@mcp.tool()
def github_create_repo(
    name: str,
    description: str = "",
    private: bool = False,
    auto_init: bool = True,
    gitignore_template: str = "",
    license_template: str = "",
    org: str = "",
    session_name: str = "default",
) -> str:
    """
    Create a new GitHub repository.

    Args:
        name: Repository name
        description: Repository description
        private: Make repository private (default: False = public)
        auto_init: Initialize with a README (default: True)
        gitignore_template: Gitignore template name (e.g., 'Python', 'Node', 'Go')
        license_template: License template (e.g., 'mit', 'apache-2.0', 'gpl-3.0')
        org: Organization to create repo under (empty = personal repo)
        session_name: GitHub session to use
    """
    payload = {
        "name": name,
        "description": description,
        "private": private,
        "auto_init": auto_init,
    }
    if gitignore_template:
        payload["gitignore_template"] = gitignore_template
    if license_template:
        payload["license_template"] = license_template

    path = f"/orgs/{org}/repos" if org else "/user/repos"
    data, error = _github.post(path, json_data=payload, session_name=session_name)
    if error:
        return error

    visibility = "🔒 Private" if private else "🌐 Public"
    ssh_url = data.get("ssh_url", "N/A")
    https_url = data.get("clone_url", "N/A")

    return (
        f"✅ Repository '{data.get('full_name', name)}' created!\n"
        f"  • Visibility: {visibility}\n"
        f"  • URL: {data.get('html_url', 'N/A')}\n"
        f"  • SSH: {ssh_url}\n"
        f"  • HTTPS: {https_url}"
    )


@mcp.tool()
def github_delete_repo(owner: str, repo: str, session_name: str = "default") -> str:
    """
    Delete a GitHub repository permanently.

    ⚠️ This action cannot be undone. All data, issues, PRs, and wiki will be lost.

    Args:
        owner: Repository owner
        repo: Repository name
        session_name: GitHub session to use
    """
    _, error = _github.delete(f"/repos/{owner}/{repo}", session_name=session_name)
    if error:
        return error

    return f"✅ Repository '{owner}/{repo}' deleted permanently."


@mcp.tool()
def github_fork_repo(
    owner: str,
    repo: str,
    org: str = "",
    new_name: str = "",
    session_name: str = "default",
) -> str:
    """
    Fork a repository to your account or an organization.

    Args:
        owner: Original repo owner
        repo: Original repo name
        org: Organization to fork to (empty = your personal account)
        new_name: Custom name for the fork (empty = keep original name)
        session_name: GitHub session to use
    """
    payload = {}
    if org:
        payload["organization"] = org
    if new_name:
        payload["name"] = new_name

    data, error = _github.post(
        f"/repos/{owner}/{repo}/forks",
        json_data=payload if payload else None,
        session_name=session_name,
    )
    if error:
        return error

    return (
        f"✅ Forked '{owner}/{repo}' → '{data.get('full_name', 'unknown')}'\n"
        f"  • URL: {data.get('html_url', 'N/A')}\n"
        f"  • SSH: {data.get('ssh_url', 'N/A')}\n"
        f"  • HTTPS: {data.get('clone_url', 'N/A')}"
    )


@mcp.tool()
def github_update_repo(
    owner: str,
    repo: str,
    description: str = "",
    homepage: str = "",
    private: str = "",
    archived: str = "",
    default_branch: str = "",
    session_name: str = "default",
) -> str:
    """
    Update repository settings.

    Only provided fields will be updated. Leave empty to keep current value.

    Args:
        owner: Repository owner
        repo: Repository name
        description: New description (empty = no change)
        homepage: Homepage URL (empty = no change)
        private: 'true' or 'false' (empty = no change)
        archived: 'true' to archive (empty = no change)
        default_branch: New default branch name (empty = no change)
        session_name: GitHub session to use
    """
    payload = {}
    if description:
        payload["description"] = description
    if homepage:
        payload["homepage"] = homepage
    if private:
        payload["private"] = private.lower() == "true"
    if archived:
        payload["archived"] = archived.lower() == "true"
    if default_branch:
        payload["default_branch"] = default_branch

    if not payload:
        return "⚠️ No fields to update. Provide at least one field."

    data, error = _github.patch(f"/repos/{owner}/{repo}", json_data=payload, session_name=session_name)
    if error:
        return error

    return f"✅ Repository '{owner}/{repo}' updated. Changed: {', '.join(payload.keys())}"


@mcp.tool()
def github_list_topics(owner: str, repo: str, session_name: str = "default") -> str:
    """
    Get repository topics/tags.

    Args:
        owner: Repository owner
        repo: Repository name
        session_name: GitHub session to use
    """
    data, error = _github.get(f"/repos/{owner}/{repo}/topics", session_name=session_name)
    if error:
        return error

    topics = data.get("names", [])
    if not topics:
        return f"🏷️ No topics set for '{owner}/{repo}'."

    return f"🏷️ Topics for '{owner}/{repo}':\n  {', '.join(topics)}"


@mcp.tool()
def github_update_topics(
    owner: str,
    repo: str,
    topics: str,
    session_name: str = "default",
) -> str:
    """
    Set repository topics/tags (replaces all existing topics).

    Args:
        owner: Repository owner
        repo: Repository name
        topics: Comma-separated topic names (e.g., 'python,mcp,devops')
        session_name: GitHub session to use
    """
    topic_list = [t.strip().lower() for t in topics.split(",") if t.strip()]

    _, error = _github.put(
        f"/repos/{owner}/{repo}/topics",
        json_data={"names": topic_list},
        session_name=session_name,
    )
    if error:
        return error

    return f"✅ Topics updated for '{owner}/{repo}': {', '.join(topic_list)}"


@mcp.tool()
def github_list_languages(owner: str, repo: str, session_name: str = "default") -> str:
    """
    Get the language breakdown for a repository (bytes per language).

    Args:
        owner: Repository owner
        repo: Repository name
        session_name: GitHub session to use
    """
    data, error = _github.get(f"/repos/{owner}/{repo}/languages", session_name=session_name)
    if error:
        return error

    if not data:
        return f"💻 No language data for '{owner}/{repo}'."

    total = sum(data.values())
    lines = [f"💻 Languages for '{owner}/{repo}':\n"]
    for lang, bytes_count in sorted(data.items(), key=lambda x: x[1], reverse=True):
        pct = (bytes_count / total * 100) if total > 0 else 0
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        lines.append(f"  {bar} {lang}: {pct:.1f}% ({bytes_count:,} bytes)")

    return "\n".join(lines)


@mcp.tool()
def github_list_contributors(
    owner: str,
    repo: str,
    max_results: int = 30,
    session_name: str = "default",
) -> str:
    """
    List repository contributors with commit counts.

    Args:
        owner: Repository owner
        repo: Repository name
        max_results: Maximum contributors to return (default: 30)
        session_name: GitHub session to use
    """
    data, error = _github.get_paginated(
        f"/repos/{owner}/{repo}/contributors",
        session_name=session_name,
        max_items=max_results,
    )
    if error:
        return error

    if not data:
        return f"👥 No contributors found for '{owner}/{repo}'."

    lines = [f"👥 Contributors for '{owner}/{repo}' ({len(data)}):\n"]
    for i, c in enumerate(data, 1):
        lines.append(f"  {i}. @{c.get('login', '?')} — {c.get('contributions', 0)} commits")

    return "\n".join(lines)


# ============================================================
# CATEGORY 3: Branch & Tag Management (8 tools)
# ============================================================

@mcp.tool()
def github_list_branches(
    owner: str,
    repo: str,
    max_results: int = 30,
    session_name: str = "default",
) -> str:
    """
    List all branches in a repository.

    Args:
        owner: Repository owner
        repo: Repository name
        max_results: Maximum branches to return (default: 30)
        session_name: GitHub session to use
    """
    data, error = _github.get_paginated(
        f"/repos/{owner}/{repo}/branches",
        session_name=session_name,
        max_items=max_results,
    )
    if error:
        return error

    if not data:
        return f"🌿 No branches found in '{owner}/{repo}'."

    lines = [f"🌿 Branches in '{owner}/{repo}' ({len(data)}):\n"]
    for branch in data:
        protected = "🛡️" if branch.get("protected") else "  "
        sha = branch.get("commit", {}).get("sha", "")[:7]
        lines.append(f"  {protected} {branch['name']}  ({sha})")

    return "\n".join(lines)


@mcp.tool()
def github_get_branch(
    owner: str,
    repo: str,
    branch: str,
    session_name: str = "default",
) -> str:
    """
    Get detailed information about a specific branch.

    Args:
        owner: Repository owner
        repo: Repository name
        branch: Branch name
        session_name: GitHub session to use
    """
    data, error = _github.get(f"/repos/{owner}/{repo}/branches/{branch}", session_name=session_name)
    if error:
        return error

    commit = data.get("commit", {})
    commit_info = commit.get("commit", {})
    author = commit_info.get("author", {})

    lines = [f"🌿 Branch: {data.get('name', branch)}\n"]
    lines.append(f"  • Protected: {'Yes 🛡️' if data.get('protected') else 'No'}")
    lines.append(f"  • Last Commit: {commit.get('sha', '?')[:7]}")
    lines.append(f"  • Author: {author.get('name', '?')} ({author.get('date', '?')[:10]})")
    lines.append(f"  • Message: {commit_info.get('message', '?')[:200]}")

    protection = data.get("protection")
    if protection:
        lines.append(f"\n🛡️ Protection Rules:")
        lines.append(f"  • Enforce admins: {protection.get('enforce_admins', {}).get('enabled', False)}")

    return "\n".join(lines)


@mcp.tool()
def github_create_branch(
    owner: str,
    repo: str,
    branch_name: str,
    from_branch: str = "",
    from_sha: str = "",
    session_name: str = "default",
) -> str:
    """
    Create a new branch from an existing branch or commit SHA.

    Args:
        owner: Repository owner
        repo: Repository name
        branch_name: Name for the new branch
        from_branch: Source branch name (default: repo's default branch)
        from_sha: Specific commit SHA to branch from (overrides from_branch)
        session_name: GitHub session to use
    """
    # Get the SHA to branch from
    if from_sha:
        sha = from_sha
    else:
        if not from_branch:
            # Get default branch
            repo_data, error = _github.get(f"/repos/{owner}/{repo}", session_name=session_name)
            if error:
                return error
            from_branch = repo_data.get("default_branch", "main")

        ref_data, error = _github.get(
            f"/repos/{owner}/{repo}/git/ref/heads/{from_branch}",
            session_name=session_name,
        )
        if error:
            return error
        sha = ref_data.get("object", {}).get("sha")

    if not sha:
        return "❌ Could not determine the source commit SHA."

    _, error = _github.post(
        f"/repos/{owner}/{repo}/git/refs",
        json_data={"ref": f"refs/heads/{branch_name}", "sha": sha},
        session_name=session_name,
    )
    if error:
        return error

    source = from_branch if from_branch else sha[:7]
    return f"✅ Branch '{branch_name}' created from '{source}' in '{owner}/{repo}'."


@mcp.tool()
def github_delete_branch(
    owner: str,
    repo: str,
    branch: str,
    session_name: str = "default",
) -> str:
    """
    Delete a branch from a repository.

    Args:
        owner: Repository owner
        repo: Repository name
        branch: Branch name to delete
        session_name: GitHub session to use
    """
    _, error = _github.delete(
        f"/repos/{owner}/{repo}/git/refs/heads/{branch}",
        session_name=session_name,
    )
    if error:
        return error

    return f"✅ Branch '{branch}' deleted from '{owner}/{repo}'."


@mcp.tool()
def github_protect_branch(
    owner: str,
    repo: str,
    branch: str,
    require_reviews: bool = True,
    required_reviewers: int = 1,
    enforce_admins: bool = False,
    session_name: str = "default",
) -> str:
    """
    Set branch protection rules.

    Args:
        owner: Repository owner
        repo: Repository name
        branch: Branch name to protect
        require_reviews: Require pull request reviews (default: True)
        required_reviewers: Minimum number of reviewers (default: 1)
        enforce_admins: Enforce rules for admins too (default: False)
        session_name: GitHub session to use
    """
    payload = {
        "enforce_admins": enforce_admins,
        "required_status_checks": None,
        "restrictions": None,
    }

    if require_reviews:
        payload["required_pull_request_reviews"] = {
            "required_approving_review_count": required_reviewers,
        }
    else:
        payload["required_pull_request_reviews"] = None

    _, error = _github.put(
        f"/repos/{owner}/{repo}/branches/{branch}/protection",
        json_data=payload,
        session_name=session_name,
    )
    if error:
        return error

    return (
        f"✅ Branch protection set for '{branch}' in '{owner}/{repo}'.\n"
        f"  • Reviews required: {require_reviews} ({required_reviewers} reviewers)\n"
        f"  • Enforce for admins: {enforce_admins}"
    )


@mcp.tool()
def github_list_tags(
    owner: str,
    repo: str,
    max_results: int = 30,
    session_name: str = "default",
) -> str:
    """
    List all tags in a repository.

    Args:
        owner: Repository owner
        repo: Repository name
        max_results: Maximum tags to return (default: 30)
        session_name: GitHub session to use
    """
    data, error = _github.get_paginated(
        f"/repos/{owner}/{repo}/tags",
        session_name=session_name,
        max_items=max_results,
    )
    if error:
        return error

    if not data:
        return f"🏷️ No tags found in '{owner}/{repo}'."

    lines = [f"🏷️ Tags in '{owner}/{repo}' ({len(data)}):\n"]
    for tag in data:
        sha = tag.get("commit", {}).get("sha", "")[:7]
        lines.append(f"  • {tag['name']}  ({sha})")

    return "\n".join(lines)


@mcp.tool()
def github_create_tag(
    owner: str,
    repo: str,
    tag_name: str,
    sha: str,
    message: str = "",
    session_name: str = "default",
) -> str:
    """
    Create a new tag (lightweight or annotated).

    Args:
        owner: Repository owner
        repo: Repository name
        tag_name: Tag name (e.g., 'v1.0.0')
        sha: Commit SHA to tag
        message: Tag message (if provided, creates an annotated tag)
        session_name: GitHub session to use
    """
    if message:
        # Create annotated tag object first
        tag_data, error = _github.post(
            f"/repos/{owner}/{repo}/git/tags",
            json_data={
                "tag": tag_name,
                "message": message,
                "object": sha,
                "type": "commit",
            },
            session_name=session_name,
        )
        if error:
            return error
        tag_sha = tag_data.get("sha", sha)
        obj_type = "tag"
    else:
        tag_sha = sha
        obj_type = "commit"

    # Create the ref
    _, error = _github.post(
        f"/repos/{owner}/{repo}/git/refs",
        json_data={"ref": f"refs/tags/{tag_name}", "sha": tag_sha},
        session_name=session_name,
    )
    if error:
        return error

    tag_type = "annotated" if message else "lightweight"
    return f"✅ Tag '{tag_name}' created ({tag_type}) at {sha[:7]} in '{owner}/{repo}'."


@mcp.tool()
def github_compare_branches(
    owner: str,
    repo: str,
    base: str,
    head: str,
    session_name: str = "default",
) -> str:
    """
    Compare two branches showing ahead/behind counts and changed files.

    Args:
        owner: Repository owner
        repo: Repository name
        base: Base branch (e.g., 'main')
        head: Head branch to compare (e.g., 'feature-branch')
        session_name: GitHub session to use
    """
    data, error = _github.get(
        f"/repos/{owner}/{repo}/compare/{base}...{head}",
        session_name=session_name,
    )
    if error:
        return error

    lines = [f"🔀 Comparing {base}...{head} in '{owner}/{repo}':\n"]
    lines.append(f"  • Status: {data.get('status', '?')}")
    lines.append(f"  • Ahead by: {data.get('ahead_by', 0)} commits")
    lines.append(f"  • Behind by: {data.get('behind_by', 0)} commits")
    lines.append(f"  • Total Commits: {data.get('total_commits', 0)}")

    files = data.get("files", [])
    if files:
        lines.append(f"\n📁 Changed Files ({len(files)}):")
        for f in files[:30]:
            status_icon = {"added": "➕", "removed": "➖", "modified": "✏️", "renamed": "📝"}.get(f.get("status", ""), "❓")
            lines.append(f"  {status_icon} {f.get('filename', '?')} (+{f.get('additions', 0)}/−{f.get('deletions', 0)})")
        if len(files) > 30:
            lines.append(f"  ... and {len(files) - 30} more files")

    return "\n".join(lines)


# ============================================================
# CATEGORY 4: File & Content Operations (6 tools)
# ============================================================

@mcp.tool()
def github_get_file(
    owner: str,
    repo: str,
    path: str,
    ref: str = "",
    session_name: str = "default",
) -> str:
    """
    Get file content from a repository (auto-decodes base64).

    Args:
        owner: Repository owner
        repo: Repository name
        path: File path in the repo (e.g., 'src/main.py')
        ref: Branch, tag, or commit SHA (empty = default branch)
        session_name: GitHub session to use
    """
    params = {}
    if ref:
        params["ref"] = ref

    data, error = _github.get(
        f"/repos/{owner}/{repo}/contents/{path}",
        params=params if params else None,
        session_name=session_name,
    )
    if error:
        return error

    if isinstance(data, list):
        return f"📁 '{path}' is a directory. Use github_get_tree to list contents."

    content = data.get("content", "")
    encoding = data.get("encoding", "")

    if encoding == "base64" and content:
        try:
            decoded = base64.b64decode(content).decode("utf-8", errors="replace")
        except Exception:
            decoded = "(binary file — cannot decode)"
    else:
        decoded = content

    lines = [f"📄 {data.get('name', path)} ({data.get('size', 0)} bytes)\n"]
    lines.append(f"  • Path: {data.get('path', path)}")
    lines.append(f"  • SHA: {data.get('sha', '?')[:7]}")
    ref_label = ref or "default branch"
    lines.append(f"  • Ref: {ref_label}")
    lines.append(f"\n{decoded}")

    return "\n".join(lines)


@mcp.tool()
def github_create_file(
    owner: str,
    repo: str,
    path: str,
    content: str,
    message: str,
    branch: str = "",
    session_name: str = "default",
) -> str:
    """
    Create a new file in a repository via a commit.

    Args:
        owner: Repository owner
        repo: Repository name
        path: File path to create (e.g., 'docs/guide.md')
        content: File content (will be base64-encoded automatically)
        message: Commit message
        branch: Branch to commit to (empty = default branch)
        session_name: GitHub session to use
    """
    encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")

    payload = {
        "message": message,
        "content": encoded,
    }
    if branch:
        payload["branch"] = branch

    data, error = _github.put(
        f"/repos/{owner}/{repo}/contents/{path}",
        json_data=payload,
        session_name=session_name,
    )
    if error:
        return error

    commit = data.get("commit", {})
    return (
        f"✅ File '{path}' created in '{owner}/{repo}'.\n"
        f"  • Commit: {commit.get('sha', '?')[:7]}\n"
        f"  • Message: {message}\n"
        f"  • Branch: {branch or 'default'}"
    )


@mcp.tool()
def github_update_file(
    owner: str,
    repo: str,
    path: str,
    content: str,
    message: str,
    sha: str,
    branch: str = "",
    session_name: str = "default",
) -> str:
    """
    Update an existing file in a repository via a commit.

    You need the current file's SHA (get it from github_get_file).

    Args:
        owner: Repository owner
        repo: Repository name
        path: File path to update
        content: New file content
        message: Commit message
        sha: Current file SHA (required to prevent conflicts)
        branch: Branch to commit to (empty = default branch)
        session_name: GitHub session to use
    """
    encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")

    payload = {
        "message": message,
        "content": encoded,
        "sha": sha,
    }
    if branch:
        payload["branch"] = branch

    data, error = _github.put(
        f"/repos/{owner}/{repo}/contents/{path}",
        json_data=payload,
        session_name=session_name,
    )
    if error:
        return error

    commit = data.get("commit", {})
    return (
        f"✅ File '{path}' updated in '{owner}/{repo}'.\n"
        f"  • Commit: {commit.get('sha', '?')[:7]}\n"
        f"  • Message: {message}"
    )


@mcp.tool()
def github_delete_file(
    owner: str,
    repo: str,
    path: str,
    message: str,
    sha: str,
    branch: str = "",
    session_name: str = "default",
) -> str:
    """
    Delete a file from a repository via a commit.

    Args:
        owner: Repository owner
        repo: Repository name
        path: File path to delete
        message: Commit message
        sha: Current file SHA (get from github_get_file)
        branch: Branch to commit to (empty = default branch)
        session_name: GitHub session to use
    """
    payload = {
        "message": message,
        "sha": sha,
    }
    if branch:
        payload["branch"] = branch

    _, error = _github.delete(
        f"/repos/{owner}/{repo}/contents/{path}",
        json_data=payload,
        session_name=session_name,
    )
    if error:
        return error

    return f"✅ File '{path}' deleted from '{owner}/{repo}'. Message: {message}"


@mcp.tool()
def github_get_tree(
    owner: str,
    repo: str,
    path: str = "",
    ref: str = "",
    session_name: str = "default",
) -> str:
    """
    Get directory listing/tree for a repository path.

    Args:
        owner: Repository owner
        repo: Repository name
        path: Directory path (empty = root)
        ref: Branch, tag, or SHA (empty = default branch)
        session_name: GitHub session to use
    """
    params = {}
    if ref:
        params["ref"] = ref

    endpoint = f"/repos/{owner}/{repo}/contents/{path}" if path else f"/repos/{owner}/{repo}/contents"
    data, error = _github.get(endpoint, params=params if params else None, session_name=session_name)
    if error:
        return error

    if not isinstance(data, list):
        return f"📄 '{path}' is a file, not a directory. Use github_get_file to read it."

    lines = [f"📁 Tree: {owner}/{repo}/{path or ''}\n"]

    # Separate dirs and files
    dirs = [item for item in data if item.get("type") == "dir"]
    files = [item for item in data if item.get("type") != "dir"]

    for d in sorted(dirs, key=lambda x: x.get("name", "")):
        lines.append(f"  📁 {d['name']}/")

    for f in sorted(files, key=lambda x: x.get("name", "")):
        size = f.get("size", 0)
        size_str = f"{size:,} bytes" if size < 10000 else f"{size / 1024:.1f} KB"
        lines.append(f"  📄 {f['name']}  ({size_str})")

    lines.append(f"\n  Total: {len(dirs)} directories, {len(files)} files")

    return "\n".join(lines)


@mcp.tool()
def github_get_clone_url(
    owner: str,
    repo: str,
    protocol: str = "",
    session_name: str = "default",
) -> str:
    """
    Get the clone URL for a repository in SSH or HTTPS format.

    Args:
        owner: Repository owner
        repo: Repository name
        protocol: 'ssh' or 'https' (empty = use session default)
        session_name: GitHub session to use
    """
    if not protocol:
        protocol = _github.get_protocol(session_name)

    if protocol == "https":
        url = f"https://github.com/{owner}/{repo}.git"
    else:
        url = f"git@github.com:{owner}/{repo}.git"

    other_protocol = "https" if protocol == "ssh" else "ssh"
    if other_protocol == "https":
        other_url = f"https://github.com/{owner}/{repo}.git"
    else:
        other_url = f"git@github.com:{owner}/{repo}.git"

    return (
        f"🔗 Clone URL for '{owner}/{repo}':\n\n"
        f"  {protocol.upper()} (preferred):\n"
        f"    git clone {url}\n\n"
        f"  {other_protocol.upper()} (alternative):\n"
        f"    git clone {other_url}"
    )


# ============================================================
# CATEGORY 5: Pull Requests (10 tools)
# ============================================================

@mcp.tool()
def github_list_prs(
    owner: str,
    repo: str,
    state: str = "open",
    sort: str = "created",
    max_results: int = 30,
    session_name: str = "default",
) -> str:
    """
    List pull requests for a repository.

    Args:
        owner: Repository owner
        repo: Repository name
        state: Filter — 'open', 'closed', 'all' (default: open)
        sort: Sort by — 'created', 'updated', 'popularity' (default: created)
        max_results: Maximum PRs to return (default: 30)
        session_name: GitHub session to use
    """
    data, error = _github.get_paginated(
        f"/repos/{owner}/{repo}/pulls",
        params={"state": state, "sort": sort},
        session_name=session_name,
        max_items=max_results,
    )
    if error:
        return error

    if not data:
        return f"📋 No {state} pull requests in '{owner}/{repo}'."

    lines = [f"📋 Pull Requests ({len(data)}, {state}):\n"]
    for pr in data:
        state_icon = {"open": "🟢", "closed": "🔴"}.get(pr.get("state", ""), "❓")
        if pr.get("merged_at"):
            state_icon = "🟣"

        draft = " [DRAFT]" if pr.get("draft") else ""
        lines.append(
            f"  {state_icon} #{pr['number']}: {pr['title']}{draft}\n"
            f"     {pr.get('head', {}).get('ref', '?')} → {pr.get('base', {}).get('ref', '?')}"
            f"  by @{pr.get('user', {}).get('login', '?')}"
        )

    return "\n".join(lines)


@mcp.tool()
def github_get_pr(
    owner: str,
    repo: str,
    pr_number: int,
    session_name: str = "default",
) -> str:
    """
    Get detailed information about a pull request.

    Args:
        owner: Repository owner
        repo: Repository name
        pr_number: PR number
        session_name: GitHub session to use
    """
    data, error = _github.get(f"/repos/{owner}/{repo}/pulls/{pr_number}", session_name=session_name)
    if error:
        return error

    state = data.get("state", "unknown")
    if data.get("merged"):
        state_icon = "🟣 Merged"
    elif state == "open":
        state_icon = "🟢 Open"
    else:
        state_icon = "🔴 Closed"

    draft = " [DRAFT]" if data.get("draft") else ""

    lines = [f"{state_icon} PR #{data['number']}: {data['title']}{draft}\n"]
    lines.append(f"  • Author: @{data.get('user', {}).get('login', '?')}")
    lines.append(f"  • Branch: {data.get('head', {}).get('ref', '?')} → {data.get('base', {}).get('ref', '?')}")
    lines.append(f"  • Created: {data.get('created_at', '?')[:10]}")
    lines.append(f"  • Updated: {data.get('updated_at', '?')[:10]}")
    lines.append(f"  • Mergeable: {data.get('mergeable', 'unknown')}")
    lines.append(f"  • Changed Files: {data.get('changed_files', 0)}")
    lines.append(f"  • Additions: +{data.get('additions', 0)}")
    lines.append(f"  • Deletions: −{data.get('deletions', 0)}")
    lines.append(f"  • Commits: {data.get('commits', 0)}")
    lines.append(f"  • Comments: {data.get('comments', 0)}")
    lines.append(f"  • Review Comments: {data.get('review_comments', 0)}")
    lines.append(f"  • URL: {data.get('html_url', 'N/A')}")

    body = data.get("body")
    if body:
        lines.append(f"\n📝 Description:\n{body[:500]}")

    labels = data.get("labels", [])
    if labels:
        label_names = [l.get("name", "") for l in labels]
        lines.append(f"\n🏷️ Labels: {', '.join(label_names)}")

    assignees = data.get("assignees", [])
    if assignees:
        names = [f"@{a.get('login', '?')}" for a in assignees]
        lines.append(f"👤 Assignees: {', '.join(names)}")

    reviewers = data.get("requested_reviewers", [])
    if reviewers:
        names = [f"@{r.get('login', '?')}" for r in reviewers]
        lines.append(f"👀 Requested Reviewers: {', '.join(names)}")

    return "\n".join(lines)


@mcp.tool()
def github_create_pr(
    owner: str,
    repo: str,
    title: str,
    head: str,
    base: str,
    body: str = "",
    draft: bool = False,
    session_name: str = "default",
) -> str:
    """
    Create a new pull request.

    Args:
        owner: Repository owner
        repo: Repository name
        title: PR title
        head: Source branch name (e.g., 'feature-branch')
        base: Target branch name (e.g., 'main')
        body: PR description/body (markdown supported)
        draft: Create as draft PR (default: False)
        session_name: GitHub session to use
    """
    payload = {
        "title": title,
        "head": head,
        "base": base,
        "body": body,
        "draft": draft,
    }

    data, error = _github.post(f"/repos/{owner}/{repo}/pulls", json_data=payload, session_name=session_name)
    if error:
        return error

    return (
        f"✅ PR #{data.get('number')} created: {title}\n"
        f"  • Branch: {head} → {base}\n"
        f"  • Draft: {draft}\n"
        f"  • URL: {data.get('html_url', 'N/A')}"
    )


@mcp.tool()
def github_update_pr(
    owner: str,
    repo: str,
    pr_number: int,
    title: str = "",
    body: str = "",
    base: str = "",
    state: str = "",
    session_name: str = "default",
) -> str:
    """
    Update a pull request's title, body, base branch, or state.

    Args:
        owner: Repository owner
        repo: Repository name
        pr_number: PR number
        title: New title (empty = no change)
        body: New body (empty = no change)
        base: New base branch (empty = no change)
        state: New state — 'open' or 'closed' (empty = no change)
        session_name: GitHub session to use
    """
    payload = {}
    if title:
        payload["title"] = title
    if body:
        payload["body"] = body
    if base:
        payload["base"] = base
    if state:
        payload["state"] = state

    if not payload:
        return "⚠️ No fields to update."

    _, error = _github.patch(f"/repos/{owner}/{repo}/pulls/{pr_number}", json_data=payload, session_name=session_name)
    if error:
        return error

    return f"✅ PR #{pr_number} updated. Changed: {', '.join(payload.keys())}"


@mcp.tool()
def github_merge_pr(
    owner: str,
    repo: str,
    pr_number: int,
    merge_method: str = "merge",
    commit_title: str = "",
    commit_message: str = "",
    session_name: str = "default",
) -> str:
    """
    Merge a pull request.

    Args:
        owner: Repository owner
        repo: Repository name
        pr_number: PR number to merge
        merge_method: Merge strategy — 'merge', 'squash', or 'rebase' (default: merge)
        commit_title: Custom merge commit title (empty = default)
        commit_message: Custom merge commit message (empty = default)
        session_name: GitHub session to use
    """
    payload = {"merge_method": merge_method}
    if commit_title:
        payload["commit_title"] = commit_title
    if commit_message:
        payload["commit_message"] = commit_message

    data, error = _github.put(
        f"/repos/{owner}/{repo}/pulls/{pr_number}/merge",
        json_data=payload,
        session_name=session_name,
    )
    if error:
        return error

    return (
        f"✅ PR #{pr_number} merged ({merge_method})!\n"
        f"  • SHA: {data.get('sha', '?')[:7]}\n"
        f"  • Message: {data.get('message', 'Merged')}"
    )


@mcp.tool()
def github_close_pr(owner: str, repo: str, pr_number: int, session_name: str = "default") -> str:
    """
    Close a pull request without merging.

    Args:
        owner: Repository owner
        repo: Repository name
        pr_number: PR number to close
        session_name: GitHub session to use
    """
    return github_update_pr(owner=owner, repo=repo, pr_number=pr_number, state="closed", session_name=session_name)


@mcp.tool()
def github_list_pr_files(
    owner: str,
    repo: str,
    pr_number: int,
    session_name: str = "default",
) -> str:
    """
    List files changed in a pull request.

    Args:
        owner: Repository owner
        repo: Repository name
        pr_number: PR number
        session_name: GitHub session to use
    """
    data, error = _github.get_paginated(
        f"/repos/{owner}/{repo}/pulls/{pr_number}/files",
        session_name=session_name,
        max_items=100,
    )
    if error:
        return error

    if not data:
        return f"📁 No files changed in PR #{pr_number}."

    total_add = sum(f.get("additions", 0) for f in data)
    total_del = sum(f.get("deletions", 0) for f in data)

    lines = [f"📁 Files changed in PR #{pr_number} ({len(data)} files, +{total_add}/−{total_del}):\n"]
    for f in data:
        status_icon = {"added": "➕", "removed": "➖", "modified": "✏️", "renamed": "📝"}.get(f.get("status", ""), "❓")
        lines.append(f"  {status_icon} {f.get('filename', '?')} (+{f.get('additions', 0)}/−{f.get('deletions', 0)})")

    return "\n".join(lines)


@mcp.tool()
def github_list_pr_reviews(
    owner: str,
    repo: str,
    pr_number: int,
    session_name: str = "default",
) -> str:
    """
    List reviews on a pull request.

    Args:
        owner: Repository owner
        repo: Repository name
        pr_number: PR number
        session_name: GitHub session to use
    """
    data, error = _github.get_paginated(
        f"/repos/{owner}/{repo}/pulls/{pr_number}/reviews",
        session_name=session_name,
        max_items=50,
    )
    if error:
        return error

    if not data:
        return f"👀 No reviews on PR #{pr_number}."

    lines = [f"👀 Reviews on PR #{pr_number} ({len(data)}):\n"]
    for review in data:
        state = review.get("state", "unknown")
        state_icon = {
            "APPROVED": "✅", "CHANGES_REQUESTED": "🔴",
            "COMMENTED": "💬", "DISMISSED": "⛔", "PENDING": "⏳",
        }.get(state, "❓")
        lines.append(f"  {state_icon} @{review.get('user', {}).get('login', '?')}: {state}")
        body = review.get("body")
        if body:
            lines.append(f"     {body[:150]}")

    return "\n".join(lines)


@mcp.tool()
def github_request_reviewers(
    owner: str,
    repo: str,
    pr_number: int,
    reviewers: str,
    session_name: str = "default",
) -> str:
    """
    Request reviewers for a pull request.

    Args:
        owner: Repository owner
        repo: Repository name
        pr_number: PR number
        reviewers: Comma-separated GitHub usernames (e.g., 'user1,user2')
        session_name: GitHub session to use
    """
    reviewer_list = [r.strip().lstrip("@") for r in reviewers.split(",") if r.strip()]

    _, error = _github.post(
        f"/repos/{owner}/{repo}/pulls/{pr_number}/requested_reviewers",
        json_data={"reviewers": reviewer_list},
        session_name=session_name,
    )
    if error:
        return error

    return f"✅ Reviewers requested for PR #{pr_number}: {', '.join('@' + r for r in reviewer_list)}"


@mcp.tool()
def github_create_pr_comment(
    owner: str,
    repo: str,
    pr_number: int,
    body: str,
    session_name: str = "default",
) -> str:
    """
    Add a comment on a pull request.

    Args:
        owner: Repository owner
        repo: Repository name
        pr_number: PR number
        body: Comment body (markdown supported)
        session_name: GitHub session to use
    """
    # PRs use the issues comments endpoint
    data, error = _github.post(
        f"/repos/{owner}/{repo}/issues/{pr_number}/comments",
        json_data={"body": body},
        session_name=session_name,
    )
    if error:
        return error

    return f"✅ Comment added to PR #{pr_number}.\n  • URL: {data.get('html_url', 'N/A')}"


# ============================================================
# CATEGORY 6: Issues (8 tools)
# ============================================================

@mcp.tool()
def github_list_issues(
    owner: str,
    repo: str,
    state: str = "open",
    labels: str = "",
    assignee: str = "",
    sort: str = "created",
    max_results: int = 30,
    session_name: str = "default",
) -> str:
    """
    List issues in a repository with optional filters.

    Args:
        owner: Repository owner
        repo: Repository name
        state: Filter — 'open', 'closed', 'all' (default: open)
        labels: Comma-separated label names to filter by
        assignee: Filter by assignee username
        sort: Sort by — 'created', 'updated', 'comments' (default: created)
        max_results: Maximum issues to return (default: 30)
        session_name: GitHub session to use
    """
    params = {"state": state, "sort": sort}
    if labels:
        params["labels"] = labels
    if assignee:
        params["assignee"] = assignee

    data, error = _github.get_paginated(
        f"/repos/{owner}/{repo}/issues",
        params=params,
        session_name=session_name,
        max_items=max_results,
    )
    if error:
        return error

    # Filter out PRs (GitHub API returns both issues and PRs)
    issues = [i for i in data if "pull_request" not in i]

    if not issues:
        return f"📋 No {state} issues in '{owner}/{repo}'."

    lines = [f"📋 Issues ({len(issues)}, {state}):\n"]
    for issue in issues:
        state_icon = "🟢" if issue.get("state") == "open" else "🔴"
        label_tags = ""
        issue_labels = issue.get("labels", [])
        if issue_labels:
            label_tags = " [" + ", ".join(l.get("name", "") for l in issue_labels[:3]) + "]"

        lines.append(
            f"  {state_icon} #{issue['number']}: {issue['title']}{label_tags}\n"
            f"     by @{issue.get('user', {}).get('login', '?')}  💬 {issue.get('comments', 0)} comments"
        )

    return "\n".join(lines)


@mcp.tool()
def github_get_issue(
    owner: str,
    repo: str,
    issue_number: int,
    session_name: str = "default",
) -> str:
    """
    Get detailed information about an issue.

    Args:
        owner: Repository owner
        repo: Repository name
        issue_number: Issue number
        session_name: GitHub session to use
    """
    data, error = _github.get(f"/repos/{owner}/{repo}/issues/{issue_number}", session_name=session_name)
    if error:
        return error

    state_icon = "🟢 Open" if data.get("state") == "open" else "🔴 Closed"

    lines = [f"{state_icon} Issue #{data['number']}: {data['title']}\n"]
    lines.append(f"  • Author: @{data.get('user', {}).get('login', '?')}")
    lines.append(f"  • Created: {data.get('created_at', '?')[:10]}")
    lines.append(f"  • Updated: {data.get('updated_at', '?')[:10]}")
    lines.append(f"  • Comments: {data.get('comments', 0)}")
    lines.append(f"  • URL: {data.get('html_url', 'N/A')}")

    labels = data.get("labels", [])
    if labels:
        lines.append(f"  • Labels: {', '.join(l.get('name', '') for l in labels)}")

    assignees = data.get("assignees", [])
    if assignees:
        lines.append(f"  • Assignees: {', '.join('@' + a.get('login', '?') for a in assignees)}")

    milestone = data.get("milestone")
    if milestone:
        lines.append(f"  • Milestone: {milestone.get('title', '?')}")

    body = data.get("body")
    if body:
        lines.append(f"\n📝 Body:\n{body[:800]}")

    return "\n".join(lines)


@mcp.tool()
def github_create_issue(
    owner: str,
    repo: str,
    title: str,
    body: str = "",
    labels: str = "",
    assignees: str = "",
    session_name: str = "default",
) -> str:
    """
    Create a new issue in a repository.

    Args:
        owner: Repository owner
        repo: Repository name
        title: Issue title
        body: Issue body (markdown supported)
        labels: Comma-separated label names (e.g., 'bug,priority:high')
        assignees: Comma-separated usernames to assign
        session_name: GitHub session to use
    """
    payload = {"title": title}
    if body:
        payload["body"] = body
    if labels:
        payload["labels"] = [l.strip() for l in labels.split(",") if l.strip()]
    if assignees:
        payload["assignees"] = [a.strip().lstrip("@") for a in assignees.split(",") if a.strip()]

    data, error = _github.post(f"/repos/{owner}/{repo}/issues", json_data=payload, session_name=session_name)
    if error:
        return error

    return (
        f"✅ Issue #{data.get('number')} created: {title}\n"
        f"  • URL: {data.get('html_url', 'N/A')}"
    )


@mcp.tool()
def github_update_issue(
    owner: str,
    repo: str,
    issue_number: int,
    title: str = "",
    body: str = "",
    labels: str = "",
    assignees: str = "",
    state: str = "",
    session_name: str = "default",
) -> str:
    """
    Update an issue's title, body, labels, assignees, or state.

    Args:
        owner: Repository owner
        repo: Repository name
        issue_number: Issue number
        title: New title (empty = no change)
        body: New body (empty = no change)
        labels: Comma-separated labels (replaces all labels; empty = no change)
        assignees: Comma-separated assignees (replaces all; empty = no change)
        state: 'open' or 'closed' (empty = no change)
        session_name: GitHub session to use
    """
    payload = {}
    if title:
        payload["title"] = title
    if body:
        payload["body"] = body
    if labels:
        payload["labels"] = [l.strip() for l in labels.split(",") if l.strip()]
    if assignees:
        payload["assignees"] = [a.strip().lstrip("@") for a in assignees.split(",") if a.strip()]
    if state:
        payload["state"] = state

    if not payload:
        return "⚠️ No fields to update."

    _, error = _github.patch(f"/repos/{owner}/{repo}/issues/{issue_number}", json_data=payload, session_name=session_name)
    if error:
        return error

    return f"✅ Issue #{issue_number} updated. Changed: {', '.join(payload.keys())}"


@mcp.tool()
def github_close_issue(owner: str, repo: str, issue_number: int, session_name: str = "default") -> str:
    """
    Close an issue.

    Args:
        owner: Repository owner
        repo: Repository name
        issue_number: Issue number to close
        session_name: GitHub session to use
    """
    return github_update_issue(owner=owner, repo=repo, issue_number=issue_number, state="closed", session_name=session_name)


@mcp.tool()
def github_create_issue_comment(
    owner: str,
    repo: str,
    issue_number: int,
    body: str,
    session_name: str = "default",
) -> str:
    """
    Add a comment on an issue.

    Args:
        owner: Repository owner
        repo: Repository name
        issue_number: Issue number
        body: Comment body (markdown supported)
        session_name: GitHub session to use
    """
    data, error = _github.post(
        f"/repos/{owner}/{repo}/issues/{issue_number}/comments",
        json_data={"body": body},
        session_name=session_name,
    )
    if error:
        return error

    return f"✅ Comment added to issue #{issue_number}.\n  • URL: {data.get('html_url', 'N/A')}"


@mcp.tool()
def github_list_issue_comments(
    owner: str,
    repo: str,
    issue_number: int,
    max_results: int = 30,
    session_name: str = "default",
) -> str:
    """
    List comments on an issue.

    Args:
        owner: Repository owner
        repo: Repository name
        issue_number: Issue number
        max_results: Maximum comments to return (default: 30)
        session_name: GitHub session to use
    """
    data, error = _github.get_paginated(
        f"/repos/{owner}/{repo}/issues/{issue_number}/comments",
        session_name=session_name,
        max_items=max_results,
    )
    if error:
        return error

    if not data:
        return f"💬 No comments on issue #{issue_number}."

    lines = [f"💬 Comments on issue #{issue_number} ({len(data)}):\n"]
    for comment in data:
        lines.append(
            f"  @{comment.get('user', {}).get('login', '?')} ({comment.get('created_at', '?')[:10]}):\n"
            f"    {comment.get('body', '')[:200]}\n"
        )

    return "\n".join(lines)


@mcp.tool()
def github_add_labels(
    owner: str,
    repo: str,
    issue_number: int,
    labels: str,
    session_name: str = "default",
) -> str:
    """
    Add labels to an issue or pull request.

    Args:
        owner: Repository owner
        repo: Repository name
        issue_number: Issue or PR number
        labels: Comma-separated label names to add
        session_name: GitHub session to use
    """
    label_list = [l.strip() for l in labels.split(",") if l.strip()]

    _, error = _github.post(
        f"/repos/{owner}/{repo}/issues/{issue_number}/labels",
        json_data={"labels": label_list},
        session_name=session_name,
    )
    if error:
        return error

    return f"✅ Labels added to #{issue_number}: {', '.join(label_list)}"


# ============================================================
# CATEGORY 7: Actions & Workflows (7 tools)
# ============================================================

@mcp.tool()
def github_list_workflows(
    owner: str,
    repo: str,
    session_name: str = "default",
) -> str:
    """
    List all GitHub Actions workflows in a repository.

    Args:
        owner: Repository owner
        repo: Repository name
        session_name: GitHub session to use
    """
    data, error = _github.get(f"/repos/{owner}/{repo}/actions/workflows", session_name=session_name)
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
    owner: str,
    repo: str,
    workflow_id: str,
    ref: str = "main",
    inputs: str = "",
    session_name: str = "default",
) -> str:
    """
    Trigger a workflow dispatch event (manually run a workflow).

    The workflow must have a 'workflow_dispatch' trigger defined.

    Args:
        owner: Repository owner
        repo: Repository name
        workflow_id: Workflow ID or filename (e.g., 'deploy.yml')
        ref: Branch or tag to run on (default: main)
        inputs: Workflow inputs as JSON string (e.g., '{"environment": "staging"}')
        session_name: GitHub session to use
    """
    payload = {"ref": ref}
    if inputs:
        try:
            payload["inputs"] = json.loads(inputs)
        except json.JSONDecodeError:
            return f"❌ Invalid JSON inputs: {inputs}"

    _, error = _github.post(
        f"/repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches",
        json_data=payload,
        session_name=session_name,
    )
    if error:
        return error

    return f"✅ Workflow '{workflow_id}' triggered on ref '{ref}'." + (f"\n  Inputs: {inputs}" if inputs else "")


@mcp.tool()
def github_list_workflow_runs(
    owner: str,
    repo: str,
    workflow_id: str = "",
    status: str = "",
    branch: str = "",
    max_results: int = 20,
    session_name: str = "default",
) -> str:
    """
    List workflow runs for a repository or specific workflow.

    Args:
        owner: Repository owner
        repo: Repository name
        workflow_id: Specific workflow ID or filename (empty = all workflows)
        status: Filter — 'completed', 'in_progress', 'queued', 'success', 'failure'
        branch: Filter by branch name
        max_results: Maximum runs to return (default: 20)
        session_name: GitHub session to use
    """
    params = {"per_page": min(max_results, 100)}
    if status:
        params["status"] = status
    if branch:
        params["branch"] = branch

    path = f"/repos/{owner}/{repo}/actions/workflows/{workflow_id}/runs" if workflow_id else f"/repos/{owner}/{repo}/actions/runs"

    data, error = _github.get(path, params=params, session_name=session_name)
    if error:
        return error

    runs = data.get("workflow_runs", [])[:max_results]
    if not runs:
        return f"⚡ No workflow runs found."

    lines = [f"⚡ Workflow Runs ({len(runs)}):\n"]
    for run in runs:
        conclusion = run.get("conclusion", run.get("status", "unknown"))
        icon_map = {
            "success": "🟢", "failure": "🔴", "cancelled": "⚫",
            "in_progress": "🔵", "queued": "⏳", "skipped": "⬜",
        }
        icon = icon_map.get(conclusion, "❓")

        lines.append(
            f"  {icon} #{run.get('run_number', '?')}: {run.get('name', '?')} — {conclusion}\n"
            f"     Branch: {run.get('head_branch', '?')} | {run.get('created_at', '?')[:10]}"
        )

    return "\n".join(lines)


@mcp.tool()
def github_get_workflow_run(
    owner: str,
    repo: str,
    run_id: int,
    session_name: str = "default",
) -> str:
    """
    Get details of a specific workflow run.

    Args:
        owner: Repository owner
        repo: Repository name
        run_id: Workflow run ID
        session_name: GitHub session to use
    """
    data, error = _github.get(f"/repos/{owner}/{repo}/actions/runs/{run_id}", session_name=session_name)
    if error:
        return error

    conclusion = data.get("conclusion", data.get("status", "unknown"))
    icon_map = {"success": "🟢", "failure": "🔴", "cancelled": "⚫", "in_progress": "🔵"}
    icon = icon_map.get(conclusion, "❓")

    lines = [f"{icon} Workflow Run #{data.get('run_number', '?')}: {data.get('name', '?')}\n"]
    lines.append(f"  • Status: {data.get('status', '?')}")
    lines.append(f"  • Conclusion: {conclusion}")
    lines.append(f"  • Branch: {data.get('head_branch', '?')}")
    lines.append(f"  • Event: {data.get('event', '?')}")
    lines.append(f"  • Created: {data.get('created_at', '?')[:19]}")
    lines.append(f"  • Updated: {data.get('updated_at', '?')[:19]}")
    lines.append(f"  • URL: {data.get('html_url', 'N/A')}")

    actor = data.get("actor", {})
    if actor:
        lines.append(f"  • Triggered by: @{actor.get('login', '?')}")

    return "\n".join(lines)


@mcp.tool()
def github_get_run_logs(
    owner: str,
    repo: str,
    run_id: int,
    session_name: str = "default",
) -> str:
    """
    Get the download URL for workflow run logs (returns a redirect URL).

    Args:
        owner: Repository owner
        repo: Repository name
        run_id: Workflow run ID
        session_name: GitHub session to use
    """
    data, error = _github.get(
        f"/repos/{owner}/{repo}/actions/runs/{run_id}/logs",
        session_name=session_name,
        raw=True,
    )
    if error:
        # The logs endpoint often redirects — provide the URL instead
        return (
            f"📜 Logs for run #{run_id} can be downloaded from:\n"
            f"  https://github.com/{owner}/{repo}/actions/runs/{run_id}\n\n"
            f"💡 Click 'Download logs' in the Actions UI, or use the 'jobs' endpoint for specific job logs."
        )

    return f"📜 Logs for run #{run_id}:\n\n{data}"


@mcp.tool()
def github_cancel_workflow_run(
    owner: str,
    repo: str,
    run_id: int,
    session_name: str = "default",
) -> str:
    """
    Cancel a workflow run that is in progress.

    Args:
        owner: Repository owner
        repo: Repository name
        run_id: Workflow run ID to cancel
        session_name: GitHub session to use
    """
    _, error = _github.post(
        f"/repos/{owner}/{repo}/actions/runs/{run_id}/cancel",
        session_name=session_name,
    )
    if error:
        return error

    return f"✅ Workflow run #{run_id} cancelled."


@mcp.tool()
def github_rerun_workflow(
    owner: str,
    repo: str,
    run_id: int,
    session_name: str = "default",
) -> str:
    """
    Re-run a workflow (all jobs or only failed jobs).

    Args:
        owner: Repository owner
        repo: Repository name
        run_id: Workflow run ID to re-run
        session_name: GitHub session to use
    """
    _, error = _github.post(
        f"/repos/{owner}/{repo}/actions/runs/{run_id}/rerun",
        session_name=session_name,
    )
    if error:
        return error

    return f"✅ Workflow run #{run_id} re-triggered."


# ============================================================
# CATEGORY 8: Releases (5 tools)
# ============================================================

@mcp.tool()
def github_list_releases(
    owner: str,
    repo: str,
    max_results: int = 20,
    session_name: str = "default",
) -> str:
    """
    List all releases for a repository.

    Args:
        owner: Repository owner
        repo: Repository name
        max_results: Maximum releases to return (default: 20)
        session_name: GitHub session to use
    """
    data, error = _github.get_paginated(
        f"/repos/{owner}/{repo}/releases",
        session_name=session_name,
        max_items=max_results,
    )
    if error:
        return error

    if not data:
        return f"📦 No releases found in '{owner}/{repo}'."

    lines = [f"📦 Releases in '{owner}/{repo}' ({len(data)}):\n"]
    for release in data:
        pre = " [Pre-release]" if release.get("prerelease") else ""
        draft = " [Draft]" if release.get("draft") else ""
        assets = release.get("assets", [])
        asset_count = f" ({len(assets)} assets)" if assets else ""

        lines.append(
            f"  🏷️ {release.get('tag_name', '?')}: {release.get('name', '(no title)')}{pre}{draft}{asset_count}\n"
            f"     Published: {release.get('published_at', '?')[:10]} by @{release.get('author', {}).get('login', '?')}"
        )

    return "\n".join(lines)


@mcp.tool()
def github_get_release(
    owner: str,
    repo: str,
    release_id: int = 0,
    tag: str = "",
    session_name: str = "default",
) -> str:
    """
    Get details of a specific release.

    Args:
        owner: Repository owner
        repo: Repository name
        release_id: Release ID (use either this or tag)
        tag: Release tag name (e.g., 'v1.0.0')
        session_name: GitHub session to use
    """
    if tag:
        path = f"/repos/{owner}/{repo}/releases/tags/{tag}"
    elif release_id:
        path = f"/repos/{owner}/{repo}/releases/{release_id}"
    else:
        return "❌ Provide either release_id or tag."

    data, error = _github.get(path, session_name=session_name)
    if error:
        return error

    lines = [f"📦 Release: {data.get('name', data.get('tag_name', '?'))}\n"]
    lines.append(f"  • Tag: {data.get('tag_name', '?')}")
    lines.append(f"  • Target: {data.get('target_commitish', '?')}")
    lines.append(f"  • Draft: {data.get('draft', False)}")
    lines.append(f"  • Prerelease: {data.get('prerelease', False)}")
    lines.append(f"  • Published: {data.get('published_at', '?')[:10]}")
    lines.append(f"  • Author: @{data.get('author', {}).get('login', '?')}")
    lines.append(f"  • URL: {data.get('html_url', 'N/A')}")

    body = data.get("body")
    if body:
        lines.append(f"\n📝 Release Notes:\n{body[:800]}")

    assets = data.get("assets", [])
    if assets:
        lines.append(f"\n📎 Assets ({len(assets)}):")
        for asset in assets:
            size_mb = asset.get("size", 0) / (1024 * 1024)
            downloads = asset.get("download_count", 0)
            lines.append(f"  • {asset.get('name', '?')} ({size_mb:.1f} MB, {downloads} downloads)")

    return "\n".join(lines)


@mcp.tool()
def github_create_release(
    owner: str,
    repo: str,
    tag_name: str,
    name: str = "",
    body: str = "",
    target: str = "",
    draft: bool = False,
    prerelease: bool = False,
    generate_notes: bool = False,
    session_name: str = "default",
) -> str:
    """
    Create a new release with auto-generated or custom release notes.

    Args:
        owner: Repository owner
        repo: Repository name
        tag_name: Tag name for the release (e.g., 'v1.0.0')
        name: Release title (default: tag name)
        body: Release notes body (markdown)
        target: Branch or commit SHA (default: default branch)
        draft: Create as draft (default: False)
        prerelease: Mark as pre-release (default: False)
        generate_notes: Auto-generate release notes (default: False)
        session_name: GitHub session to use
    """
    payload = {
        "tag_name": tag_name,
        "name": name or tag_name,
        "draft": draft,
        "prerelease": prerelease,
        "generate_release_notes": generate_notes,
    }
    if body:
        payload["body"] = body
    if target:
        payload["target_commitish"] = target

    data, error = _github.post(f"/repos/{owner}/{repo}/releases", json_data=payload, session_name=session_name)
    if error:
        return error

    return (
        f"✅ Release '{data.get('name', tag_name)}' created!\n"
        f"  • Tag: {tag_name}\n"
        f"  • Draft: {draft}\n"
        f"  • Pre-release: {prerelease}\n"
        f"  • URL: {data.get('html_url', 'N/A')}"
    )


@mcp.tool()
def github_delete_release(
    owner: str,
    repo: str,
    release_id: int,
    session_name: str = "default",
) -> str:
    """
    Delete a release (the tag is NOT deleted).

    Args:
        owner: Repository owner
        repo: Repository name
        release_id: Release ID to delete
        session_name: GitHub session to use
    """
    _, error = _github.delete(f"/repos/{owner}/{repo}/releases/{release_id}", session_name=session_name)
    if error:
        return error

    return f"✅ Release #{release_id} deleted. The tag was kept."


@mcp.tool()
def github_get_latest_release(owner: str, repo: str, session_name: str = "default") -> str:
    """
    Get the latest published release for a repository.

    Args:
        owner: Repository owner
        repo: Repository name
        session_name: GitHub session to use
    """
    data, error = _github.get(f"/repos/{owner}/{repo}/releases/latest", session_name=session_name)
    if error:
        return error

    lines = [f"📦 Latest Release: {data.get('name', data.get('tag_name', '?'))}\n"]
    lines.append(f"  • Tag: {data.get('tag_name', '?')}")
    lines.append(f"  • Published: {data.get('published_at', '?')[:10]}")
    lines.append(f"  • URL: {data.get('html_url', 'N/A')}")

    assets = data.get("assets", [])
    if assets:
        lines.append(f"  • Assets: {len(assets)}")

    body = data.get("body")
    if body:
        lines.append(f"\n📝 Notes:\n{body[:500]}")

    return "\n".join(lines)


# ============================================================
# CATEGORY 9: Users & Organizations (5 tools)
# ============================================================

@mcp.tool()
def github_get_user(username: str = "", session_name: str = "default") -> str:
    """
    Get user profile information (authenticated user if username is empty).

    Args:
        username: GitHub username (empty = authenticated user)
        session_name: GitHub session to use
    """
    path = f"/users/{username}" if username else "/user"
    data, error = _github.get(path, session_name=session_name)
    if error:
        return error

    lines = [f"👤 @{data.get('login', '?')}\n"]
    name = data.get("name")
    if name:
        lines.append(f"  • Name: {name}")
    bio = data.get("bio")
    if bio:
        lines.append(f"  • Bio: {bio[:200]}")
    lines.append(f"  • Public Repos: {data.get('public_repos', 0)}")
    lines.append(f"  • Followers: {data.get('followers', 0)}")
    lines.append(f"  • Following: {data.get('following', 0)}")
    company = data.get("company")
    if company:
        lines.append(f"  • Company: {company}")
    location = data.get("location")
    if location:
        lines.append(f"  • Location: {location}")
    blog = data.get("blog")
    if blog:
        lines.append(f"  • Website: {blog}")
    lines.append(f"  • Profile: {data.get('html_url', 'N/A')}")
    lines.append(f"  • Joined: {data.get('created_at', '?')[:10]}")

    return "\n".join(lines)


@mcp.tool()
def github_list_user_repos(
    username: str,
    sort: str = "updated",
    max_results: int = 30,
    session_name: str = "default",
) -> str:
    """
    List public repositories for a specific user.

    Args:
        username: GitHub username
        sort: Sort by — 'updated', 'created', 'pushed', 'full_name' (default: updated)
        max_results: Maximum repos (default: 30)
        session_name: GitHub session to use
    """
    return github_list_repos(owner=username, sort=sort, max_results=max_results, session_name=session_name)


@mcp.tool()
def github_get_org(org: str, session_name: str = "default") -> str:
    """
    Get organization information.

    Args:
        org: Organization name
        session_name: GitHub session to use
    """
    data, error = _github.get(f"/orgs/{org}", session_name=session_name)
    if error:
        return error

    lines = [f"🏢 {data.get('login', org)}\n"]
    name = data.get("name")
    if name:
        lines.append(f"  • Name: {name}")
    desc = data.get("description")
    if desc:
        lines.append(f"  • Description: {desc[:200]}")
    lines.append(f"  • Public Repos: {data.get('public_repos', 0)}")
    lines.append(f"  • Members: {data.get('public_members_url', 'N/A').split('{')[0]}")
    location = data.get("location")
    if location:
        lines.append(f"  • Location: {location}")
    blog = data.get("blog")
    if blog:
        lines.append(f"  • Website: {blog}")
    lines.append(f"  • Profile: {data.get('html_url', 'N/A')}")
    lines.append(f"  • Created: {data.get('created_at', '?')[:10]}")

    return "\n".join(lines)


@mcp.tool()
def github_list_org_repos(
    org: str,
    repo_type: str = "all",
    sort: str = "updated",
    max_results: int = 30,
    session_name: str = "default",
) -> str:
    """
    List repositories for an organization.

    Args:
        org: Organization name
        repo_type: Filter — 'all', 'public', 'private', 'forks', 'sources' (default: all)
        sort: Sort by — 'updated', 'created', 'pushed', 'full_name'
        max_results: Maximum repos (default: 30)
        session_name: GitHub session to use
    """
    data, error = _github.get_paginated(
        f"/orgs/{org}/repos",
        params={"type": repo_type, "sort": sort},
        session_name=session_name,
        max_items=max_results,
    )
    if error:
        return error

    if not data:
        return f"📋 No repositories found in org '{org}'."

    lines = [f"📋 Repos in '{org}' ({len(data)}):\n"]
    for repo in data:
        visibility = "🔒" if repo.get("private") else "🌐"
        lang = repo.get("language", "")
        lang_str = f" [{lang}]" if lang else ""
        lines.append(f"  {visibility} {repo['name']}{lang_str}  ⭐ {repo.get('stargazers_count', 0)}")

    return "\n".join(lines)


@mcp.tool()
def github_list_org_members(
    org: str,
    max_results: int = 50,
    session_name: str = "default",
) -> str:
    """
    List members of an organization.

    Args:
        org: Organization name
        max_results: Maximum members to return (default: 50)
        session_name: GitHub session to use
    """
    data, error = _github.get_paginated(
        f"/orgs/{org}/members",
        session_name=session_name,
        max_items=max_results,
    )
    if error:
        return error

    if not data:
        return f"👥 No public members found in org '{org}'."

    lines = [f"👥 Members of '{org}' ({len(data)}):\n"]
    for member in data:
        lines.append(f"  • @{member.get('login', '?')}")

    return "\n".join(lines)


# ============================================================
# CATEGORY 10: Search (4 tools)
# ============================================================

@mcp.tool()
def github_search_repos(
    query: str,
    sort: str = "stars",
    max_results: int = 20,
    session_name: str = "default",
) -> str:
    """
    Search GitHub repositories by query.

    Supports GitHub search qualifiers: language:python, stars:>100, topic:mcp, etc.

    Args:
        query: Search query (e.g., 'mcp server language:python stars:>10')
        sort: Sort by — 'stars', 'forks', 'updated', 'help-wanted-issues' (default: stars)
        max_results: Maximum results (default: 20)
        session_name: GitHub session to use
    """
    data, error = _github.get(
        "/search/repositories",
        params={"q": query, "sort": sort, "per_page": min(max_results, 100)},
        session_name=session_name,
    )
    if error:
        return error

    total = data.get("total_count", 0)
    items = data.get("items", [])[:max_results]

    if not items:
        return f"🔍 No repositories found for '{query}'."

    lines = [f"🔍 Search Results: {total:,} repos found (showing {len(items)}):\n"]
    for repo in items:
        lang = repo.get("language", "")
        lang_str = f" [{lang}]" if lang else ""
        lines.append(
            f"  ⭐ {repo.get('stargazers_count', 0):,}  {repo['full_name']}{lang_str}\n"
            f"     {repo.get('description', '')[:120]}"
        )

    return "\n".join(lines)


@mcp.tool()
def github_search_code(
    query: str,
    max_results: int = 20,
    session_name: str = "default",
) -> str:
    """
    Search code across GitHub.

    Supports qualifiers: repo:owner/repo, path:src/, extension:py, language:python, etc.

    Args:
        query: Code search query (e.g., 'FastMCP language:python')
        max_results: Maximum results (default: 20)
        session_name: GitHub session to use
    """
    data, error = _github.get(
        "/search/code",
        params={"q": query, "per_page": min(max_results, 100)},
        session_name=session_name,
    )
    if error:
        return error

    total = data.get("total_count", 0)
    items = data.get("items", [])[:max_results]

    if not items:
        return f"🔍 No code found for '{query}'."

    lines = [f"🔍 Code Search: {total:,} results (showing {len(items)}):\n"]
    for item in items:
        repo = item.get("repository", {}).get("full_name", "?")
        lines.append(f"  📄 {repo}/{item.get('path', '?')}")

    return "\n".join(lines)


@mcp.tool()
def github_search_issues(
    query: str,
    sort: str = "created",
    max_results: int = 20,
    session_name: str = "default",
) -> str:
    """
    Search issues and pull requests across GitHub.

    Supports qualifiers: repo:owner/repo, is:issue, is:pr, state:open, label:bug, etc.

    Args:
        query: Search query (e.g., 'is:issue state:open label:bug repo:owner/repo')
        sort: Sort by — 'created', 'updated', 'comments', 'reactions' (default: created)
        max_results: Maximum results (default: 20)
        session_name: GitHub session to use
    """
    data, error = _github.get(
        "/search/issues",
        params={"q": query, "sort": sort, "per_page": min(max_results, 100)},
        session_name=session_name,
    )
    if error:
        return error

    total = data.get("total_count", 0)
    items = data.get("items", [])[:max_results]

    if not items:
        return f"🔍 No issues/PRs found for '{query}'."

    lines = [f"🔍 Issues/PRs: {total:,} results (showing {len(items)}):\n"]
    for item in items:
        is_pr = "pull_request" in item
        icon = "🔀" if is_pr else "🐛"
        state_icon = "🟢" if item.get("state") == "open" else "🔴"
        repo_url = item.get("repository_url", "")
        repo_name = "/".join(repo_url.split("/")[-2:]) if repo_url else "?"

        lines.append(
            f"  {icon}{state_icon} #{item.get('number', '?')}: {item.get('title', '?')}\n"
            f"     {repo_name} by @{item.get('user', {}).get('login', '?')}"
        )

    return "\n".join(lines)


@mcp.tool()
def github_search_users(
    query: str,
    sort: str = "followers",
    max_results: int = 20,
    session_name: str = "default",
) -> str:
    """
    Search GitHub users and organizations.

    Supports qualifiers: type:user, type:org, location:india, language:python, etc.

    Args:
        query: Search query (e.g., 'type:org language:python')
        sort: Sort by — 'followers', 'repositories', 'joined' (default: followers)
        max_results: Maximum results (default: 20)
        session_name: GitHub session to use
    """
    data, error = _github.get(
        "/search/users",
        params={"q": query, "sort": sort, "per_page": min(max_results, 100)},
        session_name=session_name,
    )
    if error:
        return error

    total = data.get("total_count", 0)
    items = data.get("items", [])[:max_results]

    if not items:
        return f"🔍 No users found for '{query}'."

    lines = [f"🔍 Users: {total:,} results (showing {len(items)}):\n"]
    for user in items:
        user_type = "🏢" if user.get("type") == "Organization" else "👤"
        lines.append(f"  {user_type} @{user.get('login', '?')} — {user.get('html_url', '')}")

    return "\n".join(lines)


# ============================================================
# CATEGORY 11: Gists (4 tools)
# ============================================================

@mcp.tool()
def github_list_gists(
    username: str = "",
    max_results: int = 20,
    session_name: str = "default",
) -> str:
    """
    List gists for the authenticated user or a specific user.

    Args:
        username: GitHub username (empty = authenticated user)
        max_results: Maximum gists to return (default: 20)
        session_name: GitHub session to use
    """
    path = f"/users/{username}/gists" if username else "/gists"
    data, error = _github.get_paginated(path, session_name=session_name, max_items=max_results)
    if error:
        return error

    if not data:
        return "📝 No gists found."

    lines = [f"📝 Gists ({len(data)}):\n"]
    for gist in data:
        visibility = "🌐" if gist.get("public") else "🔒"
        files = list(gist.get("files", {}).keys())
        file_list = ", ".join(files[:3])
        if len(files) > 3:
            file_list += f" (+{len(files) - 3} more)"

        desc = gist.get("description") or "(no description)"
        lines.append(
            f"  {visibility} {gist.get('id', '?')[:8]}...: {desc[:80]}\n"
            f"     Files: {file_list} | {gist.get('created_at', '?')[:10]}"
        )

    return "\n".join(lines)


@mcp.tool()
def github_create_gist(
    files: str,
    description: str = "",
    public: bool = False,
    session_name: str = "default",
) -> str:
    """
    Create a new gist with one or more files.

    Args:
        files: JSON string mapping filenames to content, e.g. '{"hello.py": "print(\\\"hello\\\")", "readme.md": "# Hello"}'
        description: Gist description
        public: Make gist public (default: False = secret)
        session_name: GitHub session to use
    """
    try:
        file_dict = json.loads(files)
    except json.JSONDecodeError:
        return f"❌ Invalid JSON for files parameter. Expected format: {{\"filename.ext\": \"content\"}}"

    gist_files = {}
    for name, content in file_dict.items():
        gist_files[name] = {"content": content}

    payload = {
        "description": description,
        "public": public,
        "files": gist_files,
    }

    data, error = _github.post("/gists", json_data=payload, session_name=session_name)
    if error:
        return error

    visibility = "🌐 Public" if public else "🔒 Secret"
    return (
        f"✅ Gist created!\n"
        f"  • ID: {data.get('id', '?')}\n"
        f"  • Visibility: {visibility}\n"
        f"  • Files: {', '.join(file_dict.keys())}\n"
        f"  • URL: {data.get('html_url', 'N/A')}"
    )


@mcp.tool()
def github_get_gist(gist_id: str, session_name: str = "default") -> str:
    """
    Get gist content and details.

    Args:
        gist_id: Gist ID
        session_name: GitHub session to use
    """
    data, error = _github.get(f"/gists/{gist_id}", session_name=session_name)
    if error:
        return error

    visibility = "🌐 Public" if data.get("public") else "🔒 Secret"
    lines = [f"📝 Gist: {data.get('id', gist_id)}\n"]
    lines.append(f"  • Description: {data.get('description') or '(none)'}")
    lines.append(f"  • Visibility: {visibility}")
    lines.append(f"  • Created: {data.get('created_at', '?')[:10]}")
    lines.append(f"  • URL: {data.get('html_url', 'N/A')}")

    files = data.get("files", {})
    for name, file_info in files.items():
        content = file_info.get("content", "")
        lang = file_info.get("language", "")
        size = file_info.get("size", 0)
        lines.append(f"\n📄 {name} ({lang}, {size} bytes):")
        lines.append(content[:2000])
        if len(content) > 2000:
            lines.append(f"\n... [TRUNCATED — {len(content)} bytes total]")

    return "\n".join(lines)


@mcp.tool()
def github_delete_gist(gist_id: str, session_name: str = "default") -> str:
    """
    Delete a gist permanently.

    Args:
        gist_id: Gist ID to delete
        session_name: GitHub session to use
    """
    _, error = _github.delete(f"/gists/{gist_id}", session_name=session_name)
    if error:
        return error

    return f"✅ Gist '{gist_id}' deleted."


# ============================================================
# CATEGORY 12: Webhooks & Notifications (2 tools)
# ============================================================

@mcp.tool()
def github_list_notifications(
    all_notifications: bool = False,
    participating: bool = False,
    max_results: int = 30,
    session_name: str = "default",
) -> str:
    """
    List GitHub notifications for the authenticated user.

    Args:
        all_notifications: Show all notifications including read ones (default: False = unread only)
        participating: Only show notifications where user is participating (default: False)
        max_results: Maximum notifications to return (default: 30)
        session_name: GitHub session to use
    """
    params = {
        "all": str(all_notifications).lower(),
        "participating": str(participating).lower(),
    }

    data, error = _github.get_paginated(
        "/notifications",
        params=params,
        session_name=session_name,
        max_items=max_results,
    )
    if error:
        return error

    if not data:
        return "🔔 No notifications." + (" (showing all)" if all_notifications else " (unread only)")

    lines = [f"🔔 Notifications ({len(data)}):\n"]
    for notif in data:
        unread = "🔴" if notif.get("unread") else "⚪"
        reason = notif.get("reason", "unknown")
        subject = notif.get("subject", {})
        repo = notif.get("repository", {}).get("full_name", "?")
        subject_type = subject.get("type", "?")

        type_icon = {"Issue": "🐛", "PullRequest": "🔀", "Release": "📦", "Discussion": "💬"}.get(subject_type, "📌")

        lines.append(
            f"  {unread}{type_icon} [{repo}] {subject.get('title', '?')}\n"
            f"     Reason: {reason} | Updated: {notif.get('updated_at', '?')[:10]}"
        )

    return "\n".join(lines)


@mcp.tool()
def github_mark_notifications_read(
    last_read_at: str = "",
    session_name: str = "default",
) -> str:
    """
    Mark all notifications as read.

    Args:
        last_read_at: ISO 8601 timestamp — mark notifications before this as read (empty = all)
        session_name: GitHub session to use
    """
    payload = {}
    if last_read_at:
        payload["last_read_at"] = last_read_at

    _, error = _github.put("/notifications", json_data=payload, session_name=session_name)
    if error:
        return error

    return "✅ All notifications marked as read."


# ============================================================
# Entry Point
# ============================================================

if __name__ == "__main__":
    mcp.run(transport="stdio")
