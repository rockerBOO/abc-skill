import io
import json

import abcbox


def _send(monkeypatch, tmp_path, text):
    monkeypatch.setattr(abcbox, "CACHE", str(tmp_path))
    monkeypatch.setattr("sys.stdin", io.StringIO(text))
    return abcbox.load_text


def test_send_caches_and_ids(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(abcbox, "CACHE", str(tmp_path))
    monkeypatch.setattr("sys.stdin", io.StringIO("X:1\nM:4/4\nL:1/4\nK:C\nC D E F|\n"))
    abcbox.cmd_send()
    out = json.loads(capsys.readouterr().out)
    assert out["voices"] == ["1"]
    assert out["key"] == "C"
    assert (tmp_path / (out["id"] + ".abc")).exists()


def test_load_text_by_handle_and_path(monkeypatch, tmp_path):
    monkeypatch.setattr(abcbox, "CACHE", str(tmp_path))
    (tmp_path / "abcd1234.abc").write_text("X:1\nK:C\nC|\n")
    text, src = abcbox.load_text("abcd1234")
    assert "K:C" in text
    p = tmp_path / "file.abc"
    p.write_text("X:2\nK:G\nG|\n")
    text, src = abcbox.load_text(str(p))
    assert "K:G" in text


def test_load_text_unknown_raises(monkeypatch, tmp_path):
    import pytest
    monkeypatch.setattr(abcbox, "CACHE", str(tmp_path))
    with pytest.raises(SystemExit):
        abcbox.load_text("nope-nope")


def test_sections_table(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(abcbox, "CACHE", str(tmp_path))
    (tmp_path / "sec1.abc").write_text(
        "X:1\nM:4/4\nL:1/4\nK:C\n% intro\nC D E F|\n% chorus\nG A B c|\n")
    abcbox.cmd_sections("sec1")
    out = capsys.readouterr().out
    assert "intro" in out and "chorus" in out
