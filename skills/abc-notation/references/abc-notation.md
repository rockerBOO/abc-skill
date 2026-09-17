# ABC notation cheat-sheet

A concise reference for the subset of ABC this skill parses.

## Header fields

| Field | Meaning | Example |
|---|---|---|
| `X:` | Tune index (conventionally the first field) | `X:1` |
| `T:` | Title | `T:The Kesh Jig` |
| `M:` | Meter | `M:4/4`, `M:6/8`, `M:2/4` |
| `L:` | Default note length — the unit a bare note gets | `L:1/8`, `L:1/16` |
| `Q:` | Tempo | `Q:1/4=120` or `Q:120` |
| `K:` | Key (also sets the key signature) | `K:G`, `K:F`, `K:Dm`, `K:G mixolydian` |
| `V:` | Voice declaration / switch | `V:Lead clef=treble name="Lead"` |

Header fields appear before the body. A header on its own line mid-tune (e.g. `K:G`) takes effect from that point on; bracketed inline forms such as `[K:G]` are accepted but ignored.

## Pitches and octaves

Notes are `A`–`G`.

```
C,        C         c         c'
low C     middle C  C5        C6
```

- `C` (uppercase) is **middle C = C4 = MIDI 60**. Lowercase `c` is the octave above (C5).
- A comma `,` lowers an octave; an apostrophe `'` raises it (`C,` = C3, `c'` = C6).
- Accidentals: `^F` = F sharp, `_B` = B flat, `=C` = C natural.
- Accidentals apply for the rest of the bar.
- The key signature from `K:` supplies sharps/flats automatically.

## Durations

A duration suffix multiplies the default note length `L:`.

| Written | Relative to `L:` |
|---|---|
| `A` | 1× |
| `A2` | 2× |
| `A3` | 3× |
| `A/2` or `A/` | 1/2× |
| `A//` | 1/4× |
| `A3/2` | 1.5× |

## Rests

- `z` — a rest of a stated length (`z2`, `z/2`).
- `x` — an invisible rest (spacing only).
- `Z` — a multi-measure rest; `Z` is one full bar and `Z4` is four bars.

## Barlines, ties, chords, and decorations

- `|`, `||`, `|]` — barlines. `|:` and `:|` — repeat marks.
- `A- A` — a tie; the two notes sound as one held note.
- `[CEG]` — a chord (the notes sound together).
- `"Gm"` before a note is a **chord symbol** (harmonic label, not a sounded pitch).
- `( )` slurs, `{ }` grace notes, and `!...!` decorations are ignored by the parser.

## Multiple voices and sections

- `V:Name` switches voice; each voice is an independent line of music and they sound together.
- A `%` comment line names a **section**, for example `% chorus`. Section comments build the
  structure map that `sections` prints.
- `%` elsewhere (for example at the end of a body line) is an ordinary comment and is ignored.

## Worked example

```
X:1
T:Example
M:4/4
L:1/4
Q:1/4=120
K:G
% verse
V:Lead
G2 A B | c2 B A |
V:Bass
G,4 | D,4 |
% chorus
V:Lead
d4 | B4 |
V:Bass
G,4 | G,4 |
```

This tune has two voices (`Lead`, `Bass`), a `verse` and a `chorus` section, key G (so `F` sounds
as F sharp), a `L:1/4` default note length, and a tempo of 120 quarter-notes per minute.
