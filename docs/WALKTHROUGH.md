# A walkthrough: one shift, start to morning

This is what using NIGHTSHIFT actually looks like, with real command output from
this repository's own shift. It takes about five minutes to read and it is the
fastest way to decide whether the tool is for you.

---

## 22:49 — the plan

```console
$ nsh init --goal "ship v0.1 of the report CLI" --deadline 06:30 \
           --non-goal "no web UI" --risk "fixtures are locale dependent"

✈ NIGHTSHIFT · flight plan created  .nightshift
────────────────────────────────────────────────────────────────
  goal        ship v0.1 of the report CLI
  deadline    2026-10-25T06:30:00+08:00
```

Then the part that decides whether the night is auditable at all:

```console
$ nsh done add "tests pass"         -- python -m pytest -q
  + d1 tests pass  $ python -m pytest -q
$ nsh done add "quickstart exists"  -- python scripts/check_readme.py
  + d2 quickstart exists  $ python scripts/check_readme.py
```

If you cannot write the command, the criterion is a wish. `nsh done add` lets
you add a wish (`nsh done add "code is clean"` with no command) and the gate will
still hold you to it — but you will have to supply a command at check time, which
is a worse position to be in.

---

## 23:10 — work, with receipts

The difference between this and a normal agent run is one word: `run` instead of
"just do it".

```console
$ nsh run --target src/parser.py -- python -m pytest tests/test_parser.py -q
  ● 23:14:02 e000003 python -m pytest tests/test_parser.py -q  ok (2.4s)
      │ 12 passed in 2.41s

$ nsh step "rewrote the quickstart by hand" -e README.md
  ● 23:15:38 e000004 rewrote the quickstart by hand  1 evidence
```

`nsh run` captured stdout, the exit code, the duration and a sha256 of the
bytes. `nsh step` recorded a file hash. Both landed in the append-only log at
the moment they happened, which is the only moment a receipt means anything.

---

## 00:20 — the checkpoint

```console
$ nsh tick --progress 40 --note "parser done, templating next"

✈ NIGHTSHIFT · checkpoint  #1
────────────────────────────────────────────────────────────────
  progress    40%
  elapsed     1h31m  · 5h09m left
  gate        RED  1/2 criteria
  coverage    100%
  drift       clean
  advisory    1 low-confidence: plan overlap 0.10 over the last 6 steps
```

Two things to notice:

- **`gate RED 1/2`** is normal at 00:20. It is not a failure; it is the current
  truth, and you can see it without opening anything.
- **`advisory`** is deliberately separate from `drift`. It fired here — on this
  very run — and it was wrong. That is why it is low severity and why the
  benchmark scores it separately. Read
  [`docs/BENCHMARKS.md`](BENCHMARKS.md) for the measurement that caused the
  demotion.

---

## 03:40 — the moment it goes wrong

Somewhere around hour five the agent edited `src/render.rs` four times without
running anything. The next checkpoint says so:

```console
$ nsh tick --progress 61

✈ NIGHTSHIFT · checkpoint  #3
────────────────────────────────────────────────────────────────
  drift       1 flag(s)
      ▸ `src/render.rs` touched 4x with no check in between
```

`churn` is the cheapest useful detector in the box: it needs no model, no
judgement and no context, only `--target` on the steps that edit a file. It is
also the one detector that will be **blind** if you forget `--target`, which is
the single false negative in the benchmark.

The agent's job at this point is not to feel bad. It is to run the check.

```console
$ nsh check d3
  PASS d3 three templates render without warnings  exit 0
```

---

## 06:12 — the gate

Before writing the report, re-run everything. Checks age.

```console
$ nsh check --all
  PASS d1 tests pass                          exit 0
  PASS d2 quickstart exists                   exit 0

$ nsh gate
✈ NIGHTSHIFT · completion gate  DONE & PROVEN
────────────────────────────────────────────────────────────────
  ✓ d1  tests pass                                              proven
  ✓ d2  quickstart exists                                       proven

  GATE GREEN — every criterion is proven with evidence.
```

A red gate here is a valid outcome — the report then says `PARTIAL · NOT PROVEN`
and lists exactly what is missing. **A truthful red report is worth more than a
false green one**, because the entire point of leaving an agent alone overnight
is that the morning is not a surprise.

---

## 06:15 — verify, then report

```console
$ nsh verify
  7 intact · 0 tampered · 14 changed · 0 missing · 0 without a digest
  VERIFY OK — every captured artefact is intact; 14 project file(s) moved on
  since they were snapshotted.
```

`verify` separates two things that look identical if you only compare hashes:
captured output inside `.nightshift/evidence/` that must never change
(**tampered** → exit 1), and project files that have legitimately been edited
since their snapshot (**changed** → informational). Without that split, every
run fails its own verification and nobody reads the check.

```console
$ nsh report
  ✓ wrote .nightshift/reports/flight-report.html  (17240 bytes)

$ nsh brief
GOAL      ship v0.1 of the report CLI
WINDOW    7h26m used · 46m left
ACTIVITY  11 steps · 10 checks · 3 checkpoints · 26 pieces of evidence
EVIDENCE  100% of steps carry proof (11/11)
GATE      GREEN · 5/5 criteria proven
RISK      no structural drift flags
TREND     improving - still climbing: +37 points over 0.2h
```

---

## 06:30 — what the human reads

Open `flight-report.html`. Read in this order:

1. **Verdict** — one line, and the number behind it.
2. **Not proven** — always first, even when it is empty. If it is not empty,
   you just saved four hours of believing something false.
3. **Drift & near-misses** — the churn loop, the silent stretch, the forty
   minutes spent on a non-goal. These are the lessons; a report without them is
   marketing.
4. **Proven** — with the sha256 of every captured byte, so you can check.

Then go get coffee. The night is over, and nothing about it is a surprise.
