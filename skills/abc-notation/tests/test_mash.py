import pytest

from mash import plan_mash


def test_transposes_b_into_a_key():
    _, plan = plan_mash(key_a="F", key_b="G", qpm_a=60, qpm_b=160,
                        events_a=[(60, 0.0, 1.0)], events_b=[(67, 0.0, 1.0)],
                        target_key="F")
    assert plan["A"]["shift"] == 0
    assert plan["B"]["shift"] == -2


def test_seq_offsets_b_by_a_length():
    notes, plan = plan_mash(key_a="C", key_b="C", qpm_a=120, qpm_b=120,
                            events_a=[(60, 0.0, 2.0)], events_b=[(64, 0.0, 1.0)],
                            mode="seq", xfade=0.0, target_qpm=60)
    b = [n for n in notes if n[0] == 64][0]
    assert b[1] == pytest.approx(2.0)
    assert plan["total_s"] == pytest.approx(3.0)


def test_xfade_overlaps():
    notes, plan = plan_mash(key_a="C", key_b="C", qpm_a=120, qpm_b=120,
                            events_a=[(60, 0.0, 4.0)], events_b=[(64, 0.0, 1.0)],
                            mode="seq", xfade=1.0, target_qpm=60)
    b = [n for n in notes if n[0] == 64][0]
    assert b[1] == pytest.approx(3.0)


def test_layer_starts_both_at_zero():
    notes, plan = plan_mash(key_a="C", key_b="C", qpm_a=120, qpm_b=120,
                            events_a=[(60, 0.0, 1.0)], events_b=[(64, 0.0, 1.0)],
                            mode="layer")
    starts = {n[0]: n[1] for n in notes}
    assert starts[60] == 0.0 and starts[64] == 0.0


def test_gains_scale_note_velocity_gain():
    notes, _ = plan_mash(key_a="C", key_b="C", qpm_a=120, qpm_b=120,
                         events_a=[(60, 0.0, 1.0)], events_b=[(64, 0.0, 1.0)],
                         mode="layer", a_gain=0.5, b_gain=1.0)
    a = [n for n in notes if n[0] == 60][0]
    assert a[3] == pytest.approx(0.5)


def test_tempo_normalization():
    # source at 60 qpm played at 120 -> durations halve
    notes, _ = plan_mash(key_a="C", key_b="C", qpm_a=60, qpm_b=120,
                         events_a=[(60, 0.0, 2.0)], events_b=[(64, 0.0, 1.0)],
                         target_qpm=120, mode="layer")
    a = [n for n in notes if n[0] == 60][0]
    assert a[2] == pytest.approx(1.0)


def test_slice_section_clamps_boundaries(monkeypatch):
    import abcbox as B
    from mash import slice_section

    sections = [{"label": "chorus", "index": 1, "start_beat": 4.0, "end_beat": 8.0}]
    voices = {"A": [(60, 3.0, 2.0), (62, 7.0, 3.0)]}  # first crosses start, second crosses end
    monkeypatch.setattr(B, "parse_ref",
                        lambda ref: ({"K": "C"}, voices, ["A"], {"qpm": 120.0}, sections))
    _h, _m, _sec, ev = slice_section("x", "chorus", "all")
    assert ev[0][1] == 0.0 and abs(ev[0][2] - 1.0) < 1e-9   # clamped start, truncated
    assert ev[1][1] == 3.0 and abs(ev[1][2] - 1.0) < 1e-9   # truncated at section end
