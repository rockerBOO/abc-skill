#!/usr/bin/env python3
"""
SPIKE library (throwaway until the design says otherwise).

ABC -> note events per voice + a STRUCTURE MAP (sections, chords).
Sequential parse so interleaved voices and section markers stay aligned.
"""
import math
import os
import re
import struct
import wave

SR = 44100
NOTE_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
SHARP_ORDER = ["F", "C", "G", "D", "A", "E", "B"]
FLAT_ORDER = ["B", "E", "A", "D", "G", "C", "F"]
MAJOR_SIG = {"C": 0, "G": 1, "D": 2, "A": 3, "E": 4, "B": 5, "F#": 6, "C#": 7,
             "F": -1, "Bb": -2, "Eb": -3, "Ab": -4, "Db": -5, "Gb": -6, "Cb": -7}
MODE_OFFSET = {"major": 0, "ionian": 0, "dorian": 10, "phrygian": 8, "lydian": 7,
               "mixolydian": 5, "minor": 3, "aeolian": 3, "locrian": 1, "": 0}
PC_TO_MAJOR_NAME = {0: "C", 1: "Db", 2: "D", 3: "Eb", 4: "E", 5: "F",
                    6: "F#", 7: "G", 8: "Ab", 9: "A", 10: "Bb", 11: "B"}


def key_accidentals(keystr):
    m = re.match(r"\s*([A-Ga-g])([#b]?)\s*([A-Za-z]*)", (keystr or "C").strip())
    if not m:
        return {}
    letter, acc, mode = m.group(1).upper(), m.group(2), (m.group(3) or "major").lower()
    mode = {"maj": "major", "min": "minor", "": "major"}.get(mode, mode)
    pc = (NOTE_PC[letter] + (1 if acc == "#" else -1 if acc == "b" else 0)) % 12
    sig = MAJOR_SIG[PC_TO_MAJOR_NAME[(pc + MODE_OFFSET.get(mode, 0)) % 12]]
    out = {}
    if sig > 0:
        for L in SHARP_ORDER[:sig]:
            out[L] = "^"
    elif sig < 0:
        for L in FLAT_ORDER[:-sig]:
            out[L] = "_"
    return out


def parse_qpm(q, unit_beats):
    m = re.search(r"(\d+)/(\d+)\s*=\s*(\d+)", q or "")
    if m:
        return int(m.group(3)) * (int(m.group(1)) / int(m.group(2))) * 4.0
    m2 = re.search(r"(\d+)", q or "")
    return (int(m2.group(1)) if m2 else 120) * unit_beats


DUR_RE = re.compile(r"(\d*)(/+)?(\d*)")


def parse_duration(spec):
    if not spec:
        return 1.0
    m = DUR_RE.fullmatch(spec)
    if not m:
        return 1.0
    num, slashes, den = m.group(1), m.group(2), m.group(3)
    if slashes:
        n = int(num) if num else 1
        return n / int(den) if den else n / (2 ** len(slashes))
    return float(num) if num else 1.0


def note_to_midi(letter, octmarks, accsym):
    pc = NOTE_PC[letter.upper()]
    if accsym == "^":
        pc += 1
    elif accsym == "_":
        pc -= 1
    pc %= 12
    octave = (4 if letter.isupper() else 5) + octmarks.count("'") - octmarks.count(",")
    return (octave + 1) * 12 + pc


TOKEN_RE = re.compile(r"""
    (?P<sym>"[^"]*")
  | (?P<chord>\[[^\]]*\](?:\d*(?:/{1,2}\d*|\d*/\d+)?)?)
  | (?P<note>\^?_?=?[A-Ga-g][,']*\d*(?:/{1,2}\d*|\d*/\d+)?)
  | (?P<rest>Z\d*|[zx]\d*(?:/{1,2}\d*|\d*/\d+)?)
  | (?P<bar>:\|:?|\|:?|\|\]|\[\||::)
  | (?P<tie>-)
  | (?P<other>.)
""", re.X)


class VoiceState:
    def __init__(self):
        self.beat = 0.0
        self.measure_acc = {}
        self.pending_tie = False
        self.events = []
        self.chords = []


def parse_voice_line(line, st, keyacc, unit_beats, meter_beats):
    line = re.sub(r"![^!]*!|\+[^+]*\+", " ", line)
    line = re.sub(r"\{[^}]*\}", " ", line)
    line = re.sub(r"\[[A-Za-z]:[^\]]*\]", " ", line)
    line = line.replace("(", " ").replace(")", " ")
    for m in TOKEN_RE.finditer(line):
        if m.group("sym"):
            st.chords.append((st.beat, m.group("sym")[1:-1]))
            continue
        if m.group("bar"):
            st.measure_acc = {}
            continue
        if m.group("tie"):
            st.pending_tie = True
            continue
        r = m.group("rest")
        if r:
            if r[0] == "Z":
                n = int(r[1:]) if r[1:] else 1
                st.beat += n * meter_beats
            else:
                st.beat += parse_duration(r[1:]) * unit_beats
            st.pending_tie = False
            continue
        c = m.group("chord")
        if c:
            inner, spec = c[1:].split("]")[0], c.split("]")[1]
            dur = parse_duration(spec) * unit_beats
            for s in re.findall(r"\^?_?=?[A-Ga-g][,']*", inner):
                mm = re.match(r"(\^|_|=)?([A-Ga-g])([,']*)", s)
                accsym = mm.group(1) or st.measure_acc.get(mm.group(2).upper(), keyacc.get(mm.group(2).upper(), ""))
                if mm.group(1):
                    st.measure_acc[mm.group(2).upper()] = mm.group(1)
                st.events.append((note_to_midi(mm.group(2), mm.group(3), accsym), st.beat, dur))
            st.beat += dur
            st.pending_tie = False
            continue
        n = m.group("note")
        if not n:
            continue
        mm = re.match(r"(\^|_|=)?([A-Ga-g])([,']*)(\d*)(/{1,2}\d*|\d*/\d+)?$", n)
        accsym, letter, octmarks, num, frac = mm.groups()
        dur = parse_duration((num or "") + (frac or "")) * unit_beats
        acc = accsym or st.measure_acc.get(letter.upper(), keyacc.get(letter.upper(), ""))
        if accsym:
            st.measure_acc[letter.upper()] = accsym
        midi = note_to_midi(letter, octmarks, acc)
        if st.pending_tie and st.events and st.events[-1][0] == midi:
            pm, ps, pd = st.events[-1]
            st.events[-1] = (pm, ps, pd + dur)
        else:
            st.events.append((midi, st.beat, dur))
        st.beat += dur
        st.pending_tie = False


def parse_abc(text):
    headers, states, order, sections, counts = {}, {}, [], [], {}
    cur, keyacc, unit_beats, meter_beats, qpm = "1", {}, 0.5, 4.0, 120.0

    def touch(vid):
        if vid not in states:
            states[vid] = VoiceState()
            order.append(vid)
        return states[vid]

    for raw in text.splitlines():
        if raw.lstrip().startswith("%"):
            label = raw.lstrip().lstrip("%").strip().lower()
            if label:
                pos = max((s.beat for s in states.values()), default=0.0)
                counts[label] = counts.get(label, 0) + 1
                sections.append({"label": label, "index": counts[label], "start_beat": pos})
            continue
        line = raw.split("%", 1)[0].rstrip()
        if not line.strip():
            continue
        mh = re.match(r"^([A-Za-z]):\s*(.*)$", line)
        if mh:
            f, val = mh.group(1), mh.group(2)
            if f == "V":
                vid = (val.split() or ["1"])[0]
                touch(vid)
                cur = vid
                continue
            headers[f] = val
            if f == "K":
                keyacc = key_accidentals(val)
            elif f == "L":
                ln, ld = val.split("/") if "/" in val else (val, "1")
                unit_beats = float(ln) / float(ld) * 4.0
            elif f == "M":
                mm = re.match(r"(\d+)/(\d+)", val)
                if mm:
                    meter_beats = int(mm.group(1)) * 4.0 / int(mm.group(2))
            elif f == "Q":
                qpm = parse_qpm(val, unit_beats)
            continue
        parse_voice_line(line, touch(cur), keyacc, unit_beats, meter_beats)

    total = max((s.beat for s in states.values()), default=0.0)
    for i, sec in enumerate(sections):
        sec["end_beat"] = sections[i + 1]["start_beat"] if i + 1 < len(sections) else total
    for sec in sections:
        sec["start_sec"] = sec["start_beat"] * 60.0 / qpm
        sec["end_sec"] = sec["end_beat"] * 60.0 / qpm
        sec["voices"] = sorted({vid for vid, s in states.items()
                                if any(e[1] < sec["end_beat"] and e[1] + e[2] > sec["start_beat"] and _not_rest(e)
                                       for e in s.events)})
        sec["chords"] = _dedup([c for c in _all_chords(states) if sec["start_beat"] <= c[0] < sec["end_beat"]])
    voices = {vid: st.events for vid, st in states.items()}
    meta = {"unit_beats": unit_beats, "meter_beats": meter_beats, "qpm": qpm,
            "keyacc": keyacc, "total_beat": total, "total_sec": total * 60.0 / qpm}
    return headers, voices, order, meta, sections


def _not_rest(e):
    return True


def _all_chords(states):
    out = []
    for st in states.values():
        out += st.chords
    return sorted(out)


def _dedup(chords):
    out = []
    for beat, sym in chords:
        if not out or out[-1][1] != sym:
            out.append((round(beat, 3), sym))
    return [s for _, s in out]


def synth_window(events, start_beat, dur_beats, qpm, path, gain=0.20):
    spb = 60.0 / qpm
    n = max(1, int(dur_beats * spb * SR))
    buf = [0.0] * n
    atk = max(1, int(0.006 * SR))
    rel = max(1, int(0.08 * SR))
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
            buf[i] += g * env * (math.sin(ph) + 0.5 * math.sin(2 * ph) + 0.25 * math.sin(3 * ph))
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


def merge(voices, order, which="all"):
    out = []
    for vid in order:
        if which in ("all", vid):
            out += voices.get(vid, [])
    return out


def find_section(sections, spec):
    """spec = 'chorus' or 'chorus#2'. Returns section dict or None."""
    name, _, idx = spec.partition("#")
    idx = int(idx) if idx else 1
    for sec in sections:
        if sec["label"] == name.strip().lower() and sec["index"] == idx:
            return sec
    return None


def tonic_pc(keystr):
    m = re.match(r"\s*([A-Ga-g])([#b]?)", keystr or "C")
    return (NOTE_PC[m.group(1).upper()]
            + (1 if m.group(2) == "#" else -1 if m.group(2) == "b" else 0)) % 12


def transpose_shift(src_key, target_key):
    d = (tonic_pc(target_key) - tonic_pc(src_key)) % 12
    return d - 12 if d > 6 else d


def to_notes(events, qpm, time_scale=1.0, semis=0):
    """Events (beats) -> absolute-time notes (seconds), transposed/stretched."""
    k = 60.0 / qpm * time_scale
    return [(midi + semis, s * k, d * k) for midi, s, d in events]


def synth_notes(notes, total_sec, path, gain=0.20):
    """Seconds-based synth: pass qpm=60 so synth_window's "beats" are seconds."""
    return synth_window(notes, 0.0, total_sec, 60.0, path, gain=gain)


# ---- MIDI + SoundFont rendering (no third-party deps) -----------------------
DIV = 480


def _vlq(n):
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
            t0 = int(round(st * qpm / 60 * DIV))
            t1 = int(round((st + du) * qpm / 60 * DIV))
            v = max(1, min(127, int(vel)))
            ev.append((t0, bytes([0x90 | ch, midi & 0x7F, v])))
            ev.append((t1, bytes([0x80 | ch, midi & 0x7F, 0])))
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
    import glob
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
    import shutil
    return shutil.which("fluidsynth") is not None


def render_soundfont(midi_path, wav_path, soundfont, rate=44100):
    import subprocess
    r = subprocess.run(["fluidsynth", "-ni", "-F", wav_path, "-r", str(rate),
                        soundfont, midi_path], capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(wav_path):
        raise RuntimeError(f"fluidsynth failed: {r.stderr.strip()[:300]}")
    return wav_path


def notes_to_wav(notes, total_sec, out, qpm=120.0, engine="auto", program=0, sf=None):
    """Render notes to WAV. engine: auto|soundfont|synth.
    notes may be (midi,start_s,dur_s) or (midi,start_s,dur_s,gain)."""
    sf = sf or find_soundfont()
    if engine in ("auto", "soundfont", "sf") and sf and fluidsynth_available():
        midi_notes = [(m, s, d, max(1, min(127, int(20 + 105 * (n[3] if len(n) > 3 else 1.0)))))
                      for n in notes for m, s, d in [(n[0], n[1], n[2])]]
        write_midi([{"channel": 0, "program": program, "notes": midi_notes}], out + ".mid", qpm)
        render_soundfont(out + ".mid", out, sf)
        return out, "soundfont"
    synth_notes([(n[0], n[1], n[2]) + ((n[3],) if len(n) > 3 else ()) for n in notes], total_sec, out)
    return out, "synth"
