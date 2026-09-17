#!/usr/bin/env python3
"""
THROWAWAY SPIKE - not production code.

Question: can we take ABC, pull a piece out of it, and actually play it back
to the user so they can give feedback?

Pipeline: ABC text -> note events -> WAV (stdlib synth) -> play via paplay.
No external ABC tools, no soundfonts, no third-party deps.

Also prints a compact "normalized" view of the extracted phrase, which is the
seed of the representation the model would reason over.
"""
import math
import re
import struct
import subprocess
import sys
import wave

SR = 44100

NOTE_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
SHARP_ORDER = ["F", "C", "G", "D", "A", "E", "B"]
FLAT_ORDER = ["B", "E", "A", "D", "G", "C", "F"]
MAJOR_SIG = {  # major tonic name -> (# sharps>0 / # flats<0)
    "C": 0, "G": 1, "D": 2, "A": 3, "E": 4, "B": 5, "F#": 6, "C#": 7,
    "F": -1, "Bb": -2, "Eb": -3, "Ab": -4, "Db": -5, "Gb": -6, "Cb": -7,
}
# semitone offset to the relative major for each mode
MODE_OFFSET = {"major": 0, "ionian": 0, "dorian": 10, "phrygian": 8, "lydian": 7,
               "mixolydian": 5, "minor": 3, "aeolian": 3, "locrian": 1}
PC_TO_MAJOR_NAME = {0: "C", 1: "Db", 2: "D", 3: "Eb", 4: "E", 5: "F",
                    6: "F#", 7: "G", 8: "Ab", 9: "A", 10: "Bb", 11: "B"}


def key_accidentals(keystr):
    """Return {letter: '^'/'_'} implied by the key signature."""
    m = re.match(r"\s*([A-Ga-g])([#b]?)\s*([A-Za-z]*)", keystr.strip())
    letter = m.group(1).upper()
    acc = m.group(2)
    mode = (m.group(3) or "major").lower()
    aliases = {"maj": "major", "min": "minor", "": "major"}
    mode = aliases.get(mode, mode)
    pc = (NOTE_PC[letter] + (1 if acc == "#" else -1 if acc == "b" else 0)) % 12
    rel = (pc + MODE_OFFSET.get(mode, 0)) % 12
    sig = MAJOR_SIG[PC_TO_MAJOR_NAME[rel]]
    out = {}
    if sig > 0:
        for L in SHARP_ORDER[:sig]:
            out[L] = "^"
    elif sig < 0:
        for L in FLAT_ORDER[:-sig]:
            out[L] = "_"
    return out


DUR_RE = re.compile(r"(\d*)(/+)?(\d*)")
NOTE_RE = re.compile(r"^(\^|_|=)?([A-Ga-g])([,']*)(\d*)(/{1,2}\d*|\d*/\d+)?$")


def parse_duration(spec):
    """ABC duration suffix -> multiplier of the default note length."""
    if not spec:
        return 1.0
    m = DUR_RE.fullmatch(spec)
    if not m:
        return 1.0
    num, slashes, den = m.group(1), m.group(2), m.group(3)
    if slashes:
        # forms: '/', '//', '3/', '/2', '3/2'
        n = int(num) if num else 1
        if den:
            return n / int(den)
        return n / (2 ** len(slashes))
    return float(num) if num else 1.0


def note_to_midi(letter, octmarks, keyacc):
    """ABC note letter + octave marks + key sig -> (midi, pc)."""
    pc_base = NOTE_PC[letter.upper()]
    keyacc_letter = keyacc.get(letter.upper(), "")
    midi_pc = (pc_base + (1 if keyacc_letter == "^" else -1 if keyacc_letter == "_" else 0)) % 12
    octave = 4 if letter.isupper() else 5
    octave += octmarks.count("'") - octmarks.count(",")
    midi = (octave + 1) * 12 + midi_pc
    return midi


def parse_abc(text):
    """Parse enough ABC for a spike. Returns (headers, events)."""
    headers, body_lines = {}, []
    for raw in text.splitlines():
        line = raw.split("%", 1)[0].rstrip()
        if not line:
            continue
        m = re.match(r"^([A-Za-z]):\s*(.*)$", line)
        if m and m.group(1) in "XTM LQKRVUWwZOISNPHBCFDEAG":
            headers[m.group(1)] = m.group(2)
            if m.group(1) == "K":
                # anything after K: on the same line starting with the key is body
                rest = line.split(":", 1)[1].strip()
                tokens = rest.split(None, 1)
                if len(tokens) > 1:
                    body_lines.append(tokens[1])
            continue
        body_lines.append(line)

    keyacc = key_accidentals(headers.get("K", "C"))
    unit = parse_duration("" if "/" not in headers.get("L", "1/8") else headers["L"].split("/", 0)[0])  # placeholder
    # default note length as fraction of a whole note
    lspec = headers.get("L", "1/8")
    ln, ld = lspec.split("/") if "/" in lspec else (lspec, "1")
    unit_whole = float(ln) / float(ld)
    unit_beats = unit_whole * 4.0  # quarter-note beats

    events = []           # (midi, start_beat, dur_beats)
    beat = 0.0
    measure_acc = {}
    token_re = re.compile(r"""
        (?P<chord>\[[^\]]*\](?:\d*(?:/\d+)?)?)
      | (?P<note>\^?_?=?[A-Ga-g][,']*\d*(?:/{1,2}\d*|\d*/\d+)?)
      | (?P<rest>[zx]\d*(?:/{1,2}\d*|\d*/\d+)?)
      | (?P<bar>:\|:?|\|:?|\|\]|\[\||::)
      | (?P<tie>-)
      | (?P<other>.)
    """, re.X)

    for line in body_lines:
        # strip things we don't model in the spike
        line = re.sub(r'"[^"]*"', " ", line)        # chord symbols
        line = re.sub(r"![^!]*!|\+[^+]*\+", " ", line)  # decorations
        line = re.sub(r"\{[^}]*\}", " ", line)       # grace notes
        line = re.sub(r"\[[A-Za-z]:[^\]]*\]", " ", line)  # inline fields
        line = line.replace("(", " ").replace(")", " ")
        prev_tie = False
        for m in token_re.finditer(line):
            if m.group("bar"):
                measure_acc = {}
                continue
            if m.group("tie"):
                # extend the duration of the last note events
                if events:
                    last = events[-1]
                    prev_tie = True
                continue
            if m.group("other") or m.group("rest"):
                if m.group("rest"):
                    spec = m.group("rest")[1:]
                    rest_beats = parse_duration(spec) * unit_beats
                    beat += rest_beats
                prev_tie = False
                continue
            if m.group("chord"):
                inner = m.group("chord")[1:].split("]")[0]
                spec = m.group("chord").split("]")[1]
                dur = parse_duration(spec) * unit_beats
                subs = re.findall(r"\^?_?=?[A-Ga-g][,']*", inner)
                midis = []
                for s in subs:
                    mm = re.match(r"(\^|_|=)?([A-Ga-g])([,']*)", s)
                    pc = NOTE_PC[mm.group(2).upper()]
                    accsym = mm.group(1) or measure_acc.get(mm.group(2).upper(), keyacc.get(mm.group(2).upper(), ""))
                    if mm.group(1):
                        measure_acc[mm.group(2).upper()] = mm.group(1)
                    midis.append(note_to_midi(mm.group(2), mm.group(3), {mm.group(2).upper(): accsym} if accsym else {}))
                for mi in midis:
                    events.append((mi, beat, dur))
                beat += dur
                prev_tie = False
                continue
            # a plain note
            mm = NOTE_RE.match(m.group("note"))
            if not mm:
                prev_tie = False
                continue
            accsym, letter, octmarks, num, frac = mm.groups()
            spec = (num or "") + (frac or "")
            dur = parse_duration(spec) * unit_beats
            acc = accsym or measure_acc.get(letter.upper(), keyacc.get(letter.upper(), ""))
            if accsym:
                measure_acc[letter.upper()] = accsym
            midi = note_to_midi(letter, octmarks, {letter.upper(): acc} if acc else {})
            if prev_tie and events:
                # merge into previous event
                pm, ps, pd = events[-1]
                if pm == midi:
                    events[-1] = (pm, ps, pd + dur)
                else:
                    events.append((midi, beat, dur))
            else:
                events.append((midi, beat, dur))
            beat += dur
            prev_tie = False

    return headers, events, unit_beats


def synth(events, total_beats, qpm, path):
    spb = 60.0 / qpm
    n = int((total_beats * spb + 0.6) * SR)
    buf = [0.0] * n
    atk = max(1, int(0.006 * SR))
    rel = max(1, int(0.07 * SR))
    for midi, start_b, dur_b in events:
        f = 440.0 * 2 ** ((midi - 69) / 12.0)
        s0 = int(start_b * spb * SR)
        length = int(dur_b * spb * SR)
        for i in range(length):
            idx = s0 + i
            if idx >= n:
                break
            t = i / SR
            env = min(1.0, i / atk) if i < atk else 1.0
            if i > length - rel:
                env *= max(0.0, (length - i) / rel)
            env *= math.exp(-1.6 * t)
            ph = 2 * math.pi * f * t
            s = math.sin(ph) + 0.5 * math.sin(2 * ph) + 0.25 * math.sin(3 * ph)
            buf[idx] += 0.20 * env * s
    frames = bytearray()
    for v in buf:
        v = max(-1.0, min(1.0, v))
        frames += struct.pack("<h", int(v * 32000))
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(bytes(frames))
    return path


def play(path):
    try:
        subprocess.run(["paplay", path], check=True)
    except Exception:
        subprocess.run(["ffplay", "-autoexit", "-nodisp", "-loglevel", "quiet", path])


def qpm_from_headers(h):
    q = h.get("Q", "120")
    m = re.search(r"(?:(\d+)/(\d+)\s*=\s*)?(\d+)", q)
    if m and m.group(1):
        note_whole = int(m.group(1)) / int(m.group(2))
        bpm = int(m.group(3))
        return bpm * note_whole * 4.0
    bpm = int(m.group(3)) if m else 120
    lspec = h.get("L", "1/8")
    ln, ld = lspec.split("/") if "/" in lspec else (lspec, "1")
    return bpm * (float(ln) / float(ld)) * 4.0


# ---- two public-domain tunes -------------------------------------------------
TWINKLE = """X:1
T:Twinkle Twinkle Little Star
M:4/4
L:1/4
K:C
C C G G | A A G2 | F F E E | D D C2 |
G G F F | E E D2 | G G F F | E E D2 |
C C G G | A A G2 | F F E E | D D C2 |
"""

ODE = """X:2
T:Ode to Joy
M:4/4
L:1/4
K:C
E E F G | G F E D | C C D E | E3/2 D/2 D2 |
E E F G | G F E D | C C D E | D3/2 C/2 C2 |
"""


def show(label, headers, events, unit_beats):
    print(f"\n== {label} ==")
    print(f"   key={headers.get('K')} meter={headers.get('M')} unit={unit_beats} beats qpm={qpm_from_headers(headers):.0f}")
    names = []
    for midi, s, d in events:
        step = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"][midi % 12]
        names.append(f"{step}{midi // 12 - 1}:{d:g}")
    print("   " + " ".join(names))


def main():
    for name, abc, measures in [("Twinkle (bars 1-4)", TWINKLE, 4), ("Ode to Joy (bars 1-4)", ODE, 4)]:
        headers, events, ub = parse_abc(abc)
        total = events[-1][1] + events[-1][2]
        # extract first `measures` bars (M numerator * measures beats, since M/4)
        beats_per_measure = 4.0
        cut = measures * beats_per_measure
        piece = [e for e in events if e[1] < cut]
        show(name, headers, piece, ub)
        out = f"spike/out/{name.split()[0].lower()}.wav"
        synth(piece, cut, qpm_from_headers(headers), out)
        print(f"   -> {out}")
        play(out)

    # a first taste of a "medley" mashup
    h1, e1, _ = parse_abc(TWINKLE)
    h2, e2, _ = parse_abc(ODE)
    a = [e for e in e1 if e[1] < 16]
    b = [e for e in e2 if e[1] < 16]
    merged = a + [(m, s + 16, d) for m, s, d in b]
    show("MEDLEY: Twinkle->Ode (sequential, same key)", h1, merged, 0.5)
    synth(merged, 32, 120, "spike/out/medley.wav")
    print("   -> spike/out/medley.wav")
    play("spike/out/medley.wav")


if __name__ == "__main__":
    main()
