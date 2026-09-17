import pathlib
import subprocess

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_canonical_skill_dir_exists():
    assert (REPO_ROOT / "skills" / "abc-notation" / "SKILL.md").is_file()


def test_old_skill_location_is_gone():
    old = REPO_ROOT / ".agents" / "skills" / "abc-notation"
    # Moving the skill can leave an ignored __pycache__ behind; the invariant is
    # that no skill content remains and nothing under .agents is tracked.
    assert not (old / "SKILL.md").exists()
    tracked = subprocess.run(
        ["git", "ls-files", ".agents"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert tracked.strip() == ""


def test_scenarios_reference_new_path():
    text = (REPO_ROOT / "skills/abc-notation/tests/scenarios.md").read_text()
    assert ".agents/skills/abc-notation" not in text
    assert "skills/abc-notation" in text
