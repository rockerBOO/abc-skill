# abc-skill

An agent skill for reading, reasoning about, and recombining ABC music notation. It turns ABC
into a normalized score plus a structure map, lets the agent plan an arrangement, and renders
short audio clips a human can hear — because the agent cannot hear the music itself.

The loop: **analyze → decide (state the plan) → render a short clip → the human listens → map
their feedback to a knob → repeat.**

## Requirements

- Python 3.12 or newer. The skill's scripts are stdlib-only — there is nothing to `pip install`.
- Optional: `uv` if you prefer `uv run python` (the examples below use it).
- Optional: `fluidsynth` plus a SoundFont for realistic instrument sound. Without it, a built-in
  synth is used.
- Audio playback and volume control require **Linux with PulseAudio** (`paplay` / `pactl`).
  Rendering to WAV works everywhere; live playback is not implemented for macOS or Windows.

## Install

Install for each harness you use. `scripts/install.py` is a stdlib-only, cross-platform copy
installer — it never creates symlinks, so **Windows**, **macOS**, and **Linux** all behave the same.

```bash
# pick one or more harnesses; --scope project uses the current directory
python3 scripts/install.py --harness claude --scope project
python3 scripts/install.py --harness codex  --scope user
python3 scripts/install.py --harness pi     --scope user
python3 scripts/install.py --all --scope user --force   # everything, overwrite
python3 scripts/install.py --harness pi --dry-run       # show what would happen
```

Where it installs:

| Harness | `--scope project` | `--scope user` |
|---|---|---|
| Claude Code | `<cwd>/.claude/skills/abc-notation/` | `~/.claude/skills/abc-notation/` |
| Codex | `<cwd>/.agents/skills/abc-notation/` | `$CODEX_HOME/skills/abc-notation/` (default `~/.codex/skills/`) |
| Pi | `<cwd>/.agents/skills/abc-notation/` | `~/.agents/skills/abc-notation/` |

### Claude Code

Native plugin install from this repository:

```text
/plugin marketplace add rockerBOO/abc-skill
/plugin install abc-notation@abc-skill
```

Or use the installer:

```bash
python3 scripts/install.py --harness claude --scope user
```

### Codex

Codex reads user-level skills from `$CODEX_HOME/skills/` (default `~/.codex/skills/`) and also
from the cross-runtime `~/.agents/skills/`. Use the installer:

```bash
python3 scripts/install.py --harness codex --scope user
```

A `.codex-plugin/plugin.json` manifest is included for future marketplace distribution; there is
no marketplace listing yet.

### Pi

Install as a Pi package (this repo uses the conventional `skills/` layout):

```bash
pi install git:github.com/rockerBOO/abc-skill
```

Or copy with the installer:

```bash
python3 scripts/install.py --harness pi --scope user
```

## Quick start

Run from `skills/abc-notation/` (where `SKILL.md` lives).

```bash
# 1. hand ABC to the session; prints a handle id + structure summary
cat tune.abc | uv run python scripts/abcbox.py send

# 2. inspect the structure map (sections, times, active voices, chords)
uv run python scripts/abcbox.py sections <ref>

# 3. hear a short clip (default 5 seconds)
uv run python scripts/abcbox.py play <ref> --section chorus#2
uv run python scripts/abcbox.py stop

# 4. render a WAV without playing it
uv run python scripts/abcbox.py render <ref> -o /tmp/out.wav --section verse#1

# 5. mash two tunes
uv run python scripts/mash.py <refA> <refB> \
  --a-section chorus#1 --b-section chorus#1 \
  --key F --qpm 120 --mode seq --xfade 4 --seconds 5
```

## Optional SoundFont

For realistic instrument sound, put a SoundFont where the skill can find it:

```bash
mkdir -p ~/.local/share/soundfonts
# e.g. download MuseScore_General.sf3 into that directory
```

Or point at one explicitly with `ABC_SOUNDFONT=/path/to/soundfont.sf2`.

## Troubleshooting

- **No sound on macOS/Windows** — expected; live playback is Linux/PulseAudio only. Use
  `render` to produce a WAV and play it with any audio app.
- **Synthetic sound** — `fluidsynth` or a SoundFont is missing; install `fluidsynth` and add a
  SoundFont, or set `ABC_SOUNDFONT`.
- **Re-installing over an existing copy** — pass `--force`; otherwise the installer refuses to
  overwrite and tells you the destination.

## Development

The canonical skill is `skills/abc-notation/`. Run the full test suite from the repo root:

```bash
uv run --with pytest pytest skills/abc-notation/tests tests -q
```
