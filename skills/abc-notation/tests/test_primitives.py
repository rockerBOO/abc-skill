from abclib import key_accidentals, parse_duration, parse_qpm


def test_key_major_sharp():
    assert key_accidentals("G") == {"F": "^"}
    assert key_accidentals("D") == {"F": "^", "C": "^"}


def test_key_major_flat():
    assert key_accidentals("F") == {"B": "_"}
    assert key_accidentals("Bb") == {"B": "_", "E": "_"}


def test_key_minor():
    assert key_accidentals("Dm") == {"B": "_"}
    assert key_accidentals("Em") == {"F": "^"}


def test_key_modes():
    # D dorian, E phrygian, G mixolydian all share C major's (empty) signature
    assert key_accidentals("D dorian") == {}
    assert key_accidentals("E phrygian") == {}
    assert key_accidentals("G mixolydian") == {}


def test_parse_duration():
    assert parse_duration("") == 1.0
    assert parse_duration("2") == 2.0
    assert parse_duration("3/2") == 1.5
    assert parse_duration("/") == 0.5
    assert parse_duration("//") == 0.25
    assert parse_duration("3/") == 1.5


def test_parse_qpm():
    assert parse_qpm("1/4=60", 0.25) == 60.0
    assert parse_qpm("1/8=120", 0.5) == 60.0
    assert parse_qpm("120", 0.5) == 60.0
    assert parse_qpm("", 0.5) == 60.0
