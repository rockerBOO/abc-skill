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


def _make_source(tmp_path):
    src = tmp_path / "src" / "abc-notation"
    (src / "scripts").mkdir(parents=True)
    (src / "SKILL.md").write_text("---\nname: abc-notation\n---\n")
    (src / "scripts" / "abcbox.py").write_text("x = 1\n")
    (src / "scripts" / "__pycache__").mkdir()
    (src / "scripts" / "__pycache__" / "abcbox.cpython-312.pyc").write_bytes(b"\x00")
    return src


def _install(tmp_path, src, **kwargs):
    return install.install_skill(
        "pi",
        "project",
        source=src,
        cwd=tmp_path / "proj",
        home=tmp_path / "home",
        codex_home=None,
        **kwargs,
    )


def test_install_copies_skill_and_excludes_pycache(tmp_path):
    src = _make_source(tmp_path)
    dest = _install(tmp_path, src)
    assert (dest / "SKILL.md").is_file()
    assert (dest / "scripts" / "abcbox.py").is_file()
    assert not (dest / "scripts" / "__pycache__").exists()
    assert not list(dest.parent.glob("abc-notation.tmp-*"))


def test_dry_run_writes_nothing(tmp_path):
    src = _make_source(tmp_path)
    dest = _install(tmp_path, src, dry_run=True)
    assert not dest.exists()


def test_existing_destination_without_force_errors(tmp_path):
    src = _make_source(tmp_path)
    dest = install.destination(
        "pi", "project", cwd=tmp_path / "proj", home=tmp_path / "home", codex_home=None
    )
    dest.mkdir(parents=True)
    (dest / "stale.txt").write_text("old")
    with pytest.raises(FileExistsError):
        _install(tmp_path, src)
    assert (dest / "stale.txt").is_file()
    assert not (dest / "SKILL.md").exists()


def test_force_replaces_existing_destination(tmp_path):
    src = _make_source(tmp_path)
    dest = install.destination(
        "pi", "project", cwd=tmp_path / "proj", home=tmp_path / "home", codex_home=None
    )
    dest.mkdir(parents=True)
    (dest / "stale.txt").write_text("old")
    result = _install(tmp_path, src, force=True)
    assert result == dest
    assert (dest / "SKILL.md").is_file()
    assert not (dest / "stale.txt").exists()


def test_main_installs_all_harnesses(tmp_path, monkeypatch, capsys):
    src = _make_source(tmp_path)
    monkeypatch.setattr(install, "skill_source", lambda: src)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("CODEX_HOME", raising=False)
    code = install.main(["--all", "--scope", "user", "--cwd", str(tmp_path / "proj")])
    out = capsys.readouterr().out
    assert code == 0
    assert (tmp_path / "home/.claude/skills/abc-notation/SKILL.md").is_file()
    assert (tmp_path / "home/.agents/skills/abc-notation/SKILL.md").is_file()
    assert (tmp_path / "home/.codex/skills/abc-notation/SKILL.md").is_file()
    assert "installed" in out


def test_main_requires_harness_or_all(capsys):
    with pytest.raises(SystemExit):
        install.main(["--scope", "user"])


def test_main_all_project_scope_installs_shared_destination_once(
    tmp_path, monkeypatch, capsys
):
    src = _make_source(tmp_path)
    monkeypatch.setattr(install, "skill_source", lambda: src)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("CODEX_HOME", raising=False)
    code = install.main(["--all", "--scope", "project", "--cwd", str(tmp_path / "proj")])
    out = capsys.readouterr().out
    assert code == 0
    assert (tmp_path / "proj/.claude/skills/abc-notation/SKILL.md").is_file()
    # pi and codex share the project-scope cross-runtime path; install it once.
    assert (tmp_path / "proj/.agents/skills/abc-notation/SKILL.md").is_file()
    assert out.count("installed:") == 2
    assert "skipped" in out


def test_main_existing_destination_refuses_cleanly(tmp_path, monkeypatch, capsys):
    src = _make_source(tmp_path)
    monkeypatch.setattr(install, "skill_source", lambda: src)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("CODEX_HOME", raising=False)
    args = ["--harness", "pi", "--scope", "project", "--cwd", str(tmp_path / "proj")]
    assert install.main(args) == 0
    capsys.readouterr()
    code = install.main(args)  # destination now exists, no --force
    captured = capsys.readouterr()
    assert code == 1
    assert "already exists" in captured.err
    assert "Traceback" not in captured.err
