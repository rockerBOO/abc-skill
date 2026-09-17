import json

import abcbox


class FakePopen:
    _next = 4000

    def __init__(self, *a, **k):
        FakePopen._next += 1
        self.pid = FakePopen._next

    def wait(self):
        return 0


class FakeRun:
    def __init__(self, stdout=""):
        self.stdout = stdout
        self.returncode = 0


def _paths(monkeypatch, tmp_path):
    monkeypatch.setattr(abcbox, "PIDFILE", str(tmp_path / "play.pid"))
    monkeypatch.setattr(abcbox, "LASTFILE", str(tmp_path / "last"))
    monkeypatch.setattr(abcbox, "VOLFILE", str(tmp_path / "vol"))
    monkeypatch.setattr(abcbox, "CACHE", str(tmp_path))


def test_volume_absolute_and_relative(monkeypatch, tmp_path):
    _paths(monkeypatch, tmp_path)
    abcbox.cmd_volume("40")
    assert abcbox.current_volume() == 40
    abcbox.cmd_volume("+15")
    assert abcbox.current_volume() == 55
    abcbox.cmd_volume("-60")
    assert abcbox.current_volume() == 0


def test_volume_clamps(monkeypatch, tmp_path):
    _paths(monkeypatch, tmp_path)
    abcbox.cmd_volume("500")
    assert abcbox.current_volume() == 200


def test_sink_index_parses_pactl(monkeypatch):
    canned = (
        "Sink Input #8067\n"
        '\tapplication.process.id = "2510244"\n'
        "\tVolume: mono: 65536 / 100%\n"
    )
    monkeypatch.setattr(abcbox.subprocess, "run", lambda *a, **k: FakeRun(canned))
    assert abcbox._sink_index(2510244) == "8067"
    assert abcbox._sink_index(999) is None


def test_start_playback_records_and_applies(monkeypatch, tmp_path):
    _paths(monkeypatch, tmp_path)
    monkeypatch.setattr(abcbox.subprocess, "Popen", FakePopen)
    monkeypatch.setattr(abcbox, "_apply_volume", lambda pid, pct, tries=12: "1")
    wav = tmp_path / "c.wav"
    wav.write_bytes(b"RIFF")
    p, rec = abcbox.start_playback(str(wav), {"start_sec": 1.0})
    assert json.load(open(abcbox.PIDFILE))["pid"] == p.pid
    assert open(abcbox.LASTFILE).read() == str(wav)


def test_stop_and_status(monkeypatch, tmp_path):
    _paths(monkeypatch, tmp_path)
    monkeypatch.setattr(abcbox.subprocess, "Popen", FakePopen)
    monkeypatch.setattr(abcbox, "_apply_volume", lambda pid, pct, tries=12: "1")
    monkeypatch.setattr(abcbox.os, "kill", lambda pid, sig: None)
    monkeypatch.setattr(abcbox.os, "getpgid", lambda pid: pid)
    monkeypatch.setattr(abcbox.os, "killpg", lambda pgid, sig: None)
    wav = tmp_path / "c.wav"
    wav.write_bytes(b"RIFF")
    abcbox.start_playback(str(wav))
    abcbox.cmd_status()
    abcbox.cmd_stop()
    assert not __import__("os").path.exists(abcbox.PIDFILE)
