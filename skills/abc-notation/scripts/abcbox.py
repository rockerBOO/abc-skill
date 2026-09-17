#!/usr/bin/env python3
"""Session CLI: content handles, structure map, playback, volume.

Commands: send, sections, play, render, replay, stop, status, volume.
<ref> = handle id, file path, or '-' for stdin.
"""
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import time

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


def current_volume():
    try:
        return max(0, min(200, int(open(VOLFILE).read().strip())))
    except Exception:
        return DEFAULT_VOLUME


def _sink_index(pid):
    """Find the PulseAudio sink-input index whose process id is `pid`."""
    out = subprocess.run(["pactl", "list", "sink-inputs"],
                         capture_output=True, text=True).stdout
    idx = None
    for line in out.splitlines():
        m = re.match(r"\s*Sink Input #(\d+)", line)
        if m:
            idx = m.group(1)
        if f'application.process.id = "{pid}"' in line and idx:
            return idx
    return None


def _apply_volume(pid, percent, tries=12):
    for _ in range(tries):
        idx = _sink_index(pid)
        if idx:
            subprocess.run(["pactl", "set-sink-input-volume", idx, f"{percent}%"], check=False)
            return idx
        time.sleep(0.1)
    return None


def start_playback(path, info=None):
    """Stop anything playing, then play `path` in the background."""
    cmd_stop(quiet=True)
    p = subprocess.Popen(["paplay", path], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    vol = current_volume()
    rec = {"pid": p.pid, "file": path, "started": time.time(), "volume": vol}
    if info:
        rec.update(info)
    with open(PIDFILE, "w") as f:
        json.dump(rec, f)
    with open(LASTFILE, "w") as f:
        f.write(path)
    rec["sink_input"] = _apply_volume(p.pid, vol)
    with open(PIDFILE, "w") as f:
        json.dump(rec, f)
    return p, rec


def cmd_volume(arg):
    vol = current_volume()
    if arg in ("mute", "unmute"):
        pass
    elif arg.startswith(("+", "-")):
        vol = max(0, min(200, vol + int(arg)))
    else:
        vol = max(0, min(200, int(str(arg).rstrip("%"))))
    with open(VOLFILE, "w") as f:
        f.write(str(vol))
    applied = None
    if os.path.exists(PIDFILE):
        info = json.load(open(PIDFILE))
        try:
            os.kill(info["pid"], 0)
            idx = _sink_index(info["pid"])
            if idx and arg == "mute":
                subprocess.run(["pactl", "set-sink-input-mute", idx, "1"], check=False)
            elif idx and arg == "unmute":
                subprocess.run(["pactl", "set-sink-input-mute", idx, "0"], check=False)
            applied = _apply_volume(info["pid"], vol)
        except OSError:
            pass
    print(json.dumps({"ok": True, "volume": vol, "live": applied is not None}))


def cmd_render(args):
    out = opt(args, "-o", "/tmp/abc-skill-clip.wav")
    path, sb, eb, meta = _render_range(args[0], args, out)
    print(json.dumps({"ok": True, "file": path,
                      "start_sec": round(sb * 60 / meta["qpm"], 2),
                      "end_sec": round(eb * 60 / meta["qpm"], 2)}))


def _render_range(ref, args, out):
    headers, voices, order, meta, sections = parse_ref(ref)
    sb, eb = abclib.select_range(
        meta, sections,
        section=opt(args, "--section"), after=opt(args, "--after"),
        from_=opt(args, "--from"), start=float(opt(args, "--start", 0.0)),
        seconds=float(opt(args, "--seconds", DEFAULT_SECONDS)),
        full="--full" in args)
    events = abclib.merge(voices, order, opt(args, "--voice", "all"))
    program = int(opt(args, "--program", "0"))
    notes = abclib.to_notes(events, meta["qpm"])
    start_sec, end_sec = sb * 60 / meta["qpm"], eb * 60 / meta["qpm"]
    clipped = []
    for m, s, d in notes:
        ns, ne = max(s, start_sec), min(s + d, end_sec)
        if ns < ne:
            clipped.append((m, ns - start_sec, ne - ns))
    import render
    path, _ = render.notes_to_wav(clipped, end_sec - start_sec, out, qpm=meta["qpm"],
                                  engine=opt(args, "--engine", "auto"), program=program)
    return path, sb, eb, meta


def cmd_play(args):
    out = "/tmp/abc-skill-clip.wav"
    path, sb, eb, meta = _render_range(args[0], args, out)
    p, _ = start_playback(path, {"start_sec": round(sb * 60 / meta["qpm"], 2),
                                 "end_sec": round(eb * 60 / meta["qpm"], 2)})
    print(json.dumps({"ok": True, "pid": p.pid, "playing": path,
                      "start_sec": round(sb * 60 / meta["qpm"], 2),
                      "end_sec": round(eb * 60 / meta["qpm"], 2),
                      "stop": "abcbox.py stop"}))
    if "--fg" in args:
        p.wait()


def cmd_replay():
    if not os.path.exists(LASTFILE):
        print(json.dumps({"ok": False, "reason": "nothing to replay yet"}))
        return
    path = open(LASTFILE).read().strip()
    if not os.path.exists(path):
        print(json.dumps({"ok": False, "reason": f"clip gone: {path}"}))
        return
    p, _ = start_playback(path)
    print(json.dumps({"ok": True, "pid": p.pid, "replaying": path}))


def cmd_stop(quiet=False):
    if not os.path.exists(PIDFILE):
        if not quiet:
            print(json.dumps({"ok": True, "stopped": False, "reason": "nothing playing"}))
        return
    try:
        info = json.load(open(PIDFILE))
        os.killpg(os.getpgid(info["pid"]), signal.SIGTERM)
    except Exception:
        try:
            os.kill(json.load(open(PIDFILE))["pid"], signal.SIGTERM)
        except Exception:
            pass
    os.remove(PIDFILE)
    if not quiet:
        print(json.dumps({"ok": True, "stopped": True}))


def cmd_status():
    if not os.path.exists(PIDFILE):
        print(json.dumps({"playing": False}))
        return
    info = json.load(open(PIDFILE))
    try:
        os.kill(info["pid"], 0)
        alive = True
    except OSError:
        alive = False
        os.remove(PIDFILE)
    print(json.dumps({"playing": alive, **info, "volume": current_volume()}))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "send":
        cmd_send()
    elif cmd == "sections":
        cmd_sections(args[0])
    elif cmd == "play":
        cmd_play(args)
    elif cmd == "render":
        cmd_render(args)
    elif cmd == "replay":
        cmd_replay()
    elif cmd == "stop":
        cmd_stop()
    elif cmd == "status":
        cmd_status()
    elif cmd == "volume":
        cmd_volume(args[0] if args else str(current_volume()))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
