import json
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load(rel):
    return json.loads((REPO_ROOT / rel).read_text())


def test_claude_plugin_manifest():
    data = _load(".claude-plugin/plugin.json")
    assert data["name"] == "abc-notation"
    assert data["version"] == "0.1.0"
    assert data["repository"] == "https://github.com/rockerBOO/abc-skill"


def test_claude_marketplace_points_at_repo_root():
    data = _load(".claude-plugin/marketplace.json")
    assert data["name"] == "abc-skill"
    assert len(data["plugins"]) == 1
    plugin = data["plugins"][0]
    assert plugin["name"] == "abc-notation"
    assert plugin["source"] == "./"


def test_skill_name_matches_claude_manifest():
    skill = (REPO_ROOT / "skills/abc-notation/SKILL.md").read_text()
    assert "name: abc-notation" in skill


def test_codex_manifest_points_at_skills_dir():
    data = _load(".codex-plugin/plugin.json")
    assert data["name"] == "abc-notation"
    assert data["skills"] == "./skills/"
    assert (REPO_ROOT / data["skills"]).resolve().is_dir()


def test_pi_settings_point_at_skills_dir():
    data = _load(".pi/settings.json")
    assert data["skills"] == ["../skills"]
    resolved = (REPO_ROOT / ".pi" / data["skills"][0]).resolve()
    assert resolved == (REPO_ROOT / "skills").resolve()


def test_versions_match_across_manifests():
    import tomllib

    version = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())["project"]["version"]
    assert _load(".claude-plugin/plugin.json")["version"] == version
    assert _load(".claude-plugin/marketplace.json")["plugins"][0]["version"] == version
    assert _load(".codex-plugin/plugin.json")["version"] == version
