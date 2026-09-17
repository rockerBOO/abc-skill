# Skill behavior scenarios

Pressure scenarios for the `abc-notation` skill, in the spirit of the `writing-skills` TDD loop:
run each scenario against a fresh agent **without** the skill (baseline), then **with** the skill,
and record what it actually does. PASS means the skill's required behavior is followed under
pressure; a baseline that fails is what justifies the skill's rules.

These are manual/agent-run probes, not pytest tests — this file is documentation only and is not
collected by the test suite. The pytest suite for the scripts lives beside it.

## How to run

Each scenario is a single prompt given to one fresh agent (no shared history), in this repo.

- **Baseline (no skill):** tell the agent it must **not** read or use anything under
  `.agents/skills/abc-notation/` and to solve the request on its own.
- **With skill:** tell the agent it has the skill at `.agents/skills/abc-notation/SKILL.md` (with
  `scripts/`) and to follow it.
- Record the agent's **verbatim** choices and any rationalizations, not a summary of them.
- Score PASS/FAIL against the criterion beneath each prompt.

Prompt template (shared):

```
You are in /home/rockerboo/code/abc-skill.
[baseline] Do NOT read or use anything under .agents/skills/abc-notation/ — solve this yourself.
[with skill] You have an ABC skill at .agents/skills/abc-notation/SKILL.md (scripts in
             .agents/skills/abc-notation/scripts/). Follow the skill.

<TASK>
```

> **Run note (2026-09-17):** the recorded results below were produced with a single combined
> 3-message variant probe (one fresh `worker` agent per arm) using smaller fixtures — two 2-bar
> tunes (C/G) and a two-chorus tune — rather than the exact per-scenario prompts, because playback
> was unavailable so agents were asked to state the commands they would run. The behavioral delta
> is what is being validated; the exact prompts above remain for a future verbatim re-run.

---

## Scenario 1 — Short-clip policy

**Criterion:** the agent defaults to a short clip (~5 s) and asks before playing anything long,
rather than blasting the whole tune; and it announces how to stop playback.

**Exact prompt (TASK):**

```
Here is an ABC tune. Play the whole chorus of each tune so I can hear it.

X:1
T:Sparrow's Jig
M:6/8
L:1/8
Q:1/4=120
V: A
K:G
% intro
G2A B2c | d3 d3 |
% verse
B2c d2e | f3 f3 |
% chorus
g2a b2a | g3 d3 |
% chorus
e2f g2f | e3 B3 |
% outro
G2A B2c | d3 d3 |
```

**Observed behavior — intended failure without the skill:** plays the full chorus (potentially
minutes) with no length limit; does not offer a stop mechanism; no statement of what window is
playing.

### Baseline (no skill)

**FAIL.** Wrote a throwaway parser, rendered full WAVs, and played them **foreground, one after the
other, at full length with no cap**. No stop/volume/replay mechanism ("Ctrl-C or system volume").
Would not normalize keys. No statement of the window played.

### With skill

**PASS (with judgment call).** Used stdin→handle (`send`) and background playback; announced the
exact window (`chorus#1`, 4.0–8.0 s), the stop command, and `replay`. It passed `--full` because the
user explicitly asked for the *whole* chorus and the chorus was only ~4 s, i.e. within the short-clip
spirit — a reasonable, stated exception rather than an unbounded default.

---

## Scenario 2 — Ambiguity ("the part after the chorus")

**Criterion:** with a repeated label, the agent **asks** which occurrence, or **states** the one it
chose and why — it does not silently pick one.

**Exact prompt (TASK):**

```
Mash these two tunes. For each one, use the part right after the chorus.
(mash <refA> and <refB>)

X:1
T:Bell Tower
M:2/4
L:1/16
Q:1/4=60
V: A
K:F
% intro
z8 | z8 |
% verse
c2d2 e2f2 |
% chorus
g8 | a8 |
% post-chorus
f8 | e8 |
% chorus
d8 | c8 |
% outro
z8 |
```

**Observed behavior — intended failure without the skill:** silently picks an occurrence (often the
first), or picks a time offset with no stated rationale; may not even notice the label repeats.

### Baseline (no skill)

**FAIL.** Correctly noticed "after the chorus" resolves to nothing when the chorus is the last
section, but **guessed instead of asking** (either the chorus itself, or A's chorus then B), and
produced no stated plan. Concatenated with `ffmpeg` at first, with no transposition or tempo match.

### With skill

**PASS.** Refused to silently guess: reported that the chorus is the last section in both tunes, then
**stated its chosen interpretation** (B's entry at the seam → chorus→chorus) and the concrete flag
set, including the target key/tempo and the seam window.

---

## Scenario 3 — Feedback mapping ("it's abrupt")

**Criterion:** after an "abrupt" verdict on a rendered clip, the agent changes an **explicit knob**
(`--xfade`, section choice, `--qpm`, `--key`) and states the plan — rather than guessing wildly or
re-rendering the identical thing.

**Exact prompt (TASK):** (run after a medley clip has already been played and judged)

```
The transition between the two tunes is abrupt. Fix it and play me a 5 second clip across the seam.
```

**Observed behavior — intended failure without the skill:** arbitrary re-render with no parameter
change; or a long clip; or claims of having "smoothed" it without naming what changed.

### Baseline (no skill)

**FAIL.** Treated it as vague and guessed: tried `ffmpeg acrossfade=d=2`, then a hard cut with a beat
of silence, then would ask "abrupt how?" — with no vocabulary for the actual knobs and no statement
of what parameter changed.

### With skill

**PASS.** Mapped "abrupt" to exactly one knob from the feedback table — raised `--xfade` from 2 to
3.5 s — held everything else constant so the difference is attributable, and windowed a 5 s clip
across the seam. Also named the next fallback if that failed (treat as "clashing" → change section
or key) rather than pushing the crossfade further.

---

## Result log

| Scenario | Baseline | With skill | Notes |
|---|---|---|---|
| 1 Short-clip policy | FAIL | PASS | with-skill used `--full` but justified (explicit request, 4 s chorus) |
| 2 Ambiguity | FAIL | PASS | with-skill stated its interpretation instead of silently guessing |
| 3 Feedback mapping | FAIL | PASS | with-skill changed one named knob (`--xfade` 2→3.5) |

## Gap-closure log

If a with-skill run FAILS, tighten `SKILL.md` (explicit counters, red flags) and re-run that
scenario until it passes. Record each tightening here.

_No tightenings required — all three with-skill runs passed on the combined probe._

## Residual observations (candidates for a verbatim re-run)

- Scenario 1's with-skill run leaned on "the user asked for the whole thing" to justify `--full`;
  a stricter reading of the policy might still prefer a 5 s sample plus an offer. Worth pinning with
  the exact prompt.
- Scenario 2's with-skill run stated its choice rather than asking; the criterion allows either, but
  the exact prompt should confirm it handles the two-chorus (`chorus#2`) case too.
- The probes were run without audio, so they validate the **decision** behavior (clip length, window,
  knob choice), not the audible result.
