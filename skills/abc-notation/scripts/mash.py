#!/usr/bin/env python3
"""Mash two ABC sources with explicit, reversible parameters."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import abclib as L  # noqa: E402
import abcbox as B  # noqa: E402
import render  # noqa: E402


def opt(args, name, default=None):
    if name in args:
        return args[args.index(name) + 1]
    return default


def slice_section(ref, sel, voice):
    headers, voices, order, meta, sections = B.parse_ref(ref)
    sec = L.find_section(sections, sel)
    if not sec:
        raise SystemExit(f"no section {sel} in {ref}")
    ev = L.merge(voices, order, voice)
    out = []
    for m, s, d in ev:
        if s < sec["end_beat"] and s + d > sec["start_beat"]:
            ns = max(s, sec["start_beat"])
            ne = min(s + d, sec["end_beat"])
            out.append((m, ns - sec["start_beat"], ne - ns))
    return headers, meta, sec, out


def plan_mash(*, key_a, key_b, qpm_a, qpm_b, events_a, events_b,
              target_key=None, target_qpm=120.0, mode="seq", xfade=0.0,
              a_gain=1.0, b_gain=1.0, a_section="chorus#1", b_section="chorus#1"):
    """Pure planner: returns (notes, plan). notes are (midi, start_s, dur_s, gain)."""
    tkey = target_key or key_a
    sa = L.transpose_shift(key_a, tkey)
    sb = L.transpose_shift(key_b, tkey)
    na = L.to_notes(events_a, qpm_a, time_scale=qpm_a / target_qpm, semis=sa)
    nb = L.to_notes(events_b, qpm_b, time_scale=qpm_b / target_qpm, semis=sb)
    la = max((s + d for _, s, d in na), default=0.0)
    lb = max((s + d for _, s, d in nb), default=0.0)
    if mode == "seq":
        off = max(0.0, la - xfade)
        na = [(m, s, d, g * a_gain) for m, s, d, g in L.apply_fade(na, 0.0, xfade, la)]
        nb = [(m, s, d, g * b_gain) for m, s, d, g in L.apply_fade(nb, xfade, 0.0, lb)]
        notes = na + [(m, s + off, d, g) for m, s, d, g in nb]
        total = max(la, off + lb)
    else:
        na = [(m, s, d, g * a_gain) for m, s, d, g in L.apply_fade(na, 0.0, 0.0, la)]
        nb = [(m, s, d, g * b_gain) for m, s, d, g in L.apply_fade(nb, 0.0, 0.0, lb)]
        notes = na + nb
        total = max(la, lb)
    plan = {
        "target_key": tkey, "target_qpm": target_qpm, "mode": mode, "xfade": xfade,
        "a_gain": a_gain, "b_gain": b_gain, "volume": B.current_volume(),
        "A": {"section": a_section, "key": key_a, "shift": sa,
              "len_s": round(la, 2), "notes": len(events_a)},
        "B": {"section": b_section, "key": key_b, "shift": sb,
              "len_s": round(lb, 2), "notes": len(events_b)},
        "total_s": round(total, 2),
    }
    return notes, plan


def main():
    a, b = sys.argv[1], sys.argv[2]
    args = sys.argv[3:]
    a_sec = opt(args, "--a-section", "chorus#1")
    b_sec = opt(args, "--b-section", "chorus#1")
    target_key = opt(args, "--key")
    target_qpm = float(opt(args, "--qpm", 120))
    mode = opt(args, "--mode", "seq")
    xfade = float(opt(args, "--xfade", 0.0))
    ga = float(opt(args, "--a-gain", 1.0))
    gb = float(opt(args, "--b-gain", 1.0))
    engine = opt(args, "--engine", "auto")
    program = int(opt(args, "--program", "0"))

    ha, ma, sa, ea = slice_section(a, a_sec, opt(args, "--a-voice", "all"))
    hb, mb, sb_, eb = slice_section(b, b_sec, opt(args, "--b-voice", "all"))
    notes, plan = plan_mash(
        key_a=ha.get("K", "C"), key_b=hb.get("K", "C"),
        qpm_a=ma["qpm"], qpm_b=mb["qpm"], events_a=ea, events_b=eb,
        target_key=target_key, target_qpm=target_qpm, mode=mode, xfade=xfade,
        a_gain=ga, b_gain=gb, a_section=a_sec, b_section=b_sec)
    print(json.dumps(plan, indent=2))

    total = plan["total_s"]
    start = float(opt(args, "--start", 0.0))
    full = "--full" in args
    seconds = float(opt(args, "--seconds", 5.0))
    end = total if full else min(total, start + seconds)
    clipped = []
    for m, s, d, g in notes:
        ns, ne = max(s, start), min(s + d, end)
        if ns < ne:
            clipped.append((m, ns - start, ne - ns, g))
    out = "/tmp/abc-skill-mash.wav"
    rendered, used = render.notes_to_wav(clipped, end - start, out, qpm=target_qpm,
                                         engine=engine, program=program)
    p, _ = B.start_playback(rendered, {"window": [start, end], "engine_used": used,
                                       "plan": plan})
    print(json.dumps({"ok": True, "pid": p.pid, "window": [round(start, 2), round(end, 2)],
                      "engine_used": used, "volume": B.current_volume(),
                      "playing": rendered}))


if __name__ == "__main__":
    main()
