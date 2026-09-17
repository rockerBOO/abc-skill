#!/usr/bin/env python3
"""
SPIKE mashup tool - ONE real attempt so we can test reasoning + feedback.

Model of the reasoning surface (these become the knobs):
  target key   -> each source transposed by nearest semitone shift
  target qpm   -> each source's absolute timing rescaled
  sections     -> what to take from each source
  mode         -> seq (medley) or layer (simultaneous)
  xfade        -> overlap at the seam
  window       -> which slice to audition (short by default)

Usage:
  mash.py A B --a-section chorus#1 --b-section chorus#1 --key F --qpm 120 \
          --mode seq --xfade 1.0 --start 16 --seconds 5
"""
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import abclib as L  # noqa: E402
import abcbox as B  # noqa: E402

PIDFILE = B.PIDFILE


def opt(args, name, default=None):
    if name in args:
        i = args.index(name)
        return args[i + 1]
    return default


def load(ref):
    text, _ = B.load_text(ref)
    return L.parse_abc(text)


def slice_section(ref, sel, voice):
    headers, voices, order, meta, sections = load(ref)
    sec = L.find_section(sections, sel)
    if not sec:
        raise SystemExit(f"no section {sel} in {ref}")
    ev = L.merge(voices, order, voice)
    ev = [(m, s - sec["start_beat"], d) for m, s, d in ev
          if s < sec["end_beat"] and s + d > sec["start_beat"]]
    return headers, meta, sec, ev


def to_notes(ev, qpm, target_qpm, semis):
    return L.to_notes(ev, qpm, time_scale=qpm / target_qpm, semis=semis)


def apply_fade(notes, fade_in, fade_out, total):
    """Per-note gain for a linear crossfade (approx; long notes aren't split)."""
    out = []
    for m, s, d in notes:
        g = 1.0
        if fade_in > 0 and s < fade_in:
            g = min(g, s / fade_in)
        if fade_out > 0 and s > total - fade_out:
            g = min(g, (total - s) / fade_out)
        out.append((m, s, d, max(0.0, g)))
    return out


def main():
    a, b = sys.argv[1], sys.argv[2]
    args = sys.argv[3:]
    target_key = opt(args, "--key")
    target_qpm = float(opt(args, "--qpm", 120))
    mode = opt(args, "--mode", "seq")
    xfade = float(opt(args, "--xfade", 0.0))
    ga = float(opt(args, "--a-gain", 1.0))
    gb = float(opt(args, "--b-gain", 1.0))
    start = float(opt(args, "--start", 0.0))
    seconds = float(opt(args, "--seconds", 5.0))
    full = "--full" in args
    engine = opt(args, "--engine", "auto")
    program = int(opt(args, "--program", "0"))

    ha, ma, sa, ea = slice_section(a, opt(args, "--a-section", "chorus#1"), opt(args, "--a-voice", "all"))
    hb, mb, sb, eb = slice_section(b, opt(args, "--b-section", "chorus#1"), opt(args, "--b-voice", "all"))

    keyA = ha.get("K", "C")
    keyB = hb.get("K", "C")
    tkey = target_key or keyA
    semis_a = L.transpose_shift(keyA, tkey)
    semis_b = L.transpose_shift(keyB, tkey)

    notes_a = to_notes(ea, ma["qpm"], target_qpm, semis_a)
    notes_b = to_notes(eb, mb["qpm"], target_qpm, semis_b)
    len_a = max((s + d for _, s, d in notes_a), default=0.0)
    len_b = max((s + d for _, s, d in notes_b), default=0.0)

    if mode == "seq":
        off_b = max(0.0, len_a - xfade)
        notes_a = [(m, s, d, g * ga) for m, s, d, g in apply_fade(notes_a, 0.0, xfade, len_a)]
        notes_b = [(m, s, d, g * gb) for m, s, d, g in apply_fade(notes_b, xfade, 0.0, len_b)]
        merged = notes_a + [(m, s + off_b, d, g) for m, s, d, g in notes_b]
        total = max(len_a, off_b + len_b)
    else:  # layer
        notes_a = [(m, s, d, g * ga) for m, s, d, g in apply_fade(notes_a, 0.0, 0.0, len_a)]
        notes_b = [(m, s, d, g * gb) for m, s, d, g in apply_fade(notes_b, 0.0, 0.0, len_b)]
        merged = notes_a + notes_b
        total = max(len_a, len_b)

    plan = {
        "target_key": tkey, "target_qpm": target_qpm, "mode": mode, "xfade": xfade,
        "a_gain": ga, "b_gain": gb, "engine": engine, "program": program,
        "volume": B.current_volume(),
        "A": {"section": opt(args, "--a-section", "chorus#1"), "key": keyA,
              "shift": semis_a, "len_s": round(len_a, 2), "notes": len(notes_a)},
        "B": {"section": opt(args, "--b-section", "chorus#1"), "key": keyB,
              "shift": semis_b, "len_s": round(len_b, 2), "notes": len(notes_b)},
        "total_s": round(total, 2),
    }
    print(json.dumps(plan, indent=2))

    out = "/tmp/abc-skill-mash.wav"
    end = total if full else min(total, start + seconds)
    clipped = []
    for n in merged:
        m, s, d = n[0], n[1], n[2]
        g = n[3] if len(n) > 3 else 1.0
        ns, ne = max(s, start), min(s + d, end)
        if ns < ne:
            clipped.append((m, ns - start, ne - ns, g))
    rendered, used = L.notes_to_wav(clipped, end - start, out, qpm=target_qpm,
                                    engine=engine, program=program)

    if os.path.exists(PIDFILE):
        B.cmd_stop(quiet=True)
    p, _ = B.start_playback(rendered, {"window": [start, end], "engine_used": used, "plan": plan})
    print(json.dumps({"ok": True, "pid": p.pid, "window": [round(start, 2), round(end, 2)],
                      "engine_used": used, "volume": B.current_volume(),
                      "playing": rendered, "stop": "python spike/abcbox.py stop"}))


if __name__ == "__main__":
    main()
