import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_readme_documents_harnesses_and_os():
    text = (REPO_ROOT / "README.md").read_text().lower()
    for harness in ("claude code", "codex", "pi"):
        assert harness in text, f"README missing {harness}"
    for os_name in ("windows", "macos", "linux"):
        assert os_name in text, f"README missing {os_name}"
    assert "scripts/install.py" in text


def test_readme_has_quick_start_commands():
    text = (REPO_ROOT / "README.md").read_text()
    assert "abcbox.py send" in text
    assert "abcbox.py play" in text
    assert "mash.py" in text
