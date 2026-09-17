"""Rendering: dependency-free MIDI writer, SoundFont synth, stdlib fallback synth."""
import os
import re
import struct
import subprocess

SR = 44100
DIV = 480


def _vlq(n):
    """MIDI variable-length quantity. Clamps negatives (regression guard)."""
    n = max(0, int(n))
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    return bytes(reversed(out))


def write_midi(tracks, path, qpm):
    """tracks: list of {channel, program, notes:[(midi, start_s, dur_s, vel)]}."""
    data = b"MThd" + struct.pack(">IHHH", 6, 1, len(tracks), DIV)
    us_per_q = int(60_000_000 / qpm)
    for tr in tracks:
        ch, prog = tr.get("channel", 0), tr.get("program", 0)
        ev = [(0, b"\xff\x51\x03" + us_per_q.to_bytes(3, "big")),
              (0, bytes([0xC0 | ch, prog & 0x7F]))]
        for midi, st, du, vel in tr["notes"]:
            t0 = int(round(st * qpm / 60 * DIV))
            t1 = int(round((st + du) * qpm / 60 * DIV))
            v = max(1, min(127, int(vel)))
            m = int(midi) & 0x7F
            ev.append((t0, bytes([0x90 | ch, m, v])))
            ev.append((t1, bytes([0x80 | ch, m, 0])))
        ev.sort(key=lambda x: (x[0], 0 if x[1][0] == 0x80 else 1))
        trk, last = bytearray(), 0
        for t, d in ev:
            trk += _vlq(t - last) + d
            last = t
        trk += b"\x00\xff\x2f\x00"
        data += b"MTrk" + struct.pack(">I", len(trk)) + bytes(trk)
    with open(path, "wb") as f:
        f.write(data)
    return path
