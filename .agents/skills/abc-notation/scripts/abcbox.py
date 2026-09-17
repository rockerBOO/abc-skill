#!/usr/bin/env python3
"""Session CLI: content handles, structure map, playback, volume.

Commands: send, sections, play, render, replay, stop, status, volume.
<ref> = handle id, file path, or '-' for stdin.
"""
import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import abclib  # noqa: E402

CACHE = "/tmp/abc-skill"
PIDFILE = "/tmp/abc-skill-play.pid"
LASTFILE = "/tmp/abc-skill-last"
VOLFILE = "/tmp/abc-skill-volume"
DEFAULT_SECONDS = 5.0
DEFAULT_VOLUME = 100


def opt(args, name, default=None):
    if name in args:
        i = args.index(name)
        return args[i + 1]
    return default


def load_text(ref):
    """Resolve a ref (handle id, path, '-') to ABC text. Returns (text, source)."""
    if ref == "-":
        return sys.stdin.read(), "stdin"
    if os.path.exists(ref):
        with open(ref) as f:
            return f.read(), ref
    p = os.path.join(CACHE, ref + ".abc")
    if os.path.exists(p):
        with open(p) as f:
            return f.read(), p
    if os.path.isdir(CACHE):
        hits = [f for f in os.listdir(CACHE) if f.startswith(ref) and f.endswith(".abc")]
        if len(hits) == 1:
            full = os.path.join(CACHE, hits[0])
            with open(full) as f:
                return f.read(), full
    raise SystemExit(f"unknown ref: {ref}")


def parse_ref(ref):
    text, _ = load_text(ref)
    return abclib.parse_abc(text)


def cmd_send():
    text = sys.stdin.read()
    os.makedirs(CACHE, exist_ok=True)
    hid = hashlib.sha1(text.encode()).hexdigest()[:12]
    path = os.path.join(CACHE, hid + ".abc")
    with open(path, "w") as f:
        f.write(text)
    headers, voices, order, meta, sections = abclib.parse_abc(text)
    print(json.dumps({
        "id": hid, "path": path, "voices": order,
        "key": headers.get("K"), "meter": headers.get("M"), "qpm": meta["qpm"],
        "total_sec": round(meta["total_sec"], 1),
        "sections": [{"name": s["label"], "n": s["index"],
                      "start": round(s["start_sec"], 1), "end": round(s["end_sec"], 1)}
                     for s in sections],
    }, indent=2))


def cmd_sections(ref):
    headers, voices, order, meta, sections = parse_ref(ref)
    print(f"# {headers.get('T') or 'untitled'}  key={headers.get('K')} "
          f"meter={headers.get('M')} qpm={meta['qpm']:g} "
          f"len={meta['total_sec']:.1f}s voices={order}")
    print(f"{'#':>2} {'section':<16} {'start':>7} {'end':>7}  {'voices':<20} chords")
    for s in sections:
        tag = f"{s['label']}#{s['index']}"
        print(f"{s['index']:>2} {tag:<16} {s['start_sec']:>7.1f} {s['end_sec']:>7.1f}  "
              f"{','.join(s['voices']):<20} {' '.join(s['chords'][:8])}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "send":
        cmd_send()
    elif cmd == "sections":
        cmd_sections(args[0])
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
