import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_skill_frontmatter_and_triggers():
    text = (ROOT / "SKILL.md").read_text()
    assert text.startswith("---")
    assert "name: abc-notation" in text
    assert "Use when" in text
    assert "5 s" in text or "5 seconds" in text


def test_reference_exists():
    ref = (ROOT / "references" / "abc-notation.md").read_text()
    assert "K:" in ref and "L:" in ref and "V:" in ref
