# Changelog

## v0.1.0 — 2026-10-25

First public release.

**Core**

- Flight plan (`contract.json`) with goal, command-checkable done-criteria,
  non-goals, risks and a deadline.
- Append-only black box (`events.jsonl`) with evidence captured at action time:
  stdout, exit code, duration and sha256 of the captured bytes.
- Evidence gate: `nsh gate` exits 0 only when every criterion's latest check
  passed *and* carries machine-checkable evidence.
- `nsh verify`: recomputes every digest in the log. Tampered captures fail;
  project files edited after their snapshot are reported as *changed* instead,
  because projects move on and a check that always fails is never read.
- Drift detection: silent runs, churn on a target, unchecked criteria; plus a
  low-severity topical advisory.
- Convergence detection from checkpoints carrying `--progress`.
- Self-contained HTML flight report (no JS, no CDN) with a mandatory
  **Not proven** section, and a ten-line wake-up brief.

**Interfaces**

- `nsh init / done add / run / step / check [--all] / tick / gate / status /
  brief / report / log / bench / demo / doctor`
- `SKILL.md` for Claude Code, Codex, Cursor and DSH-style harnesses.

**Assets**

- Deterministic 7.5-hour demo run (`nsh demo`).
- Terminal demo gif rendered from a real CLI session.
- 33-second vertical cut for social.

**Benchmarks**

- Structural drift detector: precision 1.00, recall 0.80 on 15 labelled
  synthetic runs (one documented blind spot: churn without `--target`).
- Gate: 100% agreement with labels on the same corpus.
- The topical detector was demoted from a risk flag to an advisory after it
  false-positived on the run that built this repository; the measurement is in
  `docs/BENCHMARKS.md`.

**Known limitations**

- A determined agent with shell access can write fake check events. The log
  makes that visible, not impossible.
- Checks age. Re-run `nsh check --all` before you sleep and the report says when
  each check happened.
- Thresholds were tuned on the synthetic corpus; real logs are the fix.
