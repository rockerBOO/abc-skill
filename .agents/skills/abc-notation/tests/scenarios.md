# Skill behavior scenarios

Pressure scenarios for the `abc-notation` skill, in the spirit of the `writing-skills` TDD loop:
run each scenario against a fresh agent **without** the skill (baseline), then **with** the skill,
and record what it actually does. PASS means the skill's required behavior is followed under
pressure; a baseline that fails is what justifies the skill's rules.

These are manual/agent-run probes, not pytest tests — this file is documentation only and is not
collected by the test suite. The pytest suite for the scripts lives beside it.

## How to run

Each scenario is a single prompt given to one fresh agent (no shared history), in this repo.
(The one exception is **Scenario 3**, which is deliberately a follow-up turn in the same session —
see its setup note.)

- **Baseline (no skill):** tell the agent it must **not** read or use anything under
  `.agents/skills/abc-notation/` and to solve the request on its own.
- **With skill:** tell the agent it has the skill at `.agents/skills/abc-notation/SKILL.md` (with
  `scripts/`) and to follow it.
- Record the agent's choices and any rationalizations (a concise summary is acceptable; include the
  raw transcript when available).
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
> 3-message variant probe (one fresh `worker` agent per arm) using the fixtures recorded in the next
> section — not the canonical per-scenario prompts — because audio playback was unavailable, so the
> agent was asked to state the commands it would run rather than execute them. The behavioral delta
> is what is being validated; every recorded result below is stamped so it is traceable to those
> fixtures, and the canonical prompts remain for a future verbatim re-run.

### Variant probe actually run (2026-09-17)

Fixtures used by the recorded probe:

```
X:1
T:Tune A
M:4/4
L:1/4
K:C
% verse
C D E F | G A B c |
% chorus
d e f g | a b c' d' |
```

```
X:2
T:Tune B
M:4/4
L:1/4
K:G
% verse
G A B c | d e f g |
% chorus
a b c' d' | e' d' c' b |
```

The canonical two-chorus fixture is the **Bell Tower** ABC in Scenario 2 below.

**How it was run:** one fresh agent per arm, given all three of these requests in one session, with
audio playback unavailable and the instruction to state the exact commands it would run. No length
normalisation was applied to the tunes: no `Q:` header is present, `L:1/4`, so the default tempo is
120 qpm and each 2-bar section is 4 s.

Requests handed to each agent:

```
1. Here are two ABC tunes (Tune A and Tune B). Play the whole chorus of each tune so I can hear it.
2. Mash these two tunes. For each one, use the part right after the chorus.
   (send both tunes first to get handles, then mash)
3. The transition between the two tunes is abrupt. Fix it and play me a 5 second clip across the seam.
```

For requests 1–2 the tunes in play were **Tune A and Tune B**, both of which have their chorus as
their final section. The Bell Tower ABC (two `% chorus` blocks, followed by `% outro`) is the
canonical Scenario 2 fixture and is listed there for completeness.

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

**Observed behavior — intended failure without the skill:** plays the whole tune end-to-end
(~15 s with this fixture; unbounded in general) rather than a ~5 s clip; provides no stop mechanism;
states no window.

### Baseline (no skill) — variant probe (see fixtures above)

**FAIL.** Wrote a throwaway parser, rendered full WAVs, and played them **foreground, one after the
other, at full length with no cap** (Tune A and Tune B, 8 s each). No stop/volume/replay mechanism
("Ctrl-C or system volume"). Would not normalize keys. No statement of the window played.

### With skill — variant probe (see fixtures above)

**PASS (with judgment call).** Used stdin→handle (`send`) and background playback; announced the
exact window (`chorus#1`, 4.0–8.0 s), the stop command, and `replay`. It passed `--full` because the
user explicitly asked for the *whole* chorus and the chorus was only ~4 s, i.e. within the short-clip
spirit — a reasonable, stated exception rather than an unbounded default.

---

## Scenario 2 — Ambiguity ("the part after the chorus")

**Criterion:** with a repeated label, the agent **asks** which occurrence, or **states** the one it
chose and why — it does not silently pick one.

**Exact prompt (TASK):** (send both tunes first to get handles, then mash them)

```
Mash these two tunes. For each one, use the part right after the chorus.

# Tune 1 of 2 — Bell Tower (has two % chorus blocks)
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

# Tune 2 of 2 — Tune A (chorus is the final section)
X:2
T:Tune A
M:4/4
L:1/4
K:C
% verse
C D E F | G A B c |
% chorus
d e f g | a b c' d' |
```

Concrete run step, replacing the old `<refA>`/`<refB>` placeholders:

```bash
cat tune1.abc | python3 .agents/skills/abc-notation/scripts/abcbox.py send   # -> handle A
cat tune2.abc | python3 .agents/skills/abc-notation/scripts/abcbox.py send   # -> handle B
python3 .agents/skills/abc-notation/scripts/mash.py <handleA> <handleB> ...
```

**Observed behavior — intended failure without the skill:** silently picks an occurrence (often the
first), or picks a time offset with no stated rationale; may not even notice the label repeats.

### Baseline (no skill) — variant probe (see fixtures above)

**FAIL.** Correctly noticed "after the chorus" resolves to nothing when the chorus is the final
section of both tunes in play (Tune A and Tune B), but **guessed instead of asking** (either the
chorus itself, or one tune's chorus then the other), and produced no stated plan. Concatenated with
`ffmpeg` at first, with no transposition or tempo match.

### With skill — variant probe (see fixtures above)

**PASS.** Refused to silently guess: reported that the chorus is the final section of both tunes in
play, then **stated its chosen interpretation** (B's entry at the seam → chorus→chorus) and the
concrete flag set, including the target key/tempo and the seam window.

---

## Scenario 3 — Feedback mapping ("it's abrupt")

**Criterion:** after an "abrupt" verdict on a rendered clip, the agent changes an **explicit knob**
(`--xfade`, section choice, `--qpm`, `--key`) and states the plan — rather than guessing wildly or
re-rendering the identical thing.

**Setup (prior session state — this scenario is NOT a fresh agent):** a medley clip from the two
tunes has already been rendered and played in this same session, using `--mode seq --xfade 2`, and
the user has just judged it abrupt. So this is a follow-up turn in one session, not a cold start:
the agent already holds the handles/handles' structure map from the earlier turn.

**Exact prompt (TASK):**

```
The transition between the two tunes is abrupt. Fix it and play me a 5 second clip across the seam.
```

**Observed behavior — intended failure without the skill:** arbitrary re-render with no parameter
change; or a long clip; or claims of having "smoothed" it without naming what changed.

### Baseline (no skill) — variant probe (see fixtures above)

**FAIL.** Treated it as vague and guessed: tried `ffmpeg acrossfade=d=2`, then a hard cut with a beat
of silence, then would ask "abrupt how?" — with no vocabulary for the actual knobs and no statement
of what parameter changed.

### With skill — variant probe (see fixtures above)

**PASS.** Mapped "abrupt" to exactly one knob from the feedback table — raised `--xfade` from the
initial `2` to `3.5` — held everything else constant so the difference is attributable, and windowed
a 5 s clip across the seam. Also named the next fallback if that failed (treat as "clashing" →
change section or key) rather than pushing the crossfade further.

---

## Result log

All rows refer to the **variant probe** fixtures recorded at the top of this file, not the canonical
per-scenario prompts.

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
  the canonical prompt.
- Scenario 2's with-skill run stated its choice rather than asking; the criterion allows either, but
  a re-run with the Bell Tower fixture should confirm it handles the two-chorus (`chorus#2`) case,
  which the probe's fixtures did **not** exercise.
- The probes were run without audio, so they validate the **decision** behavior (clip length, window,
  knob choice), not the audible result.
