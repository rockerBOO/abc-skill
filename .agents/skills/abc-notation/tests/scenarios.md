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

_Not yet recorded._

### With skill

_Not yet recorded._

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

_Not yet recorded._

### With skill

_Not yet recorded._

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

_Not yet recorded._

### With skill

_Not yet recorded._

---

## Result log

| Scenario | Baseline | With skill | Notes |
|---|---|---|---|
| 1 Short-clip policy | not run | not run | |
| 2 Ambiguity | not run | not run | |
| 3 Feedback mapping | not run | not run | |

## Gap-closure log

If a with-skill run FAILS, tighten `SKILL.md` (explicit counters, red flags) and re-run that
scenario until it passes. Record each tightening here.

_No tightenings yet._
