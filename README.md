# 🐙 GitHub MCP Server

> **MCP server for GitHub operations — 73 tools for repos, PRs, issues, actions, releases, search, and more.**

A comprehensive [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server that exposes the full GitHub REST API as AI-ready tools. Connect your AI assistant (Cursor, Claude Desktop, or any MCP client) to manage GitHub through natural language.

Author: **Pawan Gunjkar** (pawangunjkar@gmail.com)

---

## 📥 Install

### Option 1: PyPI / uvx (Recommended)

No clone required — install and run directly:

```bash
uvx github-mcp
```

**Cursor / Claude Desktop** — add to `.cursor/mcp.json` or `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "github": {
      "command": "uvx",
      "args": ["github-mcp"],
      "env": {
        "GITHUB_TOKEN": "ghp_your-token-here",
        "GITHUB_PROTOCOL": "ssh"
      }
    }
  }
}
```

### Option 2: Smithery

```bash
npx -y @smithery/cli install github-mcp --client cursor
```

Or browse [smithery.ai](https://smithery.ai) and search for **github-mcp**.

### Option 3: Clone from GitHub

```bash
git clone https://github.com/Pawangunjkar/github-mcp.git
cd github-mcp
uv sync
uv run server.py
```

> See [PUBLISHING.md](PUBLISHING.md) for PyPI, Smithery, and directory submission steps.

---

## ✨ Features

- 🔌 **73 tools** across **12 categories** — full GitHub API coverage
- 🔐 **PAT authentication** — Personal Access Token with Bearer auth
- 🔄 **SSH + HTTPS** — supports both clone/push protocols
- 📄 **Auto-pagination** — transparently handles paginated API responses
- ⚡ **Rate limit aware** — tracks and warns on low rate limits
- 💾 **Credential caching** — auto-connect from env vars or cached credentials
- 🏢 **GitHub Enterprise** — configurable API URL for GHE servers
- 🎯 **Zero configuration** — just set env vars and run

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+**
- **[uv](https://docs.astral.sh/uv/)** package manager
- **GitHub account** with a Personal Access Token

### 1. Clone & Install

```bash
cd github-mcp
uv sync
```

### 2. Configure Credentials

**Option A: Environment Variables (Recommended)**

```bash
cp .env.example .env

# Set your GitHub PAT
GITHUB_TOKEN=ghp_your-personal-access-token
GITHUB_PROTOCOL=ssh    # or 'https'
```

**Option B: Connect via chat**

```
github_connect(token="ghp_xxxxxxxxxxxx", protocol="ssh")
```

### 3. Generate a Personal Access Token

1. Go to **GitHub** → **Settings** → **Developer settings** → **Personal access tokens**
2. Click **"Generate new token"** (classic)
3. Select scopes: `repo`, `workflow`, `read:org`, `gist`, `notifications`, `delete_repo`
4. Click **Generate** and copy the token

### 4. Run the Server

```bash
# For Cursor / Claude Desktop (stdio transport)
uv run server.py

# For testing with MCP Inspector
uv run mcp dev server.py
```

---

## 🛠️ Tool Reference (73 Tools)

### Category 1: Connection & Authentication (4 tools)

| Tool | Description |
|------|-------------|
| `github_connect` | Connect with Personal Access Token |
| `github_disconnect` | Disconnect current session |
| `github_status` | Show connection status, user info, rate limits |
| `github_save_credentials` | Save credentials to disk cache |

### Category 2: Repository Management (10 tools)

| Tool | Description |
|------|-------------|
| `github_list_repos` | List repos for authenticated user or any user/org |
| `github_get_repo` | Get detailed repo info (stars, forks, languages) |
| `github_create_repo` | Create a new repository |
| `github_delete_repo` | Delete a repository permanently |
| `github_fork_repo` | Fork a repository |
| `github_update_repo` | Update repo settings (description, visibility) |
| `github_list_topics` | Get repo topics/tags |
| `github_update_topics` | Set repo topics/tags |
| `github_list_languages` | Get language breakdown |
| `github_list_contributors` | List repo contributors |

### Category 3: Branch & Tag Management (8 tools)

| Tool | Description |
|------|-------------|
| `github_list_branches` | List all branches |
| `github_get_branch` | Get branch details and protection status |
| `github_create_branch` | Create a new branch from a ref |
| `github_delete_branch` | Delete a branch |
| `github_protect_branch` | Set branch protection rules |
| `github_list_tags` | List all tags |
| `github_create_tag` | Create a lightweight or annotated tag |
| `github_compare_branches` | Compare two branches (ahead/behind, diff) |

### Category 4: File & Content Operations (6 tools)

| Tool | Description |
|------|-------------|
| `github_get_file` | Get file content (auto-decodes base64) |
| `github_create_file` | Create a new file via commit |
| `github_update_file` | Update a file via commit |
| `github_delete_file` | Delete a file via commit |
| `github_get_tree` | Get directory tree listing |
| `github_get_clone_url` | Get SSH or HTTPS clone URL |

### Category 5: Pull Requests (10 tools)

| Tool | Description |
|------|-------------|
| `github_list_prs` | List pull requests (open, closed, all) |
| `github_get_pr` | Get PR details (diff stats, reviews, status) |
| `github_create_pr` | Create a new pull request |
| `github_update_pr` | Update PR title, body, base branch |
| `github_merge_pr` | Merge a PR (merge, squash, or rebase) |
| `github_close_pr` | Close a PR without merging |
| `github_list_pr_files` | List files changed in a PR |
| `github_list_pr_reviews` | List reviews on a PR |
| `github_request_reviewers` | Request reviewers for a PR |
| `github_create_pr_comment` | Add a comment on a PR |

### Category 6: Issues (8 tools)

| Tool | Description |
|------|-------------|
| `github_list_issues` | List issues with filters (state, labels, assignee) |
| `github_get_issue` | Get issue details |
| `github_create_issue` | Create a new issue |
| `github_update_issue` | Update issue title, body, labels, assignees |
| `github_close_issue` | Close an issue |
| `github_create_issue_comment` | Add a comment on an issue |
| `github_list_issue_comments` | List comments on an issue |
| `github_add_labels` | Add labels to an issue/PR |

### Category 7: Actions & Workflows (7 tools)

| Tool | Description |
|------|-------------|
| `github_list_workflows` | List all workflows in a repo |
| `github_trigger_workflow` | Trigger a workflow dispatch event |
| `github_list_workflow_runs` | List workflow runs |
| `github_get_workflow_run` | Get details of a specific run |
| `github_get_run_logs` | Get workflow run logs |
| `github_cancel_workflow_run` | Cancel a running workflow |
| `github_rerun_workflow` | Re-run a workflow |

### Category 8: Releases (5 tools)

| Tool | Description |
|------|-------------|
| `github_list_releases` | List all releases |
| `github_get_release` | Get release details and assets |
| `github_create_release` | Create a release (with auto-generated notes) |
| `github_delete_release` | Delete a release |
| `github_get_latest_release` | Get the latest release |

### Category 9: Users & Organizations (5 tools)

| Tool | Description |
|------|-------------|
| `github_get_user` | Get user profile info |
| `github_list_user_repos` | List repos for a specific user |
| `github_get_org` | Get organization info |
| `github_list_org_repos` | List repos for an organization |
| `github_list_org_members` | List organization members |

### Category 10: Search (4 tools)

| Tool | Description |
|------|-------------|
| `github_search_repos` | Search repositories (with qualifiers) |
| `github_search_code` | Search code across GitHub |
| `github_search_issues` | Search issues and PRs |
| `github_search_users` | Search users and organizations |

### Category 11: Gists (4 tools)

| Tool | Description |
|------|-------------|
| `github_list_gists` | List gists |
| `github_create_gist` | Create a new gist |
| `github_get_gist` | Get gist content and details |
| `github_delete_gist` | Delete a gist |

### Category 12: Webhooks & Notifications (2 tools)

| Tool | Description |
|------|-------------|
| `github_list_notifications` | List unread notifications |
| `github_mark_notifications_read` | Mark notifications as read |

---

## 🔗 SSH vs HTTPS Support

The server supports both protocols. Set your preference via:

- **Environment variable**: `GITHUB_PROTOCOL=ssh` (or `https`)
- **Connection parameter**: `github_connect(token="...", protocol="ssh")`

| Feature | SSH | HTTPS |
|---------|-----|-------|
| Clone URL | `git@github.com:user/repo.git` | `https://github.com/user/repo.git` |
| Auth | SSH key on machine | PAT or credential helper |
| Default | ✅ Preferred | Fallback |

Tools like `github_create_repo`, `github_fork_repo`, and `github_get_clone_url` return URLs in both formats.

---

## ⚙️ Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GITHUB_TOKEN` | Yes | — | Personal Access Token |
| `GITHUB_API_URL` | No | `https://api.github.com` | API URL (change for GitHub Enterprise) |
| `GITHUB_PROTOCOL` | No | `ssh` | Preferred clone protocol (`ssh` or `https`) |
| `GITHUB_TIMEOUT` | No | `30` | Request timeout in seconds |
| `GITHUB_MCP_CACHE_DIR` | No | `~/.github-mcp-cache` | Credential cache directory |

### Cursor Integration

Add to `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "github": {
      "command": "uvx",
      "args": ["github-mcp"],
      "env": {
        "GITHUB_TOKEN": "ghp_your-token-here",
        "GITHUB_PROTOCOL": "ssh"
      }
    }
  }
}
```

**Alternative (from source):**

```json
{
  "mcpServers": {
    "github": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/github-mcp", "server.py"],
      "env": {
        "GITHUB_TOKEN": "ghp_your-token-here",
        "GITHUB_PROTOCOL": "ssh"
      }
    }
  }
}
```

### Claude Desktop Integration

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "github": {
      "command": "uvx",
      "args": ["github-mcp"],
      "env": {
        "GITHUB_TOKEN": "ghp_your-token-here",
        "GITHUB_PROTOCOL": "ssh"
      }
    }
  }
}
```

---

## 💡 Example Usage

### Repository Management

```
"List all my repos sorted by recent activity"
→ github_list_repos(sort="updated")

"Show me the details of the linux-ssh-mcp repo"
→ github_get_repo(owner="Pawangunjkar", repo="linux-ssh-mcp")

"Fork the fastapi repo to my account"
→ github_fork_repo(owner="tiangolo", repo="fastapi")
```

### Pull Requests & Code Review

```
"Create a PR from feature-branch to main"
→ github_create_pr(owner="me", repo="my-app", title="Add login feature", head="feature-branch", base="main")

"Show me the files changed in PR #42"
→ github_list_pr_files(owner="me", repo="my-app", pr_number=42)

"Merge PR #42 with squash"
→ github_merge_pr(owner="me", repo="my-app", pr_number=42, merge_method="squash")
```

### GitHub Actions

```
"Trigger the deploy workflow on main branch"
→ github_trigger_workflow(owner="me", repo="my-app", workflow_id="deploy.yml", ref="main")

"Show recent workflow runs"
→ github_list_workflow_runs(owner="me", repo="my-app")

"Cancel the running workflow"
→ github_cancel_workflow_run(owner="me", repo="my-app", run_id=12345)
```

### Search

```
"Find popular Python MCP servers on GitHub"
→ github_search_repos(query="mcp server language:python stars:>10")

"Search for FastMCP usage in code"
→ github_search_code(query="FastMCP language:python")
```

---

## 📁 Project Structure

```
github-mcp/
├── server.py              # Main MCP server — 73 tool definitions
├── github_client.py       # GitHub REST API client (HTTP, auth, pagination)
├── credential_store.py    # Credential caching (env vars, memory, file)
├── pyproject.toml         # Project metadata & dependencies
├── .env.example           # Example environment variables
├── .gitignore             # Python gitignore
├── LICENSE                # MIT license
└── README.md              # This file
```

---

## 🔒 Security Notes

- **PAT tokens** are stored in `~/.github-mcp-cache/credentials.json` with restrictive file permissions (600)
- **Never commit** `.env` files or tokens to version control
- Use **fine-grained tokens** when possible for minimum required access
- The server tracks **rate limits** and warns when running low

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
