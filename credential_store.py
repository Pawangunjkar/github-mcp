"""
Credential Store for GitHub MCP Server.

Author: Pawan Gunjkar (pawangunjkar@gamil.com)

Manages GitHub connection credentials with a layered lookup strategy:
1. Environment variables (GITHUB_TOKEN, GITHUB_API_URL, GITHUB_PROTOCOL)
2. In-memory cache (current server session)
3. Local file cache (~/.github-mcp-cache/credentials.json)
4. If none found → returns None (server will prompt user)
"""

import json
import os
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional


@dataclass
class GitHubCredentials:
    """GitHub connection credentials."""
    token: str
    api_url: str = "https://api.github.com"
    protocol: str = "ssh"  # 'ssh' or 'https'
    timeout: int = 30

    def to_dict(self) -> dict:
        """Convert to dictionary (excludes None values)."""
        return {k: v for k, v in asdict(self).items() if v is not None}

    @classmethod
    def from_dict(cls, data: dict) -> "GitHubCredentials":
        """Create from dictionary."""
        return cls(
            token=data["token"],
            api_url=data.get("api_url", "https://api.github.com").rstrip("/"),
            protocol=data.get("protocol", "ssh"),
            timeout=int(data.get("timeout", 30)),
        )

    def masked_dict(self) -> dict:
        """Return dict with token masked (for display)."""
        d = self.to_dict()
        if "token" in d and d["token"]:
            token = d["token"]
            d["token"] = token[:4] + "****" + token[-4:] if len(token) > 8 else "****"
        return d


class CredentialStore:
    """
    Multi-layer credential store for GitHub connections.

    Credentials are cached in memory and optionally persisted to a JSON file.
    """

    def __init__(self, cache_dir: Optional[str] = None):
        """Initialize the credential store."""
        self._memory_cache: dict[str, GitHubCredentials] = {}

        # Determine cache directory
        if cache_dir:
            self._cache_dir = Path(cache_dir)
        else:
            env_cache_dir = os.environ.get("GITHUB_MCP_CACHE_DIR")
            if env_cache_dir:
                self._cache_dir = Path(env_cache_dir)
            else:
                self._cache_dir = Path.home() / ".github-mcp-cache"

        self._cache_file = self._cache_dir / "credentials.json"
        self._ensure_cache_dir()
        self._load_file_cache()

    def _ensure_cache_dir(self):
        """Create cache directory if it doesn't exist."""
        try:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            if sys.platform != "win32":
                os.chmod(self._cache_dir, 0o700)
        except OSError as e:
            print(f"Warning: Could not create cache directory: {e}", file=sys.stderr)

    def _load_file_cache(self):
        """Load credentials from the JSON cache file."""
        if self._cache_file.exists():
            try:
                with open(self._cache_file, "r") as f:
                    data = json.load(f)
                for name, cred_data in data.items():
                    if name not in self._memory_cache:
                        self._memory_cache[name] = GitHubCredentials.from_dict(cred_data)
                print(f"Loaded {len(data)} cached credential(s) from {self._cache_file}", file=sys.stderr)
            except (json.JSONDecodeError, KeyError, OSError) as e:
                print(f"Warning: Could not load credential cache: {e}", file=sys.stderr)

    def _save_file_cache(self):
        """Save all credentials to the JSON cache file."""
        try:
            data = {name: cred.to_dict() for name, cred in self._memory_cache.items()}
            with open(self._cache_file, "w") as f:
                json.dump(data, f, indent=2)
            if sys.platform != "win32":
                os.chmod(self._cache_file, 0o600)
        except OSError as e:
            print(f"Warning: Could not save credential cache: {e}", file=sys.stderr)

    def get_from_env(self) -> Optional[GitHubCredentials]:
        """
        Try to get credentials from environment variables.

        Looks for: GITHUB_TOKEN, GITHUB_API_URL, GITHUB_PROTOCOL
        """
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            return None

        return GitHubCredentials(
            token=token,
            api_url=os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/"),
            protocol=os.environ.get("GITHUB_PROTOCOL", "ssh").lower(),
            timeout=int(os.environ.get("GITHUB_TIMEOUT", "30")),
        )

    def get_credentials(self, session_name: str = "default") -> Optional[GitHubCredentials]:
        """
        Get credentials using layered lookup.

        Order: env vars (for 'default') → memory cache → file cache → None
        """
        if session_name == "default":
            env_creds = self.get_from_env()
            if env_creds:
                return env_creds

        if session_name in self._memory_cache:
            return self._memory_cache[session_name]

        return None

    def save_credentials(
        self,
        session_name: str,
        token: str,
        api_url: str = "https://api.github.com",
        protocol: str = "ssh",
        timeout: int = 30,
    ) -> GitHubCredentials:
        """Save credentials to memory and file cache."""
        creds = GitHubCredentials(
            token=token,
            api_url=api_url.rstrip("/"),
            protocol=protocol.lower(),
            timeout=timeout,
        )
        self._memory_cache[session_name] = creds
        self._save_file_cache()
        return creds

    def delete_credentials(self, session_name: str) -> bool:
        """Delete credentials for a session from all caches."""
        if session_name in self._memory_cache:
            del self._memory_cache[session_name]
            self._save_file_cache()
            return True
        return False

    def list_sessions(self) -> dict[str, dict]:
        """List all cached session credentials (with tokens masked)."""
        result = {}

        env_creds = self.get_from_env()
        if env_creds and "default" not in self._memory_cache:
            result["default (env)"] = env_creds.masked_dict()

        for name, cred in self._memory_cache.items():
            result[name] = cred.masked_dict()

        return result

    def clear_all(self):
        """Clear all cached credentials."""
        self._memory_cache.clear()
        if self._cache_file.exists():
            try:
                self._cache_file.unlink()
            except OSError:
                pass
