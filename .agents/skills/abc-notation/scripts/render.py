"""Rendering: dependency-free MIDI writer, SoundFont synth, stdlib fallback synth."""
import array
import glob
import math
import os
import re
import shutil
import struct
import subprocess
import wave

SR = 44100
DIV = 480


def _vlq(n):
    """MIDI variable-length quantity. Clamps negatives (regression guard)."""
    n = max(0, int(n))
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    return bytes(reversed(out))


def write_midi(tracks, path, qpm):
    """tracks: list of {channel, program, notes:[(midi, start_s, dur_s, vel)]}."""
    data = b"MThd" + struct.pack(">IHHH", 6, 1, len(tracks), DIV)
    us_per_q = int(60_000_000 / qpm)
    for tr in tracks:
        ch, prog = tr.get("channel", 0), tr.get("program", 0)
        ev = [(0, b"\xff\x51\x03" + us_per_q.to_bytes(3, "big")),
              (0, bytes([0xC0 | ch, prog & 0x7F]))]
        for midi, st, du, vel in tr["notes"]:
            t0 = max(0, int(round(st * qpm / 60 * DIV)))
            t1 = max(0, int(round((st + du) * qpm / 60 * DIV)))
            v = max(1, min(127, int(vel)))
            m = int(midi) & 0x7F
            ev.append((t0, bytes([0x90 | ch, m, v])))
            ev.append((t1, bytes([0x80 | ch, m, 0])))
        ev.sort(key=lambda x: (x[0], 0 if x[1][0] == 0x80 else 1))
        trk, last = bytearray(), 0
        for t, d in ev:
            trk += _vlq(t - last) + d
            last = t
        trk += b"\x00\xff\x2f\x00"
        data += b"MTrk" + struct.pack(">I", len(trk)) + bytes(trk)
    with open(path, "wb") as f:
        f.write(data)
    return path


def find_soundfont():
    """First existing SoundFont in the documented discovery order."""
    cands = []
    if os.environ.get("ABC_SOUNDFONT"):
        cands.append(os.environ["ABC_SOUNDFONT"])
    for pat in ("~/.local/share/soundfonts/*.sf2", "~/.local/share/soundfonts/*.sf3",
                "~/.local/share/sounds/sf2/*.sf2", "/usr/share/sounds/sf2/*.sf2",
                "/usr/share/soundfonts/*.sf2", "/usr/share/sounds/sf3/*.sf3"):
        cands += sorted(glob.glob(os.path.expanduser(pat)))
    for c in cands:
        if os.path.exists(c):
            return c
    return None


def fluidsynth_available():
    return shutil.which("fluidsynth") is not None


def render_soundfont(midi_path, wav_path, soundfont, rate=SR):
    r = subprocess.run(["fluidsynth", "-ni", "-F", wav_path, "-r", str(rate),
                        soundfont, midi_path], capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(wav_path):
        raise RuntimeError(f"fluidsynth failed: {r.stderr.strip()[:300]}")
    return wav_path


def trim_wav(path, total_sec, rate=SR, fade=0.1):
    """Truncate a WAV to total_sec and apply a short fade-out at the end."""
    with wave.open(path, "rb") as w:
        params = w.getparams()
        frames = w.readframes(w.getnframes())
    nch, width = params.nchannels, params.sampwidth
    keep = int(total_sec * rate) * nch * width
    frames = frames[:keep]
    if width == 2 and fade > 0 and frames:
        a = array.array("h")
        a.frombytes(frames)
        total_frames = len(a) // nch
        f = min(int(fade * rate), total_frames)
        for i in range(f):
            g = i / f
            base = (total_frames - f + i) * nch
            for c in range(nch):
                a[base + c] = int(a[base + c] * g)
        frames = a.tobytes()
    with wave.open(path, "wb") as w:
        w.setnchannels(nch)
        w.setsampwidth(width)
        w.setframerate(params.framerate)
        w.writeframes(frames)
    return path


def synth_window(events, start_beat, dur_beats, qpm, path, gain=0.20):
    """Stdlib synth. events: (midi, start, dur) or (midi, start, dur, gain)."""
    spb = 60.0 / qpm
    n = max(1, int(dur_beats * spb * SR))
    buf = [0.0] * n
    atk = max(1, int(0.006 * SR))
    for ev in events:
        if len(ev) == 4:
            midi, s, d, g = ev
        else:
            midi, s, d = ev
            g = gain
        if s >= start_beat + dur_beats or s + d <= start_beat:
            continue
        s0, e0 = max(s, start_beat), min(s + d, start_beat + dur_beats)
        i0 = int((s0 - start_beat) * spb * SR)
        i1 = min(n, int((e0 - start_beat) * spb * SR))
        length = i1 - i0
        if length <= 0:
            continue
        f = 440.0 * 2 ** ((midi - 69) / 12.0)
        for i in range(i0, i1):
            t = (i - i0) / SR
            ds = length / SR
            env = min(1.0, t / atk) if t < 0.006 else 1.0
            if ds > 0.02 and t > ds - 0.08:
                env *= max(0.0, (ds - t) / 0.08)
            env *= math.exp(-1.4 * t)
            ph = 2 * math.pi * f * t
            buf[i] += g * env * (math.sin(ph) + 0.5 * math.sin(2 * ph)
                                 + 0.25 * math.sin(3 * ph))
    edge = min(int(0.08 * SR), n // 2)
    for i in range(edge):
        buf[i] *= i / edge
        buf[n - 1 - i] *= i / edge
    frames = bytearray()
    for v in buf:
        frames += struct.pack("<h", int(max(-1.0, min(1.0, v)) * 32000))
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(bytes(frames))
    return path


def synth_notes(notes, total_sec, path, gain=0.20):
    """Seconds-based synth: qpm=60 makes synth_window's 'beats' equal seconds."""
    return synth_window(notes, 0.0, total_sec, 60.0, path, gain=gain)


def notes_to_wav(notes, total_sec, out, qpm=120.0, engine="auto", program=0, sf=None):
    """Render notes to WAV. Returns (path, engine_used). notes are seconds-based."""
    sf = sf or find_soundfont()
    if engine in ("auto", "soundfont", "sf") and sf and fluidsynth_available():
        midi_notes = [(n[0], n[1], n[2],
                       max(1, min(127, int(20 + 105 * (n[3] if len(n) > 3 else 1.0)))))
                      for n in notes]
        write_midi([{"channel": 0, "program": program, "notes": midi_notes}], out + ".mid", qpm)
        render_soundfont(out + ".mid", out, sf)
        trim_wav(out, total_sec)
        return out, "soundfont"
    synth_notes(notes, total_sec, out)
    return out, "synth"
