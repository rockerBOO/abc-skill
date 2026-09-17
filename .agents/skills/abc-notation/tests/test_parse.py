from abclib import parse_abc


def test_scale_pitches():
    _, voices, order, _, _ = parse_abc("X:1\nM:4/4\nL:1/4\nK:C\nC D E F|G A B c|")
    assert order == ["1"]
    assert [e[0] for e in voices["1"]] == [60, 62, 64, 65, 67, 69, 71, 72]


def test_octave_marks():
    _, voices, _, _, _ = parse_abc("X:1\nM:4/4\nL:1/4\nK:C\nC, C c c'|")
    assert [e[0] for e in voices["1"]] == [48, 60, 72, 84]


def test_key_signature_applied():
    _, voices, _, _, _ = parse_abc("X:1\nM:4/4\nL:1/4\nK:G\nF G|")
    assert [e[0] for e in voices["1"]] == [66, 67]


def test_accidental_override_and_measure_scope():
    _, voices, _, _, _ = parse_abc("X:1\nM:4/4\nL:1/4\nK:C\n=F F |=F F|")
    assert [e[0] for e in voices["1"]] == [65, 65, 65, 65]


def test_durations_and_rests():
    _, voices, _, meta, _ = parse_abc("X:1\nM:4/4\nL:1/4\nK:C\nC2 z2|C/2 C/2 z3|")
    assert meta["unit_beats"] == 1.0
    assert [round(e[2], 3) for e in voices["1"]] == [2.0, 0.5, 0.5]
    # rest advances time: third note starts after C2 (2) + z2 (2) = 4.0
    assert voices["1"][2][1] == 4.5


def test_tie_merges_notes():
    _, voices, _, _, _ = parse_abc("X:1\nM:4/4\nL:1/4\nK:C\nC- C2|")
    assert len(voices["1"]) == 1
    assert voices["1"][0][2] == 3.0


def test_multi_voice_and_sections():
    abc = ("X:1\nM:4/4\nL:1/4\nK:C\n"
           "% intro\nV: A\nC D E F|\nV: B\nZ|\n"
           "% chorus\nV: A\nG A B c|\nV: B\nc B A G|\n")
    headers, voices, order, meta, sections = parse_abc(abc)
    assert order == ["A", "B"]
    assert [s["label"] for s in sections] == ["intro", "chorus"]
    assert sections[0]["start_beat"] == 0.0
    assert sections[1]["start_beat"] == 4.0
    assert sections[0]["voices"] == ["A"]


def test_chords_captured():
    _, voices, _, meta, sections = parse_abc(
        'X:1\nM:4/4\nL:1/4\nK:C\n% verse\n"C"CEG z|')
    assert [e[0] for e in voices["1"]] == [60, 64, 67]
    assert sections[0]["chords"] == ["C"]
