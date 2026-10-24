# Benchmarks: how wrong is the drift detector?

`nsh bench` is a regression test with a precision/recall report. This page
explains what it measures, what it does not, and where the detector fails.

```
$ nsh bench

  NIGHTSHIFT · detector benchmark
  labelled runs · 16 cases · 1 of them a real shift
  ————————————————————————————————————————————————————————————————————
  ✓ clean-run              clean/clean  gate green/green  -
  ✓ false-done             clean/clean  gate red  /red    unchecked_criteria
  ✓ silent-run             drift/drift  gate red  /red    silent_run,unchecked_criteria
  ✓ churn                  drift/drift  gate red  /red    churn,unchecked_criteria
  ✓ off-topic              clean/clean  gate red  /red    off_topic,unchecked_criteria
  ✓ messy-but-healthy      clean/clean  gate green/green  -
  ✓ notes-are-not-proof    drift/drift  gate green/green  silent_run
  ✓ short-run              clean/clean  gate green/green  -
  ✓ churn-with-checks      clean/clean  gate green/green  -
  ✓ late-off-topic         clean/clean  gate red  /red    off_topic,unchecked_criteria
  ✓ out-of-time            clean/clean  gate red  /red    unchecked_criteria
  ✓ everything-at-once     drift/drift  gate red  /red    churn,off_topic,silent_run,unchecked_criteria
  ✓ three-silent-steps     clean/clean  gate green/green  -
  ✓ jargon-run             clean/clean  gate green/green  -
  ✗ untargeted-churn       clean/drift  gate red  /red    -
  ✓ real-v0.1-build        clean/clean  gate green/green  off_topic
  ————————————————————————————————————————————————————————————————————
  structural drift  precision 1.00   recall 0.80   f1 0.89   (silent_run + churn; what the gate reports)
  topical advisory  precision 0.75   recall 1.00   f1 0.86   (off_topic; low severity by design)
  gate              accuracy 1.00
  confusion  tp=4 fp=0 tn=11 fn=1
```

The last case is not synthetic: `bench/cases/real-v0.1-build.json` is this
repository's own shift, exported verbatim — including the topical flag that was
wrong, which is why its precision is 0.75 instead of 1.00. A benchmark that only
contains cases its author invented will always flatter its author.

## Two detectors, two numbers

Earlier versions had a single "drift" score that counted three detectors. That
was wrong, and the way we found out is the most useful thing on this page.

**Structural drift** — `silent_run` (N steps with no evidence) and `churn` (the
same target edited N times without a check). These are mechanical facts about
the log, and they are what the report treats as risk.

**Topical advisory** — `off_topic`, containment of a step's words in the flight
plan's vocabulary. It is reported as a **low-severity hint**, never as a risk,
and it is not part of the structural score.

### Why `off_topic` was demoted

The first version shipped `off_topic` as a medium-severity flag. Then it fired
on the run that was building NIGHTSHIFT itself:

```
plan overlap 0.097 over the last 6 steps
```

The work was legitimate — writing a tokenizer, a bench, a skill file — but the
words ("black box", "bench", "SKILL.md") barely appear in a goal statement that
says "ship v0.1 … with a demo video and bilingual docs".

So we measured instead of tuning. Windowed containment, worst window:

| run | worst window mean | what it actually was |
| --- | --- | --- |
| this repo's own shift | **0.097** | legitimate work |
| `off-topic` (coffee, holidays) | **0.000** | genuinely off-plan |
| `jargon-run` | 0.158 | legitimate work in tooling jargon |
| `clean-run` | 0.371 | legitimate work |

Novelty (share of words never seen earlier in the run) did not separate them
either: 0.91 for the legitimate run, 0.95 for the off-topic one. There is no
threshold in that gap which is not a guess. A detector that guesses is worse
than no detector, because it teaches people to ignore the report.

So it was demoted, the label was changed to say "advisory, not a verdict", and
the number is still shown. That is the honest version of a heuristic.

## What is being measured

Two binary detectors:

- **Structural**: does the run contain `silent_run` or `churn`?
- **Gate**: does `gate()` return the expected green/red?

The corpus has **16 runs**: 15 built in `nightshift/bench.py` (each a full flight
plan plus 5–40 events, built in pairs so every "naive" case has a near-twin that
must *not* fire) and one real shift exported from `.nightshift/`.

| case | intent | expected |
| --- | --- | --- |
| `clean-run` | 26 on-plan steps, all proven | clean |
| `false-done` | 22 steps, one criterion failed, one never checked | red gate |
| `silent-run` | 11 steps with no evidence | structural drift |
| `churn` | one file touched 6x, no check | structural drift |
| `off-topic` | 10 steps about coffee and holidays | advisory only, not structural |
| `messy-but-healthy` | 30 steps, 30 % without evidence, never 4 in a row | clean |
| `notes-are-not-proof` | every check passes, all evidence is typed notes | drift + green gate |
| `short-run` | 3 steps, everything proven | clean |
| `churn-with-checks` | same file 5x **with** checks between each pair | clean |
| `late-off-topic` | 14 on-plan steps, then 9 off-plan | advisory only |
| `out-of-time` | red gate, deadline already passed | red gate |
| `everything-at-once` | churn + silence + off-topic | structural drift |
| `three-silent-steps` | 3 unproven steps between proven ones | clean |
| `jargon-run` | on-plan work described in tooling jargon | clean |
| `untargeted-churn` | churn with no `--target` recorded | structural drift (missed) |
| `real-v0.1-build` | this repo's own shift, exported verbatim | clean structurally; the topical advisory fired and was wrong |

## What it does not measure

- **Real agents.** 15 of the 16 runs are synthetic and labelled by construction;
  the sixteenth is one real shift, by one agent. These numbers are a regression
  test for the heuristics, not a scientific benchmark of agent behaviour.
  The only honest way to improve them is more real runs; `bench/cases/*.json`
  exists for exactly that.
- **Severity calibration.** "Medium" vs "high" is a hand-set threshold, not a
  measured quantity.
- **The quality of a done-criterion.** A green gate over a bad criterion is
  still green. Nothing here fixes a badly written plan.

## Known failure modes

1. **`untargeted-churn` — the one false negative.** Churn detection needs
   `--target`. If an agent edits the same file four times and never records it,
   the detector is blind. This is why the skill says to prefer
   `nsh run --target`.
2. **Jargon.** A real agent writes "bump clap to 4.5", not "improve the CLI
   argument parser". This is exactly why `off_topic` is advisory: the words are
   a lossy description of the work.
3. **Long runs with one theme.** A 200-step run where every intent is nearly
   identical ("fix tests") will have high containment and can hide genuine
   drift inside the repetition. `silent_run` and `churn` are the backstop.
4. **Thresholds were tuned on this corpus.** `DRIFT_WINDOW = 6`,
   `CHURN_MEDIUM = 4`, `SILENT_RUN_MEDIUM = 4`, `DRIFT_SIM_FLOOR = 0.12` were
   chosen by looking at these 15 cases. That is overfitting, and the fix is more
   cases, not more tuning.

## Adding a case

```json
{
  "name": "my-real-run-2026-10-24",
  "expect_drift": true,
  "expect_gate": false,
  "topical": null,
  "contract": { "...": "paste .nightshift/contract.json" },
  "events":   [ "...": "paste lines from .nightshift/events.jsonl" ]
}
```

`topical` may be `true`, `false` or `null` (not scored). Drop the file in
`bench/cases/` and run `nsh bench`. Cases that *fail* are the most valuable
ones — open a PR with the failure rather than tuning the threshold.
