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
