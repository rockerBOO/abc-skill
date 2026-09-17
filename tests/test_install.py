import pathlib

import pytest

import install


def _dest(harness, scope, tmp_path, codex_home=None):
    return install.destination(
        harness,
        scope,
        cwd=tmp_path / "proj",
        home=tmp_path / "home",
        codex_home=codex_home,
    )


def test_destination_claude_project(tmp_path):
    assert _dest("claude", "project", tmp_path) == tmp_path / "proj/.claude/skills/abc-notation"


def test_destination_claude_user(tmp_path):
    assert _dest("claude", "user", tmp_path) == tmp_path / "home/.claude/skills/abc-notation"


def test_destination_pi_project(tmp_path):
    assert _dest("pi", "project", tmp_path) == tmp_path / "proj/.agents/skills/abc-notation"


def test_destination_pi_user(tmp_path):
    assert _dest("pi", "user", tmp_path) == tmp_path / "home/.agents/skills/abc-notation"


def test_destination_codex_project(tmp_path):
    assert _dest("codex", "project", tmp_path) == tmp_path / "proj/.agents/skills/abc-notation"


def test_destination_codex_user_default_home(tmp_path):
    assert _dest("codex", "user", tmp_path) == tmp_path / "home/.codex/skills/abc-notation"


def test_destination_codex_user_respects_codex_home(tmp_path):
    assert _dest("codex", "user", tmp_path, codex_home=tmp_path / "cx") == (
        tmp_path / "cx/skills/abc-notation"
    )


def test_unknown_harness_raises(tmp_path):
    with pytest.raises(ValueError):
        _dest("emacs", "user", tmp_path)


def test_unknown_scope_raises(tmp_path):
    with pytest.raises(ValueError):
        _dest("pi", "galaxy", tmp_path)
