"""
Regression tests for GitHub MCP fixes: branch protection, URL encoding,
Enterprise hosts, large/binary files, and rate-limit retries.

Author: Pawan Gunjkar (pawangunjkar@gmail.com)
"""

from __future__ import annotations

import base64
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import httpx

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

os.environ["GITHUB_MCP_CACHE_DIR"] = tempfile.mkdtemp()
os.environ.pop("GITHUB_TOKEN", None)

from github_mcp import github_client  # noqa: E402
from github_mcp import server  # noqa: E402
from github_mcp.github_client import GitHubClient, _GitHubSession  # noqa: E402


class FakeGitHub:
    def __init__(self):
        self.requests: list[httpx.Request] = []
        self.handler_fn = None

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.handler_fn(request)


class GitHubTestCase(unittest.TestCase):
    api_url = "https://api.github.com"

    def setUp(self):
        self.fake = FakeGitHub()
        self.fake.handler_fn = lambda r: httpx.Response(200, json={})
        client = httpx.Client(base_url=self.api_url, transport=httpx.MockTransport(self.fake.handler))
        server._github._sessions["default"] = _GitHubSession(
            name="default",
            api_url=self.api_url,
            protocol="ssh",
            client=client,
            username="octo",
            user_data={},
        )

    def tearDown(self):
        server._github._sessions.clear()


class BranchProtectionTests(GitHubTestCase):
    def test_existing_status_checks_and_restrictions_are_preserved(self):
        existing = {
            "required_status_checks": {"strict": True, "contexts": ["ci/build", "ci/test"]},
            "required_pull_request_reviews": {
                "dismiss_stale_reviews": True,
                "required_approving_review_count": 1,
                "dismissal_restrictions": {"users": [{"login": "lead"}], "teams": []},
            },
            "restrictions": {"users": [{"login": "release-bot"}], "teams": [{"slug": "core"}], "apps": []},
            "enforce_admins": {"enabled": True},
            "required_linear_history": {"enabled": True},
            "allow_force_pushes": {"enabled": False},
        }

        def handler(request):
            if request.method == "GET":
                return httpx.Response(200, json=existing)
            return httpx.Response(200, json={})

        self.fake.handler_fn = handler
        out = server.github_protect_branch("o", "r", "release/1.x", required_reviewers=2, enforce_admins=False)

        put = [r for r in self.fake.requests if r.method == "PUT"][0]
        self.assertEqual(put.url.raw_path, b"/repos/o/r/branches/release/1.x/protection")
        payload = json.loads(put.content)
        self.assertEqual(payload["required_status_checks"], {"strict": True, "contexts": ["ci/build", "ci/test"]})
        self.assertEqual(payload["restrictions"], {"users": ["release-bot"], "teams": ["core"], "apps": []})
        self.assertEqual(payload["required_pull_request_reviews"]["required_approving_review_count"], 2)
        self.assertTrue(payload["required_pull_request_reviews"]["dismiss_stale_reviews"])
        self.assertEqual(payload["required_pull_request_reviews"]["dismissal_restrictions"]["users"], ["lead"])
        self.assertTrue(payload["required_linear_history"])
        self.assertFalse(payload["enforce_admins"])
        self.assertIn("ci/build", out)

    def test_unprotected_branch_starts_clean(self):
        def handler(request):
            if request.method == "GET":
                return httpx.Response(404, json={"message": "Branch not protected"})
            return httpx.Response(200, json={})

        self.fake.handler_fn = handler
        out = server.github_protect_branch("o", "r", "main")
        self.assertIn("✅", out)
        payload = json.loads([r for r in self.fake.requests if r.method == "PUT"][0].content)
        self.assertIsNone(payload["required_status_checks"])
        self.assertEqual(payload["required_pull_request_reviews"], {"required_approving_review_count": 1})

    def test_permission_error_is_not_overwritten(self):
        self.fake.handler_fn = lambda r: httpx.Response(403, json={"message": "Must have admin rights"})
        out = server.github_protect_branch("o", "r", "main")
        self.assertIn("403", out)
        self.assertFalse([r for r in self.fake.requests if r.method == "PUT"])


class EncodingTests(GitHubTestCase):
    def test_file_path_and_branch_are_encoded(self):
        self.fake.handler_fn = lambda r: httpx.Response(200, json={
            "name": "a b#c.md", "path": "docs/a b#c.md", "sha": "abc1234", "size": 2,
            "encoding": "base64", "content": base64.b64encode(b"hi").decode(),
        })
        server.github_get_file("o", "r", "docs/a b#c.md")
        self.assertEqual(self.fake.requests[-1].url.raw_path, b"/repos/o/r/contents/docs/a%20b%23c.md")
        server.github_delete_branch("o", "r", "feature/x#1")
        self.assertEqual(self.fake.requests[-1].url.raw_path, b"/repos/o/r/git/refs/heads/feature/x%231")

    def test_compare_keeps_fork_prefix(self):
        server.github_compare_branches("o", "r", "main", "fork-user:feature/a b")
        self.assertEqual(
            self.fake.requests[-1].url.raw_path,
            b"/repos/o/r/compare/main...fork-user:feature/a%20b",
        )


class LargeAndBinaryFileTests(GitHubTestCase):
    def test_file_over_1mb_is_fetched_raw(self):
        def handler(request):
            if request.headers.get("Accept") == "application/vnd.github.raw":
                return httpx.Response(200, content=b"big text file")
            return httpx.Response(200, json={"name": "big.txt", "path": "big.txt", "sha": "abcdef1",
                                             "size": 2_000_000, "encoding": "none", "content": ""})

        self.fake.handler_fn = handler
        out = server.github_get_file("o", "r", "big.txt")
        self.assertIn("big text file", out)

    def test_binary_file_is_summarised(self):
        self.fake.handler_fn = lambda r: httpx.Response(200, json={
            "name": "logo.png", "path": "logo.png", "sha": "abcdef1", "size": 4,
            "encoding": "base64", "content": base64.b64encode(b"\x89PN\x00").decode(),
        })
        out = server.github_get_file("o", "r", "logo.png")
        self.assertIn("binary file", out)


class EnterpriseHostTests(unittest.TestCase):
    def test_web_host_mapping(self):
        self.assertEqual(GitHubClient.web_host("https://api.github.com"), "github.com")
        self.assertEqual(GitHubClient.web_host("https://ghe.corp.com/api/v3"), "ghe.corp.com")
        self.assertEqual(GitHubClient.web_host("https://api.acme.ghe.com"), "acme.ghe.com")


class EnterpriseCloneUrlTests(GitHubTestCase):
    api_url = "https://ghe.corp.com/api/v3"

    def test_clone_urls_use_enterprise_host(self):
        out = server.github_get_clone_url("team", "svc")
        self.assertIn("git@ghe.corp.com:team/svc.git", out)
        self.assertIn("https://ghe.corp.com/team/svc.git", out)
        self.assertNotIn("github.com", out.replace("ghe.corp.com", ""))
        self.assertEqual(server._github.get_clone_url("team", "svc"), "git@ghe.corp.com:team/svc.git")


class RateLimitTests(GitHubTestCase):
    def test_secondary_rate_limit_is_retried_once(self):
        responses = [
            httpx.Response(403, headers={"Retry-After": "2"}, json={"message": "secondary rate limit"}),
            httpx.Response(200, json={"name": "r", "full_name": "o/r"}),
        ]
        self.fake.handler_fn = lambda r: responses.pop(0)
        with mock.patch.object(github_client.time, "sleep") as sleep:
            data, error = server._github.get("/repos/o/r")
        self.assertIsNone(error)
        self.assertEqual(data["full_name"], "o/r")
        sleep.assert_called_once_with(2.0)

    def test_long_rate_limit_is_reported_not_slept(self):
        self.fake.handler_fn = lambda r: httpx.Response(
            403,
            headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "9999999999"},
            json={"message": "API rate limit exceeded"},
        )
        with mock.patch.object(github_client.time, "sleep") as sleep:
            _, error = server._github.post("/repos/o/r/issues", json_data={"title": "x"})
        sleep.assert_not_called()
        self.assertIn("rate limit", error)
        self.assertEqual(len(self.fake.requests), 1)


if __name__ == "__main__":
    unittest.main()
