import wave

import render


def test_synth_notes_writes_wav(tmp_path):
    out = tmp_path / "a.wav"
    render.synth_notes([(60, 0.0, 0.5), (64, 0.5, 0.5)], 1.0, str(out))
    with wave.open(str(out)) as w:
        assert w.getframerate() == render.SR
        assert w.getnchannels() == 1
        assert w.getnframes() > 0


def test_notes_to_wav_synth_engine(tmp_path):
    out = tmp_path / "b.wav"
    path, used = render.notes_to_wav([(60, 0.0, 0.5)], 0.5, str(out), engine="synth")
    assert used == "synth"
    assert path == str(out)


def test_find_soundfont_env_override(tmp_path, monkeypatch):
    sf = tmp_path / "x.sf2"
    sf.write_bytes(b"RIFF")
    monkeypatch.setenv("ABC_SOUNDFONT", str(sf))
    assert render.find_soundfont() == str(sf)


def test_render_soundfont_skipped_without_fluidsynth(tmp_path, monkeypatch):
    import pytest
    monkeypatch.setattr(render, "fluidsynth_available", lambda: False)
    path, used = render.notes_to_wav([(60, 0.0, 0.5)], 0.5, str(tmp_path / "c.wav"),
                                     engine="auto", sf=str(tmp_path / "x.sf2"))
    assert used == "synth"
