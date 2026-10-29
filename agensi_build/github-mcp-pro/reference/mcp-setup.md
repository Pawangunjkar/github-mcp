# MCP client setup

Run the pre-flight check before the first session:

```bash
# from a shell where GITHUB_TOKEN is already exported
python scripts/verify_env.py
```

The server command is `uvx github-mcp`. Put the token in the client environment. Do not paste a real token into these files.

`session_name` defaults to `default`. A second PAT uses another session name with `github_connect` or `github_save_credentials`.

## Cursor

`.cursor/mcp.json`

```json
{
  "mcpServers": {
    "github": {
      "command": "uvx",
      "args": ["github-mcp"],
      "env": {
        "GITHUB_TOKEN": "${GITHUB_TOKEN}",
        "GITHUB_API_URL": "https://api.github.com",
        "GITHUB_PROTOCOL": "ssh"
      }
    }
  }
}
```

## Claude Code

Project `.mcp.json` or the user MCP config:

```json
{
  "mcpServers": {
    "github": {
      "command": "uvx",
      "args": ["github-mcp"],
      "env": {
        "GITHUB_TOKEN": "${GITHUB_TOKEN}",
        "GITHUB_API_URL": "https://api.github.com",
        "GITHUB_PROTOCOL": "ssh"
      }
    }
  }
}
```

## VS Code

`.vscode/mcp.json`

```json
{
  "servers": {
    "github": {
      "type": "stdio",
      "command": "uvx",
      "args": ["github-mcp"],
      "env": {
        "GITHUB_TOKEN": "${GITHUB_TOKEN}",
        "GITHUB_API_URL": "https://api.github.com",
        "GITHUB_PROTOCOL": "ssh"
      }
    }
  }
}
```

Classic PAT scopes used by the pipeline suite: `repo` and `workflow`. Fine-grained tokens need Contents (read/write when committing a workflow), Actions (read/write), and secret metadata read. Secret values are never returned by `github_check_ci_secrets_and_variables`.
