"""Judgement: turn a black-box log into a verdict a human can trust.

Everything in here is a pure function over (flight plan, event log) so it can be
tested without touching the filesystem.  The heuristics are deliberately simple
and every number they produce is shown to the human, because a detector you
cannot inspect is just another thing to trust blindly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Iterable, Sequence

from . import util

# Tuned on bench/cases (see docs/BENCHMARKS.md); exposed so humans can argue.
DRIFT_SIM_FLOOR = 0.12
DRIFT_WINDOW = 6
SILENT_RUN_MEDIUM = 4
SILENT_RUN_HIGH = 8
CHURN_MEDIUM = 4
BUDGET_WARN = 0.85

PROVEN_KINDS = {"cmd", "file", "test"}


# --------------------------------------------------------------------------- #
# data types
# --------------------------------------------------------------------------- #

@dataclass
class Finding:
    code: str
    severity: str          # high | medium | low
    title: str
    detail: str
    at: str = ""
    ids: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "title": self.title,
            "detail": self.detail,
            "at": self.at,
            "ids": self.ids,
        }


@dataclass
class GateResult:
    ok: bool
    passes: list[dict[str, Any]]
    failures: list[dict[str, Any]]
    warnings: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "passes": self.passes,
            "failures": self.failures,
            "warnings": self.warnings,
        }


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #

def _ts(ev: dict) -> datetime:
    try:
        return util.parse_iso(ev.get("ts", ""))
    except Exception:
        return util.now()


def _has_proof(ev: dict) -> bool:
    for item in ev.get("evidence") or []:
        if item.get("kind") in PROVEN_KINDS and (item.get("digest") or item.get("ref")):
            return True
    return False


def has_proof(ev: dict) -> bool:
    """Public alias, used by the CLI."""
    return _has_proof(ev)


def _evidence_items(ev: dict) -> list[dict]:
    return [e for e in (ev.get("evidence") or []) if e.get("kind")]


def latest_checks(events: Sequence[dict]) -> dict[str, dict]:
    """Latest ``check`` event per criterion id."""
    out: dict[str, dict] = {}
    for ev in events:
        if ev.get("kind") == "check":
            chk = ev.get("check") or {}
            cid = chk.get("id")
            if cid:
                out[cid] = ev
    return out


def latest_ticks(events: Sequence[dict], limit: int | None = None) -> list[dict]:
    ticks = [e for e in events if e.get("kind") == "tick"]
    return ticks[-limit:] if limit else ticks


# --------------------------------------------------------------------------- #
# gate: is "done" actually done?
# --------------------------------------------------------------------------- #

def gate(contract: dict, events: Sequence[dict]) -> GateResult:
    checks = latest_checks(events)
    passes: list[dict] = []
    failures: list[dict] = []
    warnings: list[str] = []

    criteria = contract.get("done") or []
    if not criteria:
        failures.append(
            {
                "id": "-",
                "text": "the flight plan has no done-criteria",
                "why": "you cannot prove a task you never defined",
            }
        )

    for item in criteria:
        cid = item.get("id", "?")
        text = item.get("text", "")
        ev = checks.get(cid)
        if ev is None:
            failures.append({"id": cid, "text": text, "why": "never checked"})
            continue
        chk = ev.get("check") or {}
        if not chk.get("passed"):
            failures.append(
                {
                    "id": cid,
                    "text": text,
                    "why": "check failed (exit %s)" % chk.get("exit"),
                    "at": ev.get("ts", ""),
                }
            )
            continue
        if not _has_proof(ev):
            failures.append(
                {
                    "id": cid,
                    "text": text,
                    "why": "check passed but no machine-checkable evidence was attached",
                    "at": ev.get("ts", ""),
                }
            )
            continue
        passes.append(
            {
                "id": cid,
                "text": text,
                "at": ev.get("ts", ""),
                "evidence": _evidence_items(ev),
            }
        )

    stats_ = quick_stats(contract, events)
    if criteria and not latest_ticks(events) and (stats_["steps"] >= 8 or stats_["wall_s"] > 1800):
        warnings.append("no checkpoints were recorded - a long run without checkpoints cannot be audited")

    if stats_["steps"] and stats_["coverage"] < 0.5:
        warnings.append(
            "only %s of steps carry evidence - the report will be thin" % util.pct(stats_["coverage"])
        )

    return GateResult(ok=not failures, passes=passes, failures=failures, warnings=warnings)


# --------------------------------------------------------------------------- #
# drift: is the agent still working on the thing it promised?
# --------------------------------------------------------------------------- #

def _contract_vocabulary(contract: dict) -> set[str]:
    blob = " ".join(
        [
            contract.get("goal", ""),
            " ".join(str(x) for x in contract.get("non_goals") or []),
            " ".join(str(d.get("text", "")) for d in contract.get("done") or []),
            " ".join(str(x) for x in contract.get("risks") or []),
        ]
    )
    return util.tokenize(blob)


def drift(contract: dict, events: Sequence[dict]) -> list[Finding]:
    findings: list[Finding] = []
    steps = [e for e in events if e.get("kind") in ("step", "check", "tick")]
    if len(steps) < 2:
        return findings

    vocab = _contract_vocabulary(contract)

    # -- D2: silent run (activity with no evidence) -------------------------
    run = 0
    worst: list[dict] = []
    for ev in steps:
        if ev.get("kind") == "step" and not _has_proof(ev):
            run += 1
            worst.append(ev)
        else:
            if run >= SILENT_RUN_MEDIUM:
                findings.append(_silent_finding(run, worst, closed=True))
            run = 0
            worst = []
    if run >= SILENT_RUN_MEDIUM:
        findings.append(_silent_finding(run, worst, closed=False))

    # -- D1: topical drift --------------------------------------------------
    # containment (share of the step's words that appear in the flight plan)
    # rather than jaccard: one short, on-topic intent must not be diluted by a
    # long goal statement.
    sims: list[tuple[dict, float]] = []
    # checkpoints are bookkeeping, not work: they must not drag the window down
    for ev in [e for e in steps if e.get("kind") == "step"]:
        toks = util.tokenize(str(ev.get("intent", "")))
        if not toks:
            continue
        sims.append((ev, util.overlap(toks, vocab)))
    for i in range(DRIFT_WINDOW, len(sims)):
        window = sims[i - DRIFT_WINDOW : i]
        mean = sum(s for _, s in window) / len(window)
        if mean < DRIFT_SIM_FLOOR:
            ev = sims[i][0]
            findings.append(
                Finding(
                    "off_topic",
                    "medium",
                    "last %d steps barely overlap the flight plan (score %.3f)" % (DRIFT_WINDOW, mean),
                    "recent intents: "
                    + " / ".join(str(e.get("intent", ""))[:48] for e, _ in window[-3:]),
                    at=ev.get("ts", ""),
                    ids=[e.get("id", "") for e, _ in window],
                )
            )
            break

    # -- D3: churn on the same target ---------------------------------------
    seen: dict[str, list[dict]] = {}
    for ev in steps:
        if ev.get("kind") == "check":
            for bucket in seen.values():
                bucket.clear()
            continue
        target = (ev.get("target") or "").strip()
        if not target:
            continue
        bucket = seen.setdefault(target, [])
        bucket.append(ev)
        if len(bucket) == CHURN_MEDIUM:
            findings.append(
                Finding(
                    "churn",
                    "medium",
                    "`%s` touched %dx with no check in between" % (target, CHURN_MEDIUM),
                    "classic polishing loop: motion without a pass/fail",
                    at=ev.get("ts", ""),
                    ids=[e.get("id", "") for e in bucket],
                )
            )
            bucket.clear()

    # -- D4: criteria never checked -----------------------------------------
    checks = latest_checks(events)
    unchecked = [d for d in (contract.get("done") or []) if d.get("id") not in checks]
    if unchecked and len(steps) >= 12:
        findings.append(
            Finding(
                "unchecked_criteria",
                "medium",
                "%d done-criteria have never been checked" % len(unchecked),
                ", ".join("%s: %s" % (d.get("id"), util.one_line(d.get("text", ""), 40)) for d in unchecked[:4]),
                at=steps[-1].get("ts", ""),
            )
        )

    return findings


def _silent_finding(run: int, worst: list[dict], closed: bool) -> Finding:
    sev = "high" if run >= SILENT_RUN_HIGH else "medium"
    title = "%d steps in a row with no evidence" % run + ("" if closed else " (still open)")
    return Finding(
        "silent_run",
        sev,
        title,
        "%r ... %r" % (worst[0].get("intent", ""), worst[-1].get("intent", "")),
        at=worst[0].get("ts", ""),
        ids=[e.get("id", "") for e in worst[:6]],
    )


# --------------------------------------------------------------------------- #
# convergence: is more work buying anything?
# --------------------------------------------------------------------------- #

def convergence(events: Sequence[dict]) -> dict[str, Any]:
    ticks = [e for e in latest_ticks(events) if isinstance((e.get("progress")), (int, float))]
    if len(ticks) < 3:
        return {"state": "unknown", "why": "fewer than 3 checkpoints carried a progress number"}
    pts = [(e.get("ts", ""), float(e["progress"])) for e in ticks[-6:]]
    values = [v for _, v in pts]
    span = max(values) - min(values)
    gain = values[-1] - values[0]
    hours = _hours_between(pts[0][0], pts[-1][0])
    state = "improving"
    if span <= 3.0 and hours >= 0.5:
        state = "plateau"
    elif gain < 0:
        state = "regressing"
    return {
        "state": state,
        "points": pts,
        "gain": gain,
        "span": span,
        "hours": hours,
        "why": {
            "plateau": "progress moved less than 3 points across the last checkpoints - more polishing is unlikely to pay",
            "improving": "still climbing: +%g points over %.1fh" % (gain, hours),
            "regressing": "progress went backwards - the last steps may have broken something",
        }[state],
    }


def _hours_between(a: str, b: str) -> float:
    try:
        return max(0.0, (_ts({"ts": b}) - _ts({"ts": a})).total_seconds() / 3600.0)
    except Exception:
        return 0.0


# --------------------------------------------------------------------------- #
# statistics
# --------------------------------------------------------------------------- #

def quick_stats(contract: dict, events: Sequence[dict]) -> dict[str, Any]:
    steps = [e for e in events if e.get("kind") == "step"]
    checks = [e for e in events if e.get("kind") == "check"]
    ticks = [e for e in events if e.get("kind") == "tick"]
    proven = [e for e in steps if _has_proof(e)]
    evidence_n = sum(len(_evidence_items(e)) for e in events)
    checked = latest_checks(events)

    started = _ts(events[0]) if events else util.now()
    last = _ts(events[-1]) if events else started
    deadline = None
    raw_deadline = (contract.get("budget") or {}).get("deadline")
    if raw_deadline:
        try:
            deadline = util.parse_iso(raw_deadline)
        except Exception:
            deadline = None

    now = util.now()
    wall = (now - started).total_seconds()
    remaining = (deadline - now).total_seconds() if deadline else None

    return {
        "started_at": util.iso(started),
        "last_at": util.iso(last),
        "deadline": util.iso(deadline) if deadline else None,
        "elapsed_s": (last - started).total_seconds(),
        "wall_s": wall,
        "remaining_s": remaining,
        "steps": len(steps),
        "proven_steps": len(proven),
        "coverage": (len(proven) / len(steps)) if steps else 0.0,
        "checks": len(checks),
        "ticks": len(ticks),
        "evidence": evidence_n,
        "criteria": len(contract.get("done") or []),
        "criteria_passed": sum(
            1
            for d in (contract.get("done") or [])
            if (checked.get(d.get("id")) or {}).get("check", {}).get("passed")
        ),
        "events": len(events),
    }


def hourly(events: Sequence[dict]) -> list[tuple[str, int]]:
    """Event counts bucketed by hour, for the activity chart."""
    if not events:
        return []
    buckets: dict[str, int] = {}
    for ev in events:
        key = _ts(ev).strftime("%H:00")
        buckets[key] = buckets.get(key, 0) + 1
    return sorted(buckets.items())


def coverage_series(events: Sequence[dict], step: int = 5) -> list[float]:
    """Rolling share of recent steps that carried evidence."""
    flags = [_has_proof(e) if e.get("kind") == "step" else None for e in events]
    flags = [f for f in flags if f is not None]
    if not flags:
        return []
    out = []
    for i in range(len(flags)):
        lo = max(0, i - step + 1)
        chunk = flags[lo : i + 1]
        out.append(sum(1 for x in chunk if x) / len(chunk))
    return out


# --------------------------------------------------------------------------- #
# the verdict + the wake-up brief
# --------------------------------------------------------------------------- #

def verdict(stats: dict, g: GateResult, conv: dict, findings: Sequence[Finding]) -> dict[str, Any]:
    if g.ok:
        return {"code": "proven", "label": "DONE & PROVEN", "tone": "good",
                "why": "all %d done-criteria passed with evidence" % len(g.passes)}
    high = [f for f in findings if f.severity == "high"]
    if stats["remaining_s"] is not None and stats["remaining_s"] < 0:
        return {"code": "out_of_time", "label": "BUDGET SPENT · GATE RED", "tone": "bad",
                "why": "%d criteria unproven when the clock ran out" % len(g.failures)}
    if stats["checks"] or stats["coverage"] > 0.3:
        why = "%d of %d criteria unproven" % (len(g.failures), stats["criteria"])
        if high:
            why += ", %d high-severity drift flags" % len(high)
        return {"code": "partial", "label": "PARTIAL · NOT PROVEN", "tone": "warn", "why": why}
    return {"code": "unproven", "label": "NOT DONE", "tone": "bad", "why": "nothing was proven"}


def brief(contract: dict, events: Sequence[dict], stats: dict, g: GateResult,
          conv: dict, findings: Sequence[Finding]) -> list[str]:
    """Ten lines a human can read at 10:30 with coffee in hand."""
    lines: list[str] = []
    goal = util.one_line(contract.get("goal", ""), 96)
    lines.append("GOAL     " + goal)
    used = util.human_dur(stats["wall_s"])
    if stats["remaining_s"] is None:
        lines.append("WINDOW   no deadline set · %s elapsed" % used)
    else:
        left = stats["remaining_s"]
        if left >= 0:
            lines.append("WINDOW   %s used · %s left" % (used, util.human_dur(left)))
        else:
            lines.append("WINDOW   %s past the deadline" % util.human_dur(-left))
    lines.append(
        "ACTIVITY %s · %s · %s · %s of evidence"
        % (util.plural(stats["steps"], "step"), util.plural(stats["checks"], "check"),
           util.plural(stats["ticks"], "checkpoint"), util.plural(stats["evidence"], "piece", "pieces"))
    )
    lines.append(
        "EVIDENCE %s of steps carry proof (%d/%d)"
        % (util.pct(stats["coverage"]), stats["proven_steps"], stats["steps"])
    )
    gate_line = "GATE     %s · %s/%s criteria proven" % (
        "GREEN" if g.ok else "RED", stats["criteria_passed"], stats["criteria"])
    if not g.ok and g.failures:
        gate_line += " - first blocker: " + util.one_line(g.failures[0]["why"], 46)
    lines.append(gate_line)
    if findings:
        top = sorted(findings, key=lambda f: {"high": 0, "medium": 1, "low": 2}[f.severity])[:2]
        lines.append("RISK     " + " | ".join("%s: %s" % (f.severity, util.one_line(f.title, 52)) for f in top))
    else:
        lines.append("RISK     no drift flags")
    if conv.get("state") in ("plateau", "regressing"):
        lines.append("TREND    %s - %s" % (conv["state"], util.one_line(conv.get("why", ""), 62)))
    elif conv.get("state") == "improving":
        lines.append("TREND    improving - %s" % util.one_line(conv.get("why", ""), 62))
    else:
        lines.append("TREND    unknown - log checkpoints with --progress to unlock convergence detection")
    if g.failures:
        lines.append("NOT DONE " + "; ".join(
            "%s: %s" % (f["id"], util.one_line(f.get("text", ""), 28)) for f in g.failures[:3]))
    return lines


# --------------------------------------------------------------------------- #
# one call that gathers everything the renderer needs
# --------------------------------------------------------------------------- #

def analyse(store) -> dict[str, Any]:
    contract = store.load_contract()
    events = store.events()
    stats = quick_stats(contract, events)
    g = gate(contract, events)
    findings = drift(contract, events)
    conv = convergence(events)
    v = verdict(stats, g, conv, findings)
    return {
        "contract": contract,
        "events": events,
        "stats": stats,
        "gate": g,
        "findings": findings,
        "convergence": conv,
        "verdict": v,
        "brief": brief(contract, events, stats, g, conv, findings),
        "hourly": hourly(events),
        "coverage_series": coverage_series(events),
    }
