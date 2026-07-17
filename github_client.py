"""
GitHub REST API Client for GitHub MCP Server.

Author: Pawan Gunjkar (pawangunjkar@gamil.com)

Handles all HTTP communication with the GitHub API:
- Bearer token authentication with Personal Access Tokens
- Automatic pagination (follows Link headers)
- Rate limit tracking and warnings
- GET/POST/PUT/PATCH/DELETE helpers
- SSH vs HTTPS URL formatting
- GitHub Enterprise Server support
"""

import sys
import time
from typing import Optional, Any

import httpx

from credential_store import CredentialStore, GitHubCredentials


# Constants
DEFAULT_TIMEOUT = 30
MAX_OUTPUT_SIZE = 50 * 1024  # 50KB
DEFAULT_PER_PAGE = 30
MAX_PER_PAGE = 100


class GitHubClient:
    """
    GitHub REST API client.

    Manages HTTP sessions with the GitHub API, handles authentication,
    pagination, rate limiting, and provides typed API methods.
    """

    def __init__(self, credential_store: Optional[CredentialStore] = None):
        self._credentials = credential_store or CredentialStore()
        self._sessions: dict[str, _GitHubSession] = {}

    @property
    def credential_store(self) -> CredentialStore:
        return self._credentials

    def connect(
        self,
        session_name: str = "default",
        token: Optional[str] = None,
        api_url: str = "https://api.github.com",
        protocol: str = "ssh",
        timeout: int = DEFAULT_TIMEOUT,
        save_credentials: bool = True,
    ) -> str:
        """
        Connect to GitHub API and create a named session.

        Returns a status message.
        """
        # Disconnect existing session if present
        if session_name in self._sessions:
            self.disconnect(session_name)

        # Try credential store if no token
        if not token:
            creds = self._credentials.get_credentials(session_name)
            if creds:
                token = creds.token
                api_url = creds.api_url
                protocol = creds.protocol
                timeout = creds.timeout
            else:
                return (
                    f"❌ No credentials found for session '{session_name}'.\n\n"
                    f"Please provide a GitHub Personal Access Token:\n"
                    f"  • token: Your GitHub PAT (generate at https://github.com/settings/tokens)\n"
                    f"  • api_url: API URL (default: https://api.github.com)\n"
                    f"  • protocol: Clone protocol — 'ssh' or 'https' (default: ssh)\n\n"
                    f"Example: github_connect(token='ghp_xxxxxxxxxxxx')\n\n"
                    f"💡 To generate a PAT:\n"
                    f"   1. Go to GitHub → Settings → Developer settings → Personal access tokens\n"
                    f"   2. Click 'Generate new token'\n"
                    f"   3. Select scopes: repo, workflow, read:org, gist, notifications\n"
                    f"   4. Copy the token value"
                )

        if not token:
            return "❌ GitHub token is required."

        api_url = api_url.rstrip("/")
        protocol = protocol.lower()
        if protocol not in ("ssh", "https"):
            protocol = "ssh"

        try:
            # Create HTTP client
            client = httpx.Client(
                base_url=api_url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                timeout=timeout,
                follow_redirects=True,
            )

            # Validate connection by fetching authenticated user
            response = client.get("/user")
            response.raise_for_status()
            user_data = response.json()

            # Extract rate limit info
            rate_limit = response.headers.get("X-RateLimit-Limit", "?")
            rate_remaining = response.headers.get("X-RateLimit-Remaining", "?")

            # Create session
            session = _GitHubSession(
                name=session_name,
                api_url=api_url,
                protocol=protocol,
                client=client,
                username=user_data.get("login", "unknown"),
                user_data=user_data,
            )
            self._sessions[session_name] = session

            # Cache credentials
            if save_credentials:
                self._credentials.save_credentials(
                    session_name=session_name,
                    token=token,
                    api_url=api_url,
                    protocol=protocol,
                    timeout=timeout,
                )

            print(f"Connected to GitHub as {session.username} (session: {session_name})", file=sys.stderr)

            return (
                f"✅ Connected to GitHub successfully!\n"
                f"  • Session: {session_name}\n"
                f"  • User: {user_data.get('login')} ({user_data.get('name', 'N/A')})\n"
                f"  • API: {api_url}\n"
                f"  • Protocol: {protocol.upper()}\n"
                f"  • Public Repos: {user_data.get('public_repos', 0)}\n"
                f"  • Private Repos: {user_data.get('total_private_repos', 0)}\n"
                f"  • Rate Limit: {rate_remaining}/{rate_limit}\n"
                f"  • Credentials cached for future use"
            )

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                return f"❌ Authentication failed. Check your Personal Access Token."
            elif e.response.status_code == 403:
                return f"❌ Access forbidden. Your token may lack required scopes."
            return f"❌ HTTP error: {e.response.status_code} {e.response.reason_phrase}"
        except httpx.ConnectError:
            return f"❌ Connection failed to {api_url}. Check the URL and your network."
        except httpx.TimeoutException:
            return f"❌ Connection timed out to {api_url}."
        except Exception as e:
            return f"❌ Failed to connect: {str(e)}"

    def disconnect(self, session_name: str = "default") -> str:
        """Disconnect a specific session."""
        if session_name not in self._sessions:
            return f"⚠️ No active session named '{session_name}'."

        session = self._sessions.pop(session_name)
        try:
            session.client.close()
        except Exception:
            pass

        return f"✅ Disconnected session '{session_name}' (user: {session.username})"

    def disconnect_all(self) -> str:
        """Disconnect all sessions."""
        if not self._sessions:
            return "⚠️ No active sessions to disconnect."
        names = list(self._sessions.keys())
        for name in names:
            self.disconnect(name)
        return f"✅ Disconnected {len(names)} session(s): {', '.join(names)}"

    def _get_session(self, session_name: str = "default") -> tuple[Optional["_GitHubSession"], Optional[str]]:
        """Get a session by name, auto-connecting if credentials are cached."""
        if session_name not in self._sessions:
            creds = self._credentials.get_credentials(session_name)
            if creds:
                result = self.connect(
                    session_name=session_name,
                    token=creds.token,
                    api_url=creds.api_url,
                    protocol=creds.protocol,
                    timeout=creds.timeout,
                    save_credentials=False,
                )
                if session_name in self._sessions:
                    return self._sessions[session_name], None
                return None, result

            return None, (
                f"❌ No active session '{session_name}'.\n\n"
                f"Please connect first using github_connect:\n"
                f"  github_connect(token='ghp_xxxxxxxxxxxx')\n\n"
                f"Active sessions: {', '.join(self._sessions.keys()) if self._sessions else 'none'}"
            )

        return self._sessions[session_name], None

    def get_protocol(self, session_name: str = "default") -> str:
        """Get the preferred clone protocol for a session."""
        session, _ = self._get_session(session_name)
        return session.protocol if session else "ssh"

    # ================================================================
    # Core HTTP Methods
    # ================================================================

    def get(
        self,
        path: str,
        session_name: str = "default",
        params: Optional[dict] = None,
        raw: bool = False,
    ) -> tuple[Optional[Any], Optional[str]]:
        """
        Perform a GET request. Returns (data, error).
        If raw=True, returns response text instead of JSON.
        """
        session, error = self._get_session(session_name)
        if error:
            return None, error

        try:
            response = session.client.get(path, params=params)
            self._check_rate_limit(response, session)
            response.raise_for_status()
            session.last_used = time.time()
            session.request_count += 1

            if raw:
                text = response.text
                if len(text) > MAX_OUTPUT_SIZE:
                    text = text[:MAX_OUTPUT_SIZE] + f"\n\n... [OUTPUT TRUNCATED — {len(response.text)} bytes total]"
                return text, None

            return response.json(), None

        except httpx.HTTPStatusError as e:
            return None, self._format_api_error(e, path)
        except Exception as e:
            return None, f"❌ Request failed: {str(e)}"

    def get_paginated(
        self,
        path: str,
        session_name: str = "default",
        params: Optional[dict] = None,
        max_items: int = 100,
    ) -> tuple[Optional[list], Optional[str]]:
        """
        Perform a paginated GET request. Follows Link headers automatically.
        Returns (list_of_items, error).
        """
        session, error = self._get_session(session_name)
        if error:
            return None, error

        if params is None:
            params = {}
        params.setdefault("per_page", min(max_items, MAX_PER_PAGE))

        all_items = []
        url = path

        try:
            while url and len(all_items) < max_items:
                if url.startswith("http"):
                    response = session.client.get(url)
                else:
                    response = session.client.get(url, params=params)
                    params = None  # Only use params for first request

                self._check_rate_limit(response, session)
                response.raise_for_status()
                session.last_used = time.time()
                session.request_count += 1

                data = response.json()
                if isinstance(data, list):
                    all_items.extend(data)
                else:
                    all_items.append(data)
                    break

                # Follow pagination
                link_header = response.headers.get("Link", "")
                url = self._parse_next_link(link_header)

            return all_items[:max_items], None

        except httpx.HTTPStatusError as e:
            return None, self._format_api_error(e, path)
        except Exception as e:
            return None, f"❌ Request failed: {str(e)}"

    def post(
        self,
        path: str,
        session_name: str = "default",
        json_data: Optional[dict] = None,
        raw_data: Optional[str] = None,
        content_type: Optional[str] = None,
    ) -> tuple[Optional[Any], Optional[str]]:
        """Perform a POST request. Returns (data, error)."""
        session, error = self._get_session(session_name)
        if error:
            return None, error

        headers = {}
        if content_type:
            headers["Content-Type"] = content_type

        try:
            if json_data is not None:
                response = session.client.post(path, json=json_data, headers=headers)
            else:
                response = session.client.post(path, content=raw_data, headers=headers)

            self._check_rate_limit(response, session)
            response.raise_for_status()
            session.last_used = time.time()
            session.request_count += 1

            if response.text.strip():
                try:
                    return response.json(), None
                except Exception:
                    return response.text, None
            return None, None

        except httpx.HTTPStatusError as e:
            return None, self._format_api_error(e, path)
        except Exception as e:
            return None, f"❌ Request failed: {str(e)}"

    def put(
        self,
        path: str,
        session_name: str = "default",
        json_data: Optional[dict] = None,
    ) -> tuple[Optional[Any], Optional[str]]:
        """Perform a PUT request. Returns (data, error)."""
        session, error = self._get_session(session_name)
        if error:
            return None, error

        try:
            response = session.client.put(path, json=json_data)
            self._check_rate_limit(response, session)
            response.raise_for_status()
            session.last_used = time.time()
            session.request_count += 1

            if response.text.strip():
                try:
                    return response.json(), None
                except Exception:
                    return response.text, None
            return None, None

        except httpx.HTTPStatusError as e:
            return None, self._format_api_error(e, path)
        except Exception as e:
            return None, f"❌ Request failed: {str(e)}"

    def patch(
        self,
        path: str,
        session_name: str = "default",
        json_data: Optional[dict] = None,
    ) -> tuple[Optional[Any], Optional[str]]:
        """Perform a PATCH request. Returns (data, error)."""
        session, error = self._get_session(session_name)
        if error:
            return None, error

        try:
            response = session.client.patch(path, json=json_data)
            self._check_rate_limit(response, session)
            response.raise_for_status()
            session.last_used = time.time()
            session.request_count += 1

            if response.text.strip():
                try:
                    return response.json(), None
                except Exception:
                    return response.text, None
            return None, None

        except httpx.HTTPStatusError as e:
            return None, self._format_api_error(e, path)
        except Exception as e:
            return None, f"❌ Request failed: {str(e)}"

    def delete(
        self,
        path: str,
        session_name: str = "default",
        json_data: Optional[dict] = None,
    ) -> tuple[Optional[Any], Optional[str]]:
        """Perform a DELETE request. Returns (data, error)."""
        session, error = self._get_session(session_name)
        if error:
            return None, error

        try:
            response = session.client.delete(path, json=json_data)
            self._check_rate_limit(response, session)
            response.raise_for_status()
            session.last_used = time.time()
            session.request_count += 1

            if response.text.strip():
                try:
                    return response.json(), None
                except Exception:
                    return response.text, None
            return None, None

        except httpx.HTTPStatusError as e:
            return None, self._format_api_error(e, path)
        except Exception as e:
            return None, f"❌ Request failed: {str(e)}"

    # ================================================================
    # Helpers
    # ================================================================

    @staticmethod
    def _parse_next_link(link_header: str) -> Optional[str]:
        """Parse the 'next' URL from a GitHub Link header."""
        if not link_header:
            return None
        for part in link_header.split(","):
            if 'rel="next"' in part:
                url = part.split(";")[0].strip().strip("<>")
                return url
        return None

    @staticmethod
    def _check_rate_limit(response: httpx.Response, session: "_GitHubSession"):
        """Check rate limit headers and warn if low."""
        remaining = response.headers.get("X-RateLimit-Remaining")
        if remaining and int(remaining) < 100:
            limit = response.headers.get("X-RateLimit-Limit", "?")
            reset = response.headers.get("X-RateLimit-Reset", "")
            reset_str = ""
            if reset:
                import datetime
                reset_time = datetime.datetime.fromtimestamp(int(reset))
                reset_str = f" (resets at {reset_time.strftime('%H:%M:%S')})"
            print(
                f"⚠️ Rate limit low: {remaining}/{limit} remaining{reset_str}",
                file=sys.stderr,
            )

    @staticmethod
    def _format_api_error(e: httpx.HTTPStatusError, path: str) -> str:
        """Format a GitHub API error response."""
        status = e.response.status_code
        try:
            body = e.response.json()
            message = body.get("message", "")
            errors = body.get("errors", [])
            error_details = ""
            if errors:
                details = [err.get("message", str(err)) for err in errors]
                error_details = "\n  " + "\n  ".join(details)
            return f"❌ HTTP {status}: {message}{error_details} — {path}"
        except Exception:
            return f"❌ HTTP {status}: {e.response.reason_phrase} — {path}"

    def get_clone_url(self, owner: str, repo: str, session_name: str = "default") -> str:
        """Get the clone URL in the preferred protocol."""
        protocol = self.get_protocol(session_name)
        if protocol == "https":
            session, _ = self._get_session(session_name)
            base = "https://github.com"
            if session and session.api_url != "https://api.github.com":
                base = session.api_url.replace("/api/v3", "")
            return f"{base}/{owner}/{repo}.git"
        else:
            return f"git@github.com:{owner}/{repo}.git"

    # ================================================================
    # Session Info
    # ================================================================

    def list_sessions(self) -> list[dict]:
        """List all active sessions."""
        return [s.info() for s in self._sessions.values()]

    def is_connected(self, session_name: str = "default") -> bool:
        """Check if a session exists."""
        return session_name in self._sessions


class _GitHubSession:
    """Represents a single GitHub API session."""

    def __init__(
        self,
        name: str,
        api_url: str,
        protocol: str,
        client: httpx.Client,
        username: str,
        user_data: dict,
    ):
        self.name = name
        self.api_url = api_url
        self.protocol = protocol
        self.client = client
        self.username = username
        self.user_data = user_data
        self.connected_at = time.time()
        self.last_used = time.time()
        self.request_count = 0

    @property
    def uptime_str(self) -> str:
        secs = int(time.time() - self.connected_at)
        if secs < 60:
            return f"{secs}s"
        elif secs < 3600:
            return f"{secs // 60}m {secs % 60}s"
        else:
            h = secs // 3600
            m = (secs % 3600) // 60
            return f"{h}h {m}m"

    def info(self) -> dict:
        """Return session info as a dictionary."""
        return {
            "session_name": self.name,
            "api_url": self.api_url,
            "protocol": self.protocol,
            "username": self.username,
            "name": self.user_data.get("name", ""),
            "uptime": self.uptime_str,
            "requests": self.request_count,
        }
