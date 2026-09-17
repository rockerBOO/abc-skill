import pytest

from abclib import (apply_fade, find_section, merge, parse_abc, select_range,
                    to_notes, tonic_pc, transpose_shift)

ABC = ("X:1\nM:4/4\nL:1/4\nK:G\n"
       "% intro\nV: A\nC D E F|\nV: B\nZ|\n"
       "% chorus\nV: A\nG A B c|\nV: B\nc B A G|\n")


def _parsed():
    return parse_abc(ABC)


def test_find_section_and_occurrence():
    _, _, _, _, sections = _parsed()
    assert find_section(sections, "chorus")["index"] == 1
    assert find_section(sections, "chorus#1") is not None
    assert find_section(sections, "nope") is None


def test_select_section_and_after():
    _, _, _, meta, sections = _parsed()
    s, e = select_range(meta, sections, section="chorus")
    assert (s, e) == (4.0, 8.0)
    s, e = select_range(meta, sections, after="intro")
    assert (s, e) == (4.0, 8.0)


def test_select_seconds_default_and_full():
    _, _, _, meta, sections = _parsed()
    s, e = select_range(meta, sections, start=0.0)      # default 5s at qpm
    assert e - s == pytest.approx(5.0, abs=0.1) or e == meta["total_beat"]
    s, e = select_range(meta, sections, section="chorus", full=True)
    assert (s, e) == (4.0, 8.0)
    with pytest.raises(KeyError):
        select_range(meta, sections, section="missing")


def test_tonic_and_transpose():
    assert tonic_pc("G") == 7
    assert tonic_pc("Bb") == 10
    assert transpose_shift("G", "F") == -2
    assert transpose_shift("F", "G") == 2
    assert transpose_shift("F", "F") == 0


def test_merge():
    _, voices, order, _, _ = _parsed()
    assert len(merge(voices, order, "all")) == 12
    assert len(merge(voices, order, "A")) == 8
    assert len(merge(voices, order, "B")) == 4


def test_to_notes_transpose_and_stretch():
    events = [(60, 0.0, 1.0)]
    assert to_notes(events, qpm=60, time_scale=1.0, semis=0) == [(60, 0.0, 1.0)]
    assert to_notes(events, qpm=60, time_scale=0.5, semis=-2) == [(58, 0.0, 0.5)]


def test_apply_fade():
    notes = [(60, 0.0, 1.0), (62, 5.0, 1.0)]
    out = apply_fade(notes, fade_in=2.0, fade_out=2.0, total=6.0)
    assert out[0][3] == 0.0            # at t=0, fade-in gives gain 0
    assert out[1][3] == pytest.approx(0.5, abs=0.01)  # t=5, 1s to end over 2s fade
