---
name: nightshift
description: Drive a long unattended work session (hours, not minutes) that ends in a flight report a human can audit. Use when the user says "work on it while I sleep", "keep going until it is done", "spend the next N hours on this", or whenever a task will run longer than ~30 minutes and you must not declare success without proof. Enforces a flight plan, an append-only black box, checkpoints, drift detection, a convergence check and an evidence gate.
license: MIT
---

# NIGHTSHIFT

You are about to work for hours without a human watching. The failure mode is
not "the agent cannot code". The failure mode is **the agent says it is done,
the human believes it, and nothing was actually proven.**

This skill replaces "trust me" with a flight recorder and a gate.

## The deal

- The human gives you a goal and a deadline.
- You write a **flight plan**: a goal, *checkable* done-criteria, non-goals, risks.
- You work. Every meaningful action appends a line to an append-only black box,
  with machine-checkable evidence attached at the moment of action.
- Every ~45 minutes (or every 8 steps) you write a **checkpoint**: honest
  progress, plus whatever the drift detector says.
- When you believe you are done, you run `nsh gate`. If the gate is red, **you
  are not done** — you either fix it or you report it.
- You finish by generating a **flight report** and a ten-line brief written for
  a stranger who has coffee and no context.

## Bootstrap (first five minutes)

```bash
nsh status                        # resume an existing shift instead of restarting

nsh init --goal "<one sentence, concrete, falsifiable>" --deadline 06:30 \
         --non-goal "no web UI" --risk "the fixture data is locale dependent"

nsh done add "tests pass"              -- python -m pytest -q
nsh done add "the CLI builds"          -- npm run build
nsh done add "README has a quickstart" -- python scripts/check_readme.py
```

`nsh` is `python -m nightshift` if the CLI is not installed.

Rules for done-criteria:

1. **Each one is checkable by a command that exits 0 or non-zero.** If you
   cannot write the command, the criterion is a wish, not a criterion.
2. **Three to six criteria.** More than six and you are describing a project,
   not a shift.
3. **Say what is out of scope.** Non-goals are how a long run stays honest when
   it gets bored.
4. **The deadline is a real constraint.** Long runs without a deadline are how
   agents burn a night on the wrong thing.

## The loop

```
        ┌──────────────────────────────────────────────┐
        │  work one meaningful unit                    │
        │  nsh run -- <command>        (captures proof) │
        │  nsh step "did X" -e <file>  (non-command)    │
        └───────────────────┬──────────────────────────┘
                            │  every ~8 steps or ~45 min
                            ▼
        ┌──────────────────────────────────────────────┐
        │  nsh tick --progress N --note "..."           │
        │  read the drift flags. believe them.          │
        └───────────────────┬──────────────────────────┘
                            │
             done? ─────────┴──────────── not done
               │                             │
               ▼                             ▼
        nsh gate  ── red ──► fix, or report it as unproven
               │
             green
               ▼
        nsh report && nsh brief
```

### Recording work

Prefer `nsh run` over `nsh step`, always. It captures stdout, exit code and a
sha256 of the bytes, so the claim "the tests pass" stops being an opinion.

```bash
nsh run -- python -m pytest -q                 # proof: exit 0 + captured output
nsh run --target src/parser.py -- cargo build   # --target powers churn detection
nsh step "rewrote the intro by hand" -e README.md
```

`--target` matters: the detector can only notice you have edited the same file
four times without verifying it if you tell it which file you touched.

### Checkpoints

```bash
nsh tick --progress 42 --note "parser done, templating next"
```

`--progress` is **your honest estimate of completion, 0-100**, not effort spent.
Three checkpoints that all say 91 means the run has converged and more polishing
will not pay. Say so in the report.

### The gate

```bash
nsh gate          # exit 0 only if every criterion passed *with* evidence
nsh gate --json   # same, machine readable
```

A criterion passes only when: the check command ran, it exited 0, **and** the
event carries a machine-checkable evidence item (command output captured, or a
file hash). Notes do not count. Your own confidence does not count.

**If the gate is red at the deadline, that is a valid outcome.** Report
`PARTIAL` or `NOT DONE`. A truthful red report is worth more than a false green
one; the whole point of the night shift is that the morning is not a surprise.

### Finishing

```bash
nsh check --all       # re-run every criterion, right before you write the report
nsh report            # .nightshift/reports/flight-report.html  (+ --md)
nsh brief             # the ten lines the human actually reads
```

Checks age. A gate built on a check from three hours ago is a rumour — re-run
everything in one go before the report, and let the last check be the real one.

The report has a mandatory **"Not proven"** section. Do not delete it, do not
empty it by lowering the criteria after the fact. Moving the goalposts is the
one thing this tool exists to make visible.

## The seven laws

1. **The plan comes before the work.** No done-criteria, no shift.
2. **Every claim leaves a receipt.** Capture at action time; a receipt written
   afterwards is fiction with a timestamp.
3. **Checkpoints are cheap, drift is expensive.** Tick early, tick often.
4. **A red gate is not a failure of the run, it is the run's product.**
5. **Stop when the meter says stop.** Budget spent, or three checkpoints with no
   measurable gain: stop and report instead of polishing.
6. **Never rewrite the log.** Append-only. The history is the evidence.
7. **The brief is written for a stranger.** Assume the reader has no context and
   five minutes.

## Forbidden moves

| Temptation | Why it is forbidden |
| --- | --- |
| "I'll mark it done and mention the caveat in prose." | Prose is not a gate. Run `nsh check`. |
| Writing an evidence file by hand to satisfy the gate. | That is forging the receipt. Report red instead. |
| Skipping a checkpoint because you are in flow. | Flow is exactly when drift happens. |
| Deleting or editing an event in `events.jsonl`. | The log is append-only. Add a correction event. |
| Relaxing a done-criterion at 06:00 because it is hard. | Move the goalposts *before* the work, not after. |
| Reporting a percentage you did not measure. | Every number in the brief comes from the log. |

## Degraded mode (no Python, no CLI)

If `nsh` cannot run, keep the same discipline by hand in `flight-log.md`:

```
## 03:12 checkpoint (progress 40)
- did: parser + fixtures  [proof: cargo test output pasted below]
- did not: templating
- drift: spent 50 min on CSS that is a non-goal
```

The gate then requires: for every done-criterion, a pasted command + exit code.
It is worse than the tool. It is much better than nothing.

## What a good flight report looks like

- **Verdict first**, in one line, with the number that justifies it.
- **Proven** and **Not proven** side by side. The second list is the valuable one.
- **Near-misses**: the churn loop you caught at 04:10, the three hours lost to a
  non-goal. These are the lessons; a report without them is marketing.
- **A trend line**, so the human can see whether hour seven was worth it.

## Files this skill creates

```
.nightshift/
  contract.json     flight plan (goal, done-criteria, budget, non-goals)
  events.jsonl      append-only black box
  evidence/         captured output, hashed
  reports/          flight-report.html / .md
```

Commit `.nightshift/` for work you want auditable. It is small, it is text, and
it is the difference between "the agent said it worked" and "here is the night".
