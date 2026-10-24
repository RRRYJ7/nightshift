# Contributing

The most useful thing you can send is **a real run that broke the detector**.

## Ways to contribute

### 1. A failing benchmark case (highest value)

Run a shift, keep `.nightshift/`, then:

```json
{
  "name": "my-run-2026-11-02",
  "expect_drift": true,
  "expect_gate": false,
  "contract": { "...": "paste .nightshift/contract.json" },
  "events": [ "...": "paste every line of .nightshift/events.jsonl" ]
}
```

Drop it in `bench/cases/` and run `nsh bench`. If it fails, **open the PR
anyway** and say why the label is right. A detector with 12 documented failures
is worth more than one with a suspiciously perfect score.

### 2. A new detector

`nightshift/analysis.py` is pure functions over `(contract, events)`. A detector
is a function returning `Finding` objects. Requirements:

- it emits a **flag**, never a verdict;
- the finding carries the number and the events behind it;
- it comes with at least one positive and one hard-negative case in the bench.

### 3. A report section

`nightshift/report.py` is one HTML string plus SVG primitives. Keep it
self-contained: no JavaScript, no CDN, no web fonts.

### 4. Translations

`README.zh-CN.md` exists. Other languages welcome — translate the README, not
the protocol (the protocol stays English so implementations agree).

## Development

```bash
python -m unittest discover -s tests -t . -v
python -m nightshift bench
python -m nightshift demo --open
python tools/check_docs.py
```

No dependencies, no build step. Python 3.9+.

## Style

- Comments explain *why*, not *what*.
- Every user-facing number must come from the log, never from a vibe.
- If a heuristic has a blind spot, write the blind spot into the docs in the
  same PR.

## Code of conduct

Be the kind of person who can hear "your detector was wrong here" without
taking it personally. That is the entire code of conduct.
