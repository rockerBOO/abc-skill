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


import argparse
import os
import shutil
import sys


def install_skill(
    harness: str,
    scope: str,
    *,
    source: pathlib.Path,
    cwd: pathlib.Path,
    home: pathlib.Path,
    codex_home: pathlib.Path | None,
    force: bool = False,
    dry_run: bool = False,
) -> pathlib.Path:
    """Copy the skill tree into the destination for harness/scope.

    Stages into a sibling temp directory first, then publishes it, so a failed
    copy never leaves a half-written skill. Refuses to replace an existing
    destination unless force is set.
    """
    dest = destination(harness, scope, cwd=cwd, home=home, codex_home=codex_home)
    if dry_run:
        return dest

    dest.parent.mkdir(parents=True, exist_ok=True)
    staging = dest.with_name(f"{dest.name}.tmp-{os.getpid()}")
    if staging.exists():
        shutil.rmtree(staging)

    ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
    shutil.copytree(source, staging, ignore=ignore)

    if dest.exists():
        if not force:
            shutil.rmtree(staging)
            raise FileExistsError(f"{dest} already exists (use --force to replace it)")
        shutil.rmtree(dest)

    staging.rename(dest)
    return dest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="install.py", description="Install the abc-notation skill."
    )
    parser.add_argument(
        "--harness", action="append", choices=HARNESSES, help="repeatable; required unless --all"
    )
    parser.add_argument("--all", action="store_true", help="install for all harnesses")
    parser.add_argument("--scope", choices=("project", "user"), default="user")
    parser.add_argument("--cwd", type=pathlib.Path, default=None, help="project root")
    parser.add_argument("--force", action="store_true", help="replace an existing destination")
    parser.add_argument("--dry-run", action="store_true", help="print actions, write nothing")
    args = parser.parse_args(argv)

    if args.all and args.harness:
        parser.error("--all cannot be combined with --harness")
    if not args.all and not args.harness:
        parser.error("provide --harness or --all")

    harnesses = HARNESSES if args.all else tuple(args.harness)
    source = skill_source()
    if not source.is_dir():
        print(f"error: skill source not found: {source}", file=sys.stderr)
        return 1

    cwd = args.cwd if args.cwd is not None else pathlib.Path.cwd()
    home = pathlib.Path.home()
    codex_home = os.environ.get("CODEX_HOME")
    codex_home_path = pathlib.Path(codex_home) if codex_home else None

    for harness in harnesses:
        dest = install_skill(
            harness,
            args.scope,
            source=source,
            cwd=cwd,
            home=home,
            codex_home=codex_home_path,
            force=args.force,
            dry_run=args.dry_run,
        )
        verb = "would install to" if args.dry_run else "installed"
        print(f"{verb}: {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
