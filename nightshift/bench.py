"""Label the detector, not the model.

The drift detector is a set of cheap heuristics, so the honest question is:
*how often is it wrong?*  This module builds a labelled corpus of synthetic
agent runs, runs the real detector over them and prints precision / recall.

The corpus is synthetic and labelled by construction.  That makes these numbers
a regression test for the heuristics — not a scientific benchmark of real agent
behaviour.  `bench/cases/*.json` lets anyone add real runs to the same harness.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Sequence

from . import analysis, util

START = "2026-10-24T22:40:00+08:00"
DEADLINE = "2026-10-25T06:40:00+08:00"

GOAL = "ship the CSV-to-PDF report generator as a CLI: parser, templates, tests, docs, CI"
CRITERIA = [
    "parser handles all 12 fixture files",
    "CLI exposes --input/--template/--out",
    "three templates render without warnings",
    "test suite covers >= 90% of src/",
    "CI workflow is green on a clean checkout",
]
DRIFT_CODES = {"silent_run", "churn", "off_topic"}


# --------------------------------------------------------------------------- #
# corpus construction
# --------------------------------------------------------------------------- #

class _Builder:
    def __init__(self, goal: str = GOAL, criteria: Sequence[str] = CRITERIA,
                 start: str = START, deadline: str = DEADLINE):
        self.contract: dict[str, Any] = {
            "v": 1,
            "goal": goal,
            "done": [{"id": f"d{i + 1}", "text": t, "cmd": ["make", "check"]}
                     for i, t in enumerate(criteria)],
            "non_goals": ["a web UI", "PDF/A-3 compliance"],
            "risks": ["CSV fixtures are locale dependent"],
            "budget": {"started_at": start, "deadline": deadline, "hours": 8.0},
        }
        self.t = util.parse_iso(start)
        self.events: list[dict[str, Any]] = []

    def _mk(self, kind: str, intent: str, *, proof: bool = True, target: str = "",
            check: dict | None = None, progress: float | None = None) -> dict:
        self.t += timedelta(minutes=6)
        ev = []
        if proof:
            ev.append({
                "kind": "cmd",
                "ref": "evidence/%03d.txt" % (len(self.events) + 1),
                "digest": util.digest(intent + str(len(self.events))),
                "bytes": 120,
                "label": "exit 0",
            })
        rec = {
            "v": 1,
            "id": f"e{len(self.events) + 1:06d}",
            "ts": util.iso(self.t),
            "kind": kind,
            "intent": intent,
            "target": target,
            "evidence": ev,
        }
        if check:
            rec["check"] = check
        if progress is not None:
            rec["progress"] = progress
        self.events.append(rec)
        return rec

    def steps(self, n: int, intents: Sequence[str], *, proof: bool = True, target: str = "") -> None:
        for i in range(n):
            self._mk("step", intents[i % len(intents)], proof=proof, target=target)

    def check(self, cid: str, passed: bool = True, proof: bool = True) -> None:
        item = next(d for d in self.contract["done"] if d["id"] == cid)
        self._mk("check", f"check {cid}: {item['text']}", proof=proof, target=cid,
                 check={"id": cid, "passed": passed, "exit": 0 if passed else 1, "cmd": ["make", "check"]})

    def tick(self, progress: float) -> None:
        self._mk("tick", "checkpoint", proof=False, progress=progress)

    def case(self, name: str, *, drift: bool, gate_ok: bool) -> dict:
        return {"name": name, "expect_drift": drift, "expect_gate": gate_ok,
                "contract": self.contract, "events": self.events}


ON = [
    "write the CSV parser for quoted fields",
    "add parser unit test for locale decimal commas",
    "implement CLI flag parsing for --input and --out",
    "render the default invoice template",
    "fix template escaping of ampersands",
    "run the test suite and read the coverage report",
    "write the README section for --template",
    "add CI workflow for windows and linux",
]
OFF = [
    "rewrite the colour palette for the landing page",
    "answer an email about the office move",
    "look up ticket prices for the weekend",
    "tune the coffee grinder",
    "read a paper about black hole thermodynamics",
]


def build_cases() -> list[dict]:
    cases: list[dict] = []

    # 1. clean run -----------------------------------------------------------
    b = _Builder()
    b.steps(26, ON)
    for cid in ("d1", "d2", "d3", "d4", "d5"):
        b.check(cid)
    for p in (10, 25, 45, 65, 85, 100):
        b.tick(p)
    cases.append(b.case("clean-run", drift=False, gate_ok=True))

    # 2. false done: the classic -------------------------------------------
    b = _Builder()
    b.steps(22, ON)
    b.check("d1")
    b.check("d2")
    b.check("d3", passed=False)
    b.tick(70)
    cases.append(b.case("false-done", drift=False, gate_ok=False))

    # 3. silent run: motion without proof ----------------------------------
    b = _Builder()
    b.steps(6, ON)
    b.tick(20)
    b.steps(11, ON, proof=False)
    b.check("d1")
    b.tick(35)
    cases.append(b.case("silent-run", drift=True, gate_ok=False))

    # 4. churn: same file, no check ----------------------------------------
    b = _Builder()
    b.steps(5, ON)
    b.steps(6, ["polish the template renderer"], target="src/render.rs")
    b.check("d1")
    cases.append(b.case("churn", drift=True, gate_ok=False))

    # 5. off topic ----------------------------------------------------------
    b = _Builder()
    b.steps(6, ON)
    b.steps(10, OFF)
    b.check("d1")
    cases.append(b.case("off-topic", drift=True, gate_ok=False))

    # 6. messy but healthy (hard negative) ---------------------------------
    b = _Builder()
    pattern = [True, True, False, True, True, True, False, True, True, True]
    for i, p in enumerate(pattern * 3):
        b._mk("step", ON[i % len(ON)], proof=p)
        if i % 7 == 3:
            b.tick(10 + i * 3)
    for cid in ("d1", "d2", "d3", "d4", "d5"):
        b.check(cid)
    cases.append(b.case("messy-but-healthy", drift=False, gate_ok=True))

    # 7. every check passes, but evidence is only notes ---------------------
    b = _Builder()
    for i in range(20):
        b._mk("step", ON[i % len(ON)], proof=False, check=None)
        b.events[-1]["evidence"] = [{"kind": "note", "ref": "n", "digest": "sha256:x", "bytes": 1, "label": "note"}]
    for cid in ("d1", "d2", "d3", "d4", "d5"):
        b.check(cid, proof=True)
    cases.append(b.case("notes-are-not-proof", drift=True, gate_ok=True))

    # 8. short run ----------------------------------------------------------
    b = _Builder()
    b.steps(3, ON)
    for cid in ("d1", "d2", "d3", "d4", "d5"):
        b.check(cid)
    cases.append(b.case("short-run", drift=False, gate_ok=True))

    # 9. churn with checks in between (hard negative) ----------------------
    b = _Builder()
    b.steps(4, ON)
    for _ in range(5):
        b.steps(2, ["polish the template renderer"], target="src/render.rs")
        b.check("d3")
    for cid in ("d1", "d2", "d4", "d5"):
        b.check(cid)
    cases.append(b.case("churn-with-checks", drift=False, gate_ok=True))

    # 10. drift starts late -------------------------------------------------
    b = _Builder()
    b.steps(14, ON)
    b.steps(9, OFF)
    b.check("d1")
    cases.append(b.case("late-off-topic", drift=True, gate_ok=False))

    # 11. out of time -------------------------------------------------------
    b = _Builder()
    b.steps(18, ON)
    b.check("d1")
    b.check("d2")
    out = dict(b.contract)
    out["budget"] = dict(out["budget"])
    out["budget"]["deadline"] = "2026-10-24T23:30:00+08:00"
    cases.append({**b.case("out-of-time", drift=False, gate_ok=False), "contract": out})

    # 12. everything at once ------------------------------------------------
    b = _Builder()
    b.steps(4, ON)
    b.steps(5, ["polish the template renderer"], target="src/render.rs")
    b.steps(6, ON, proof=False)
    b.steps(6, OFF)
    b.check("d1")
    cases.append(b.case("everything-at-once", drift=True, gate_ok=False))

    # 13. hard negative: three silent steps are normal working rhythm ------
    b = _Builder()
    b.steps(4, ON)
    b.steps(3, ON, proof=False)
    b.steps(4, ON)
    for cid in ("d1", "d2", "d3", "d4", "d5"):
        b.check(cid)
    cases.append(b.case("three-silent-steps", drift=False, gate_ok=True))

    # 14. hard negative: on-topic work described in tooling jargon ---------
    b = _Builder()
    b.steps(6, ["bump clap to 4.5 and fix the derive macros",
                "wire serde_json into the fixture loader",
                "silence clippy on the renderer",
                "replace the stringly-typed template key",
                "add a criterion bench for the parser",
                "vendor the regex crate for the CI image"])
    b.steps(6, ON)
    for cid in ("d1", "d2", "d3", "d4", "d5"):
        b.check(cid)
    cases.append(b.case("jargon-run", drift=False, gate_ok=True))

    # 15. known blind spot: churn with no --target recorded ----------------
    # The detector cannot see what it was never told; this case is here so the
    # limitation stays visible instead of being quietly tuned away.
    b = _Builder()
    b.steps(4, ON)
    b.steps(5, ["polish the template renderer"])
    b.check("d1")
    cases.append(b.case("untargeted-churn", drift=True, gate_ok=False))

    # 16+ any user supplied cases ------------------------------------------
    extra_dir = Path(__file__).resolve().parent.parent / "bench" / "cases"
    if extra_dir.is_dir():
        for path in sorted(extra_dir.glob("*.json")):
            try:
                cases.append(json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                continue
    return cases


# --------------------------------------------------------------------------- #
# scoring
# --------------------------------------------------------------------------- #

def evaluate(cases: Sequence[dict]) -> dict[str, Any]:
    rows = []
    tp = fp = tn = fn = 0
    gate_hits = 0
    for c in cases:
        findings = analysis.drift(c["contract"], c["events"])
        codes = {f.code for f in findings}
        pred_drift = bool(codes & DRIFT_CODES)
        g = analysis.gate(c["contract"], c["events"])
        label = bool(c["expect_drift"])
        if pred_drift and label:
            tp += 1
        elif pred_drift and not label:
            fp += 1
        elif not pred_drift and not label:
            tn += 1
        else:
            fn += 1
        if g.ok == bool(c["expect_gate"]):
            gate_hits += 1
        rows.append({
            "name": c["name"],
            "expect_drift": label,
            "pred_drift": pred_drift,
            "codes": sorted(codes),
            "expect_gate": bool(c["expect_gate"]),
            "gate_ok": g.ok,
            "ok": (pred_drift == label) and (g.ok == bool(c["expect_gate"])),
        })
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {
        "n": len(cases),
        "drift": {"tp": tp, "fp": fp, "tn": tn, "fn": fn,
                  "precision": precision, "recall": recall, "f1": f1},
        "gate_accuracy": gate_hits / len(cases) if cases else 0.0,
        "rows": rows,
    }


def main(verbose: bool = True, as_json: bool = False) -> int:
    result = evaluate(build_cases())
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["drift"]["f1"] > 0.0 else 1
    if verbose:
        print()
        print(util.bold("  NIGHTSHIFT · detector benchmark"))
        print(util.grey("  labelled synthetic runs · " + str(result["n"]) + " cases"))
        print(util.grey("  " + "─" * 68))
        for r in result["rows"]:
            mark = util.green("✓") if r["ok"] else util.red("✗")
            drift = "drift" if r["pred_drift"] else "clean"
            want = "drift" if r["expect_drift"] else "clean"
            gate = "green" if r["gate_ok"] else "red  "
            want_gate = "green" if r["expect_gate"] else "red  "
            codes = ",".join(r["codes"]) or "-"
            print(f"  {mark} {util.pad(r['name'], 22)} {drift:>5}/{want:<5}  gate {gate}/{want_gate}  {util.grey(codes)}")
        d = result["drift"]
        print(util.grey("  " + "─" * 68))
        print(f"  drift detector   precision {d['precision']:.2f}   recall {d['recall']:.2f}   f1 {d['f1']:.2f}")
        print(f"  gate             accuracy {result['gate_accuracy']:.2f}")
        print(util.grey(f"  confusion  tp={d['tp']} fp={d['fp']} tn={d['tn']} fn={d['fn']}"))
        print(util.grey("  these numbers are a regression test, not a benchmark of real agents."))
        print()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
