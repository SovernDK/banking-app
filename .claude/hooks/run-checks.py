#!/usr/bin/env python3
"""Stop hook: runs lint, format check, type check, unit and e2e tests whenever Python code changed.

The result is shown to the user directly, so a check run can't be faked by the
model. A failing run blocks Claude from finishing and feeds the output back.
Ruff and pyright are what the VS Code language server reports as diagnostics,
so a green run also stands in for "no diagnostics errors in touched files".
"""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(os.environ.get("CLAUDE_PROJECT_DIR", Path.cwd()))
# Kept outside the repo so it never shows up in git status; keyed by project so repos don't share it.
STATE_FILE = (
    Path.home() / ".claude" / "cache" / f"last-green-checks-{hashlib.sha256(str(PROJECT_DIR).encode()).hexdigest()[:12]}"
)
FINGERPRINT_PATHSPECS = ["*.py", "pyproject.toml", "uv.lock"]
CHECKS = [
    ("ruff check", ["uv", "run", "ruff", "check", "."]),
    ("ruff format", ["uv", "run", "ruff", "format", "--check", "."]),
    ("pyright", ["uv", "run", "pyright"]),
    ("unit tests", ["uv", "run", "pytest", "-q"]),
    ("e2e tests", ["uv", "run", "pytest", "-m", "e2e", "-q"]),
]
OUTPUT_TAIL_LINES = 40


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=PROJECT_DIR, capture_output=True, text=True, check=False).stdout


def code_fingerprint() -> str:
    """Hash of HEAD plus every changed or untracked code file, so unchanged code isn't rechecked."""
    digest = hashlib.sha256(git("rev-parse", "HEAD").encode())
    digest.update(git("diff", "HEAD", "--", *FINGERPRINT_PATHSPECS).encode())
    for name in sorted(git("ls-files", "--others", "--exclude-standard", "--", *FINGERPRINT_PATHSPECS).split()):
        path = PROJECT_DIR / name
        if path.is_file():
            digest.update(name.encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def last_line(output: str) -> str:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    return lines[-1] if lines else "no output"


def run_check(command: list[str]) -> tuple[bool, str]:
    env = {**os.environ}
    env.pop("VIRTUAL_ENV", None)
    try:
        result = subprocess.run(command, cwd=PROJECT_DIR, env=env, capture_output=True, text=True, check=False)
    except FileNotFoundError as error:
        return False, str(error)
    return result.returncode == 0, result.stdout + result.stderr


def main() -> None:
    payload = json.load(sys.stdin)
    fingerprint = code_fingerprint()
    if STATE_FILE.exists() and STATE_FILE.read_text() == fingerprint:
        return

    failures: list[tuple[str, str]] = []
    summaries: list[str] = []
    for name, command in CHECKS:
        passed, output = run_check(command)
        summaries.append(f"{'✓' if passed else '✗'} {name}")
        if not passed:
            failures.append((name, output))
    summary = " · ".join(summaries)

    if not failures:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(fingerprint)
        print(json.dumps({"systemMessage": f"✅ Checks hook: {summary}"}))
        return

    if payload.get("stop_hook_active"):
        # Already sent back once this turn; let Claude stop instead of looping,
        # but make sure the user sees the failure.
        print(json.dumps({"systemMessage": f"❌ Checks hook: still failing — {summary}"}))
        return

    details = "\n\n".join(
        f"## {name} — {last_line(output)}\n" + "\n".join(output.splitlines()[-OUTPUT_TAIL_LINES:])
        for name, output in failures
    )
    print(
        json.dumps(
            {
                "decision": "block",
                "reason": f"Checks failed (run by a hook, not by you). Fix them before finishing.\n\n{details}",
                "systemMessage": f"❌ Checks hook: {summary}",
            }
        )
    )


if __name__ == "__main__":
    main()
