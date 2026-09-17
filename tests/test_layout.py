import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_canonical_skill_dir_exists():
    assert (REPO_ROOT / "skills" / "abc-notation" / "SKILL.md").is_file()


def test_old_skill_location_is_gone():
    assert not (REPO_ROOT / ".agents" / "skills" / "abc-notation").exists()


def test_scenarios_reference_new_path():
    text = (REPO_ROOT / "skills/abc-notation/tests/scenarios.md").read_text()
    assert ".agents/skills/abc-notation" not in text
    assert "skills/abc-notation" in text
