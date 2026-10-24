# Benchmarks: how wrong is the drift detector?

`nsh bench` is a regression test with a precision/recall report. This page
explains what it measures, what it does not, and where the detector fails.

```
$ nsh bench

  NIGHTSHIFT · detector benchmark
  labelled synthetic runs · 15 cases
  ────────────────────────────────────────────────────────────────────
  ✓ clean-run              clean/clean  gate green/green  -
  ✓ false-done             clean/clean  gate red  /red    unchecked_criteria
  ✓ silent-run             drift/drift  gate red  /red    silent_run,unchecked_criteria
  ✓ churn                  drift/drift  gate red  /red    churn,unchecked_criteria
  ✓ off-topic              drift/drift  gate red  /red    off_topic,unchecked_criteria
  ✓ messy-but-healthy      clean/clean  gate green/green  -
  ✓ notes-are-not-proof    drift/drift  gate green/green  silent_run
  ✓ short-run              clean/clean  gate green/green  -
  ✓ churn-with-checks      clean/clean  gate green/green  -
  ✓ late-off-topic         drift/drift  gate red  /red    off_topic,unchecked_criteria
  ✓ out-of-time            clean/clean  gate red  /red    unchecked_criteria
  ✓ everything-at-once     drift/drift  gate red  /red    churn,off_topic,silent_run,unchecked_criteria
  ✓ three-silent-steps     clean/clean  gate green/green  -
  ✓ jargon-run             clean/clean  gate green/green  -
  ✗ untargeted-churn       clean/drift  gate red  /red    -
  ────────────────────────────────────────────────────────────────────
  drift detector   precision 1.00   recall 0.86   f1 0.92
  gate             accuracy 1.00
  confusion  tp=6 fp=0 tn=8 fn=1
```

## What is being measured

Two binary detectors:

- **Drift**: does the run contain at least one of `silent_run`, `churn`,
  `off_topic`? (`unchecked_criteria` is a risk flag, not part of this score.)
- **Gate**: does `gate()` return the expected green/red for the run?

The corpus has **15 runs**, each a full flight plan plus 5–40 events, built in
`nightshift/bench.py`. Cases are built in pairs on purpose: every "naive" case
has a near-twin that must *not* fire.

| case | intent | expected |
| --- | --- | --- |
| `clean-run` | 26 on-plan steps, all proven | clean |
| `false-done` | 22 steps, one criterion failed, one never checked | red |
| `silent-run` | 11 steps with no evidence | drift |
| `churn` | one file touched 6x, no check | drift |
| `off-topic` | 10 steps about coffee and holidays | drift |
| `messy-but-healthy` | 30 steps, 30 % without evidence, never 4 in a row | clean |
| `notes-are-not-proof` | every check passes, all evidence is typed notes | drift + green gate |
| `short-run` | 3 steps, everything proven | clean |
| `churn-with-checks` | same file 5x **with** checks between each pair | clean |
| `late-off-topic` | 14 on-plan steps, then 9 off-plan | drift |
| `out-of-time` | red gate, deadline already passed | red |
| `everything-at-once` | churn + silence + off-topic | drift |
| `three-silent-steps` | 3 unproven steps between proven ones | clean |
| `jargon-run` | on-plan work described in tooling jargon | clean |
| `untargeted-churn` | churn with no `--target` recorded | drift (missed) |

## What it does not measure

- **Real agents.** The corpus is synthetic and labelled by construction. These
  numbers are a regression test for the heuristics, not a scientific benchmark.
  The only honest way to improve them is more real runs; `bench/cases/*.json`
  exists for exactly that.
- **Severity calibration.** "Medium" vs "high" is a hand-set threshold, not a
  measured quantity.
- **The quality of a done-criterion.** A green gate over a bad criterion is
  still green. Nothing here fixes a badly written plan.

## Known failure modes

1. **`untargeted-churn` — false negative.** Churn detection needs `--target`.
   If an agent edits the same file four times and never records it, the detector
   is blind. This is why the skill says to prefer `nsh run --target`.
2. **Jargon.** A real agent writes "bump clap to 4.5", not "improve the CLI
   argument parser". Containment against the plan vocabulary drops. The
   `jargon-run` case passes today because of the surrounding context, but a run
   written entirely in jargon would be a false positive. The current mitigation
   is that a flag is a flag, not a verdict.
3. **Long runs with one theme.** A 200-step run where every intent is nearly
   identical ("fix tests") will have high containment and can hide genuine
   drift inside the repetition. D2 (silent run) and D3 (churn) are the backstop.
4. **Thresholds were tuned on this corpus.** `DRIFT_SIM_FLOOR = 0.12`,
   `CHURN_MEDIUM = 4`, `SILENT_RUN_MEDIUM = 4` were chosen by looking at these
   15 cases. That is overfitting, and the fix is more cases, not more tuning.

## Adding a case

```json
{
  "name": "my-real-run-2026-10-24",
  "expect_drift": true,
  "expect_gate": false,
  "contract": { "...": "paste .nightshift/contract.json" },
  "events":   [ "...": "paste lines from .nightshift/events.jsonl" ]
}
```

Drop it in `bench/cases/` and run `nsh bench`. Cases that *fail* are the most
valuable ones — open a PR with the failure rather than tuning the threshold.
