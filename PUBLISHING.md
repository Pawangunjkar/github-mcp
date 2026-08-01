# Publishing Guide — GitHub MCP

This guide walks you through publishing **github-mcp** so developers and AI agents can discover and install it.

## Checklist

- [x] `README.md` with install instructions
- [x] `pyproject.toml` with metadata and console script
- [x] `smithery.yaml` for Smithery registry
- [x] `LICENSE` (MIT)
- [ ] Publish to PyPI
- [ ] Submit to Smithery
- [ ] Submit to Glama & Pulse MCP directories
- [ ] Set GitHub topics

---

## 1. Publish to PyPI

```bash
pip install build twine
cd github-mcp
python -m build
twine upload dist/*
```

### MCP config after PyPI publish

```json
{
  "mcpServers": {
    "github": {
      "command": "uvx",
      "args": ["pawangunjkar-github-mcp"],
      "env": {
        "GITHUB_TOKEN": "ghp_your-token-here",
        "GITHUB_PROTOCOL": "ssh"
      }
    }
  }
}
```

---

## 2. Submit to Smithery

1. Go to [https://smithery.ai](https://smithery.ai) → sign in with GitHub
2. Publish `Pawangunjkar/github-mcp` repository
3. Smithery reads `smithery.yaml` (requires `GITHUB_TOKEN`)

---

## 3. List on MCP Directories

| Directory | URL |
|-----------|-----|
| **Glama** | https://glama.ai/mcp/servers |
| **Pulse MCP** | https://www.pulsemcp.com |

Submit: `https://github.com/Pawangunjkar/github-mcp`

---

## 4. GitHub Topics

```
mcp, model-context-protocol, mcp-server, github, git, pull-requests, ci-cd, devops, python
```

```bash
gh repo edit Pawangunjkar/github-mcp \
  --add-topic mcp,model-context-protocol,mcp-server,github,git,devops,python
```

---

## Support

- **Issues:** https://github.com/Pawangunjkar/github-mcp/issues
- **Author:** Pawan Gunjkar — pawangunjkar@gmail.com
