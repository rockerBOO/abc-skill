#!/usr/bin/env python3
"""Install the abc-notation skill into a harness's skill directory.

Harnesses: claude (Claude Code), codex (OpenAI Codex), pi.
Scopes: project (under --cwd) or user (under $HOME / $CODEX_HOME).

Copies files; never creates symlinks, so Windows behaves like POSIX.
"""
import pathlib

SKILL_NAME = "abc-notation"
HARNESSES = ("claude", "codex", "pi")


def skill_source() -> pathlib.Path:
    """The canonical skill directory in this repo."""
    return pathlib.Path(__file__).resolve().parents[1] / "skills" / SKILL_NAME


def destination(
    harness: str,
    scope: str,
    *,
    cwd: pathlib.Path,
    home: pathlib.Path,
    codex_home: pathlib.Path | None = None,
) -> pathlib.Path:
    """Resolve the install destination for a harness/scope pair."""
    if harness not in HARNESSES:
        raise ValueError(f"unknown harness: {harness!r} (expected one of {HARNESSES})")
    if scope not in ("project", "user"):
        raise ValueError(f"unknown scope: {scope!r} (expected 'project' or 'user')")

    base = cwd if scope == "project" else home
    if harness == "claude":
        return base / ".claude" / "skills" / SKILL_NAME
    if harness == "pi":
        return base / ".agents" / "skills" / SKILL_NAME
    # codex
    if scope == "user":
        root = codex_home if codex_home is not None else home / ".codex"
        return root / "skills" / SKILL_NAME
    return base / ".agents" / "skills" / SKILL_NAME
