# Changelog

## [Unreleased]

### Fixed
- **`github_protect_branch` wiped existing protection.** It now reads the current rule and preserves required
  status checks, push restrictions, dismissal restrictions, linear history, and similar settings, changing only
  the review count and admin enforcement. Permission errors stop the update instead of overwriting.
- **GitHub Enterprise clone URLs pointed at github.com.** SSH and HTTPS clone URLs (and Actions run links) use the
  host of the configured API URL, including GHE Server (`/api/v3`) and GHE Cloud (`api.<org>.ghe.com`).
- File paths, branch names, tag names, and compare refs are URL-encoded (spaces, `#`, `%` etc. now work).
- `github_get_file` fetches files over 1 MB through the raw media type, summarises binary files instead of
  printing garbage, and truncates very large text with a clear marker.
- Rate limits: primary and secondary rate-limit rejections are retried once when the wait is 90 s or less;
  longer waits are reported instead of slept through.
- Author email typo in file headers.

### Added
- `tests/test_github_bugfixes.py`: 11 regression tests against a fake GitHub API.
