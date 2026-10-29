#!/usr/bin/env python3
"""Validate the Agensi package and write dist/github-mcp-pro.zip."""

from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "agensi_build" / "github-mcp-pro"
DIST = ROOT / "dist" / "github-mcp-pro.zip"

REQUIRED_FRONTMATTER = {
    "name": "github-devops-actions-pro",
    "version": "1.1.0",
    "author": "Pawan Gunjkar",
}

SECRET_PATTERNS = (
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"gho_[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----"),
    re.compile(r"sk-(?:ant|proj|live|test)-[A-Za-z0-9_\-]{20,}"),
)

UNSAFE_PATTERNS = (
    re.compile(r"\beval\s*\("),
    re.compile(r"\bexec\s*\("),
    re.compile(r"shell\s*=\s*True"),
    re.compile(r"\bos\.system\s*\("),
    re.compile(r"\bsubprocess\b"),
)

REQUIRED_SKILL_TOOLS = (
    "github_check_ci_secrets_and_variables",
    "github_generate_action_pipeline",
    "github_get_run_artifacts_metadata",
    "github_get_failed_job_logs",
    "github_rerun_failed_jobs",
    "github_get_pending_deployments",
    "github_review_Pending_deployment",
)


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        fail("SKILL.md must start with a YAML frontmatter block")
    end = text.find("\n---\n", 4)
    if end < 0:
        fail("SKILL.md frontmatter is not closed with ---")
    data: dict[str, str] = {}
    for line in text[4:end].splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in line:
            fail(f"Invalid frontmatter line: {line}")
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip("\"'")
    for key, expected in REQUIRED_FRONTMATTER.items():
        if data.get(key) != expected:
            fail(f"frontmatter {key} must be {expected!r}, found {data.get(key)!r}")
    return data


def tool_names() -> list[str]:
    names: list[str] = []
    for path in (ROOT / "server.py", ROOT / "actions_tools.py"):
        for match in re.finditer(r"^\s*def (github_[A-Za-z0-9_]+)\(", path.read_text(encoding="utf-8"), re.M):
            names.append(match.group(1))
    if len(names) != len(set(names)):
        fail("duplicate github_ tool names")
    return names


def scan_package() -> list[Path]:
    files = [path for path in PACKAGE.rglob("*") if path.is_file()]
    if not files:
        fail(f"package directory is empty: {PACKAGE}")
    for path in files:
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(PACKAGE)
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                fail(f"possible hardcoded secret in {rel}")
        for pattern in UNSAFE_PATTERNS:
            if pattern.search(text):
                fail(f"unsafe call matching {pattern.pattern} in {rel}")
    return files


def build_zip(files: list[Path]) -> None:
    DIST.parent.mkdir(parents=True, exist_ok=True)
    if DIST.exists():
        DIST.unlink()
    with zipfile.ZipFile(DIST, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(PACKAGE).as_posix())
    with zipfile.ZipFile(DIST) as archive:
        names = set(archive.namelist())
    required = {
        "SKILL.md",
        "scripts/verify_env.py",
        "reference/tools-reference.md",
        "reference/mcp-setup.md",
    }
    missing = required - names
    if missing:
        fail(f"zip is missing {sorted(missing)}")


def main() -> int:
    skill_path = PACKAGE / "SKILL.md"
    if not skill_path.is_file():
        fail("SKILL.md is missing")
    skill = skill_path.read_text(encoding="utf-8")
    frontmatter = parse_frontmatter(skill)
    for heading in (
        "Workflow 1: Zero-to-CI Pipeline Authoring",
        "Workflow 2: Autonomous PR Review",
        "Workflow 3: GitHub Actions Failure Root-Cause Triage",
        "Workflow 4: Environment Gate Promotion",
        "Strict Safety Guardrails",
    ):
        if heading not in skill:
            fail(f"SKILL.md is missing heading: {heading}")
    for name in REQUIRED_SKILL_TOOLS:
        if name not in skill:
            fail(f"SKILL.md does not mention {name}")

    reference = (PACKAGE / "reference" / "tools-reference.md").read_text(encoding="utf-8")
    names = tool_names()
    missing = [name for name in names if f"`{name}`" not in reference]
    if missing:
        fail("tools-reference.md is missing: " + ", ".join(missing))
    if len(names) != 80:
        fail(f"expected 80 tools, found {len(names)}")

    files = scan_package()
    build_zip(files)
    print(f"Validated {frontmatter['name']} {frontmatter['version']} by {frontmatter['author']}")
    print(f"Catalog covers {len(names)} tools")
    print(f"Wrote {DIST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
