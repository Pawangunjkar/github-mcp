#!/usr/bin/env python3
"""Pre-flight check for pawangunjkar-github-mcp. Standard library only."""

import os
import sys

_PLACEHOLDERS = {
    "",
    "changeme",
    "your-token-here",
    "ghp_your-token-here",
    "github_pat_your-token-here",
}


def main() -> int:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token.lower() in _PLACEHOLDERS or token.startswith("ghp_your"):
        print("GITHUB_TOKEN is missing or still a placeholder.", file=sys.stderr)
        return 1
    if len(token) < 20:
        print("GITHUB_TOKEN is too short to be a GitHub token.", file=sys.stderr)
        return 1
    if any(ch.isspace() for ch in token):
        print("GITHUB_TOKEN must not contain whitespace.", file=sys.stderr)
        return 1

    api = os.environ.get("GITHUB_API_URL", "https://api.github.com").strip() or "https://api.github.com"
    if not api.startswith("https://"):
        print("GITHUB_API_URL must be an https URL.", file=sys.stderr)
        return 1

    protocol = os.environ.get("GITHUB_PROTOCOL", "ssh").strip().lower() or "ssh"
    if protocol not in ("ssh", "https"):
        print("GITHUB_PROTOCOL must be ssh or https.", file=sys.stderr)
        return 1

    print("GitHub MCP pre-flight OK.")
    print(f"API: {api}")
    print(f"Protocol: {protocol}")
    print(f"Token: set ({len(token)} characters, value hidden)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
