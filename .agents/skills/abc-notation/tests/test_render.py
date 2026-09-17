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


def test_trim_wav_limits_duration(tmp_path):
    import array
    import wave

    p = tmp_path / "long.wav"
    n = int(3 * render.SR)
    a = array.array("h", [10000] * (n * 2))
    with wave.open(str(p), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(render.SR)
        w.writeframes(a.tobytes())
    render.trim_wav(str(p), 1.0)
    with wave.open(str(p)) as w:
        assert w.getnframes() == render.SR
        data = array.array("h")
        data.frombytes(w.readframes(w.getnframes()))
    # fade-out: ~full amplitude where the fade begins, ~silent at the final frame
    assert abs(data[(render.SR - int(0.1 * render.SR)) * 2]) > 5000
    assert abs(data[-1]) < 100


def test_notes_to_wav_falls_back_on_soundfont_failure(tmp_path, monkeypatch):
    sf = tmp_path / "x.sf2"
    sf.write_bytes(b"RIFF")
    monkeypatch.setattr(render, "fluidsynth_available", lambda: True)

    def boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(render, "render_soundfont", boom)
    path, used = render.notes_to_wav([(60, 0.0, 0.5)], 0.5, str(tmp_path / "d.wav"),
                                     engine="auto", sf=str(sf))
    assert used == "synth"
    assert path == str(tmp_path / "d.wav")
