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
