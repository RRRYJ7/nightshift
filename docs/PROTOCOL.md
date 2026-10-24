# The NIGHTSHIFT protocol, v1

This document is the contract between the *tool* and the *skill*. If you want to
reimplement `nsh` in another language, this is the whole specification.

Everything below is deliberately boring. The interesting part of a night shift
is the work; the record of it should be dull, exact and hard to fake.

---

## 0. Scope

A **shift** is one agent run against one **flight plan**, recorded in one
`.nightshift/` directory. A shift ends when the agent stops, with or without a
green gate.

The protocol defines five things:

1. the **flight plan** (what "done" means, in advance),
2. the **black box** (an append-only event log),
3. the **gate** (the only legitimate way to say "done"),
4. the **detectors** (drift and convergence),
5. the **report** (what a human reads).

---

## 1. Flight plan — `contract.json`

```json
{
  "v": 1,
  "tool": "nightshift 0.1.0",
  "goal": "one sentence, concrete, falsifiable",
  "created_at": "2026-10-25T03:05:00+08:00",
  "budget": {
    "started_at": "2026-10-25T03:05:00+08:00",
    "deadline": "2026-10-25T10:30:00+08:00",
    "hours": 7.4
  },
  "done": [
    {"id": "d1", "text": "test suite green", "cmd": ["python", "-m", "unittest"], "created_at": "..."}
  ],
  "non_goals": ["no web UI"],
  "risks": ["fixtures are locale dependent"],
  "stop_conditions": ["gate green", "budget spent", "blocked 3 checkpoints", "no gain 3 checkpoints"]
}
```

Rules:

- `goal` **must** be falsifiable. "Improve the codebase" is not a goal.
- `done` **must** have 1–8 entries. Each entry **should** carry a `cmd`; without
  one it can still be checked, but the agent has to supply the command at check
  time, which is a worse position to be in.
- `deadline` **must** exist for runs longer than one hour. A shift with no end
  cannot be reported honestly.
- `non_goals` is not decoration. It is the vocabulary the drift detector uses to
  tell "off-plan" from "on-plan".

The flight plan is the **only** document that may be edited during a shift, and
only to *add* criteria or non-goals — never to remove or soften one after work
has started. Softening a criterion is moving the goalposts, and the report keeps
every criterion that ever existed.

---

## 2. Black box — `events.jsonl`

One JSON object per line, UTF-8, `\n` terminated. Append-only.

```json
{
  "v": 1,
  "id": "e000042",
  "ts": "2026-10-25T04:12:09+08:00",
  "kind": "step",
  "intent": "wire --input/--template/--out with clap derive",
  "target": "src/cli.rs",
  "action": {"type": "cmd", "cmd": ["cargo", "build"], "exit": 0, "ms": 2410},
  "evidence": [
    {"kind": "cmd", "ref": "evidence/1770000000-9f2c1a3b.txt",
     "digest": "sha256:...", "bytes": 812, "label": "cargo build"}
  ],
  "tags": []
}
```

### Event kinds

| kind | meaning | required fields |
| --- | --- | --- |
| `init` | the shift started | `intent` (the goal) |
| `step` | one meaningful unit of work | `intent`, `evidence[]` |
| `check` | a done-criterion was evaluated | `check.{id,passed,exit}` |
| `tick` | a checkpoint | `progress` (0–100, optional but required for convergence) |
| `note` | free text, never counts as proof | `intent` |
| `gate` | the agent asked for a verdict | `check.ok` |

- `id` is monotonically increasing: `e000001`, `e000002`, …
- `ts` is local time with offset, second precision.
- **Edits are forbidden.** A correction is a new event; a deletion is a lie.

### Ordering and time

The log is the source of truth for time. `report` uses the first event's `ts` as
the start of the shift and the *current wall clock* to compute remaining budget.

---

## 3. Evidence

An evidence item is a claim about bytes.

| kind | `ref` is | counts as proof? |
| --- | --- | --- |
| `cmd` | path to captured output | **yes** |
| `file` | path to a file on disk | **yes** |
| `test` | path to captured test output | **yes** |
| `url` | a URL | no |
| `note` | a path to typed text | **no** |

- `digest` is `sha256:<hex>` of the captured bytes, computed **before**
  truncation, stored after.
- Captured output is truncated to 64 KiB on disk; the digest still refers to the
  full byte stream as captured.
- Evidence is written at **action time**. Evidence reconstructed after the fact
  is indistinguishable from a forgery, so the protocol does not allow it: there
  is no command that attaches evidence to a past event.

> This is the single most important rule in the protocol. A receipt printed at
> 06:59 for work done at 02:00 proves only that a command runs *now*.

---

## 4. The gate

`nsh gate` exits `0` if and only if **all** of the following hold:

1. the flight plan has at least one done-criterion;
2. for every criterion `d`, the **latest** `check` event with `check.id == d.id`
   has `check.passed == true`;
3. that same event carries at least one evidence item whose `kind` is one of
   `cmd` / `file` / `test` and whose `digest` is non-empty.

It emits warnings (not failures) when:

- no `tick` events exist (an unauditable long run),
- fewer than 50 % of steps carry proof.

```
gate(done, events):
    checks = last check event per criterion id
    for d in done:
        e = checks[d.id]
        if e is None:            fail("never checked")
        if not e.check.passed:   fail("check failed", exit=e.check.exit)
        if not has_proof(e):     fail("no machine-checkable evidence")
    return ok = no failures
```

Exit codes: `0` green, `1` red, `2` usage error.

---

## 5. Detectors

All detectors are **heuristics**. They produce *flags*, never verdicts. The
report shows the score and the events behind every flag.

### D1 — topical drift

Tokenise each `step` intent and the plan's vocabulary (goal + done-criteria +
non-goals + risks). Score each step by **containment**:

```
score(step) = |tokens(step) ∩ vocab(plan)| / |tokens(step)|
```

For a sliding window of 6 steps, flag `off_topic` when the window mean is below
`0.12`. Containment (not Jaccard) because a long goal statement would otherwise
dilute a short, perfectly on-topic intent.

Tokenisation is bilingual: Latin words are lowercased and lightly stemmed
(trailing `s`), CJK runs become character bigrams. This is not real NLP and does
not want to be.

Checkpoints (`tick`) are excluded from the window — bookkeeping must not drag the
average down.

### D2 — silent run

Flag when **4 or more consecutive `step`s carry no proof** (`medium` at 4–7,
`high` at 8+). Motion without receipts is the most common way an agent lies
without lying.

### D3 — churn

Flag when the same `target` appears in **4 consecutive `step`s with no
intervening `check`**. Any `check` event clears all buckets.

Blind spot, stated out loud: if the agent never records `--target`, this detector
cannot fire. It is the single known false negative in the benchmark.

### D4 — unchecked criteria

Flag when 12+ steps have been logged and at least one done-criterion has never
been checked. Usually means the run is building something adjacent to the plan.

---

## 6. Convergence

Using the last 6 `tick` events that carry `progress`:

- `plateau` — max−min ≤ 3 points across ≥ 0.5 h,
- `regressing` — last value < first value,
- `improving` — otherwise.

A plateau is not a failure. It is the signal to stop polishing and write the
report, and it is the difference between an eight-hour shift and an eight-hour
tab.

---

## 7. The report

`nsh report` writes one self-contained HTML file (and optionally Markdown). The
following sections are **required**:

1. verdict + the number that justifies it,
2. wake-up brief,
3. proven criteria with evidence digests,
4. **not proven** criteria with the reason (may be empty only when the gate is green),
5. drift and near-misses,
6. convergence and activity,
7. non-goals and known risks,
8. appendix of raw events.

No JavaScript, no network requests, no external fonts. It must render in five
years on a laptop with no internet.

---

## 8. Threat model

What NIGHTSHIFT is **not** defending against:

- **A lying agent with shell access.** It can append fake `check` events. The
  protocol makes lying *visible* (you can diff the log against reality), not
  impossible. Run the checks yourself on a clean checkout if it matters.
- **A wrong done-criterion.** A green gate over a bad criterion is still green.
  The plan is the human's job.
- **Nondeterministic checks.** A flaky test is a bad criterion, not a tool bug.
- **Rewritten history.** Append-only is a convention plus a diffable text file.

What it *does* defend against, which is the common case: a well-meaning agent
that is tired, drifting, over-optimistic and has no idea it is any of those
things.

---

## 9. Versioning

`v` on the contract and on every event. Readers must ignore unknown fields.
Breaking changes bump `v` and the tool refuses to read a newer major version
rather than guessing.
