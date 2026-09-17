"""ABC parsing, structure map, selection, and note utilities.

Stdlib only. Pitch convention: C = C4 = MIDI 60; lowercase c = C5;
',' lowers an octave, "'" raises.
"""
import re

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
    """Return {letter: '^'/'_'} implied by an ABC key signature string."""
    m = re.match(r"\s*([A-Ga-g])([#b]?)\s*([A-Za-z]*)", (keystr or "C").strip())
    if not m:
        return {}
    letter = m.group(1).upper()
    acc = m.group(2)
    mode = (m.group(3) or "major").lower()
    mode = {"maj": "major", "min": "minor", "m": "minor", "": "major"}.get(mode, mode)
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


DUR_RE = re.compile(r"(\d*)(/+)?(\d*)")


def parse_duration(spec):
    """ABC duration suffix -> multiplier of the default note length (L:)."""
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


def parse_qpm(q, unit_beats):
    """Quarter-notes-per-minute from a Q: header. unit_beats = L: in quarter beats."""
    m = re.search(r"(\d+)/(\d+)\s*=\s*(\d+)", q or "")
    if m:
        return int(m.group(3)) * (int(m.group(1)) / int(m.group(2))) * 4.0
    m2 = re.search(r"(\d+)", q or "")
    return (int(m2.group(1)) if m2 else 120) * unit_beats


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
                accsym = mm.group(1) or st.measure_acc.get(
                    mm.group(2).upper(), keyacc.get(mm.group(2).upper(), ""))
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
    all_chords = sorted((c for st in states.values() for c in st.chords))
    for sec in sections:
        sec["start_sec"] = sec["start_beat"] * 60.0 / qpm
        sec["end_sec"] = sec["end_beat"] * 60.0 / qpm
        sec["voices"] = sorted({vid for vid, s in states.items()
                                if any(e[1] < sec["end_beat"] and e[1] + e[2] > sec["start_beat"]
                                       for e in s.events)})
        sec["chords"] = _dedup_chords([c for c in all_chords
                                       if sec["start_beat"] <= c[0] < sec["end_beat"]])
    voices = {vid: st.events for vid, st in states.items()}
    meta = {"unit_beats": unit_beats, "meter_beats": meter_beats, "qpm": qpm,
            "keyacc": keyacc, "total_beat": total, "total_sec": total * 60.0 / qpm}
    return headers, voices, order, meta, sections


def _dedup_chords(chords):
    out = []
    for _beat, sym in chords:
        if not out or out[-1] != sym:
            out.append(sym)
    return out
