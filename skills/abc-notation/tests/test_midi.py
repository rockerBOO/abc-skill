import struct

from render import _vlq, write_midi


def test_vlq_encoding():
    assert _vlq(0) == b"\x00"
    assert _vlq(127) == b"\x7f"
    assert _vlq(128) == b"\x81\x00"


def test_vlq_clamps_negative_no_hang():
    # Regression: negative delta-times used to loop forever (n >>= 7 on -1).
    assert _vlq(-5) == b"\x00"


def test_write_midi_header_and_length(tmp_path):
    out = tmp_path / "t.mid"
    write_midi([{"channel": 0, "program": 0, "notes": [(60, 0.0, 1.0, 100)]}], str(out), 120)
    data = out.read_bytes()
    assert data[:4] == b"MThd"
    assert struct.unpack(">I", data[4:8])[0] == 6
    assert data[8:10] == struct.pack(">H", 1)      # format 1
    assert data[10:12] == struct.pack(">H", 1)     # one track
    assert b"MTrk" in data
    assert data[-3:] == b"\xff\x2f\x00"            # end of track


def test_write_midi_negative_start_delta(tmp_path):
    # A note starting before the window (negative start) must not hang;
    # a float pitch is coerced rather than crashing.
    out = tmp_path / "n.mid"
    write_midi([{"channel": 0, "program": 0,
                 "notes": [(0.0, 0.0, 1.0, 100), (60, -0.5, 1.0, 100), (64, 1.0, 1.0, 100)]}],
               str(out), 120)
    data = out.read_bytes()
    assert data[:4] == b"MThd"
    assert data[-3:] == b"\xff\x2f\x00"


def _absolute_ticks(data):
    """Absolute tick of each event in the first MTrk chunk."""
    i = data.index(b"MTrk") + 4
    length = struct.unpack(">I", data[i:i + 4])[0]
    i += 4
    end = i + length
    ticks = 0
    out = []
    while i < end:
        delta = 0
        while True:
            b = data[i]
            i += 1
            delta = (delta << 7) | (b & 0x7F)
            if not b & 0x80:
                break
        ticks += delta
        if data[i] == 0xFF:
            i += 3 + data[i + 2]
        elif data[i] & 0xF0 in (0xC0, 0xD0):
            i += 2
        else:
            i += 3
        out.append(ticks)
    return out


def test_negative_start_does_not_shift_later_events(tmp_path):
    out = tmp_path / "shift.mid"
    write_midi([{"channel": 0, "program": 0,
                 "notes": [(60, -0.5, 1.0, 100), (64, 1.0, 1.0, 100)]}], str(out), 120)
    ticks = _absolute_ticks(out.read_bytes())
    # second note's note-off is at 2.0 s = 2.0 * 2 * 480 = 1920 ticks
    assert ticks[-1] == 1920
