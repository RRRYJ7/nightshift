"""``nsh demo`` — a deterministic 7.5-hour run, so the report can be seen in 3 seconds.

Nothing here fakes the tool: it writes a real black box (events, evidence files,
sha256 digests) and renders it through the same code path a real shift uses.
Only the *content* of the run is scripted.
"""

from __future__ import annotations

import shutil
from datetime import timedelta
from pathlib import Path

from . import analysis, report, util
from .store import Store

DEMO_GOAL = "ship the CSV-to-PDF report generator as a CLI: parser, templates, tests, docs, CI"
DEMO_CRITERIA = [
    ("d1", "parser handles all 12 fixture files", ["cargo", "test", "parser"]),
    ("d2", "CLI exposes --input/--template/--out", ["cargo", "test", "cli"]),
    ("d3", "three templates render without warnings", ["cargo", "test", "render"]),
    ("d4", "test suite covers >= 90% of src/", ["cargo", "tarpaulin", "--fail-under", "90"]),
    ("d5", "CI workflow is green on a clean checkout", ["act", "-j", "test"]),
]

# Flat script: (kind, payload, weight).  Weight only controls how much wall-clock
# the step is given when the whole script is stretched onto a 7h32m shift.
SCRIPT: list[tuple[str, object, float]] = [
    ("step", ("scaffold the cargo workspace and CLI entrypoint", True, "Cargo.toml"), 1.0),
    ("step", ("write the CSV lexer for quoted fields", True, "src/parser.rs"), 1.0),
    ("step", ("handle CRLF and BOM in the lexer", True, "src/lexer.rs"), 1.0),
    ("step", ("add fixtures 01-03 and a parser test", True, "tests/parser.rs"), 1.0),
    ("step", ("fix quoted-field escape handling", True, "src/parser.rs"), 1.0),
    ("wait", 0.8, 1.4),
    ("check", "d1", 0.3),
    ("tick", 16.0, 0.4),
    ("wait", 0.9, 2.2),
    ("step", ("wire --input/--template/--out with clap derive", True, "src/cli.rs"), 1.0),
    ("step", ("print a useful --help screen", True, "src/cli.rs"), 1.0),
    ("check", "d2", 0.3),
    ("tick", 32.0, 0.4),
    ("step", ("render the invoice template", True, "src/template.rs"), 1.0),
    ("step", ("escape ampersands in the PDF backend", True, "src/render.rs"), 1.0),
    ("step", ("make template lookup case-insensitive", True, "src/template.rs"), 1.0),
    ("wait", 0.7, 1.8),
    ("step", ("run the parser fixture suite", True, "tests/parser.rs"), 1.0),
    ("step", ("triage the two failing locale fixtures", True, "tests/fixtures.rs"), 1.0),
    ("step", ("pin the locale in the test harness", True, "tests/parser.rs"), 1.0),
    ("step", ("re-run fixtures", True, "src/parser.rs"), 1.0),
    ("tick", 47.0, 0.4),
    ("wait", 1.0, 2.6),
    ("step", ("write the README section for --template", True, "README.md"), 1.0),
    # the churn: five touches on one file, no check in between
    ("step", ("polish the template renderer spacing", True, "src/render.rs"), 1.0),
    ("step", ("polish the template renderer again", True, "src/render.rs"), 1.0),
    ("step", ("polish the template renderer once more", True, "src/render.rs"), 1.0),
    ("step", ("tune the baseline spacing constants", True, "src/render.rs"), 1.0),
    ("step", ("final spacing pass on the renderer", True, "src/render.rs"), 1.0),
    ("check", "d3", 0.3),
    ("tick", 61.0, 0.4),
    ("wait", 0.6, 1.7),
    # the silent run: five steps that produced no machine-checkable proof
    ("step", ("think about the coverage gap", False, "tests/coverage.rs"), 1.0),
    ("step", ("read the tarpaulin docs", False, "docs/coverage.md"), 1.0),
    ("step", ("try a different coverage flag", False, "Cargo.toml"), 1.0),
    ("step", ("compare two coverage reports by hand", False, "tests/coverage.rs"), 1.0),
    ("step", ("decide the coverage target is reachable", False, "docs/coverage.md"), 1.0),
    ("wait", 0.8, 1.5),
    ("step", ("add tests for the template lookup table", True, "tests/render.rs"), 1.0),
    ("step", ("add a test for empty input", True, "tests/render.rs"), 1.0),
    ("step", ("cover the error branch in the CLI", True, "tests/cli.rs"), 1.0),
    ("check", "d4", 0.3),
    ("tick", 79.0, 0.4),
    ("wait", 0.7, 2.0),
    ("step", ("add the CI workflow for windows and linux", True, ".github/workflows/ci.yml"), 1.0),
    ("step", ("cache cargo between jobs", True, ".github/workflows/ci.yml"), 1.0),
    ("step", ("pin the toolchain version", True, "rust-toolchain.toml"), 1.0),
    ("check", "d5", 0.3),
    ("tick", 92.0, 0.4),
    ("step", ("write the README quickstart", True, "README.md"), 1.0),
    ("step", ("add a worked example with a real CSV", True, "examples/invoice.csv"), 1.0),
    ("tick", 100.0, 0.4),
]

TOTAL_MINUTES = 7 * 60 + 32


def _check_output(cid: str, text: str) -> str:
    """A distinct, plausible test transcript per criterion (distinct digests matter)."""
    names = {
        "d1": ["parser::quoted_fields", "parser::crlf", "parser::bom", "parser::empty_row"],
        "d2": ["cli::rejects_missing_input", "cli::accepts_out_flag", "cli::help_mentions_template"],
        "d3": ["render::invoice", "render::receipt", "render::statement"],
        "d4": ["coverage::parser", "coverage::render"],
        "d5": ["ci::checkout", "ci::test", "ci::upload_artifact"],
    }.get(cid, ["check::main"])
    body = "\n".join("test %s ... ok" % n for n in names)
    return (
        "$ make check %s   # %s\n"
        "   Compiling reports v0.3.1\n"
        "    Finished test [unoptimized + debuginfo]\n\n"
        "running %d tests\n%s\n\n"
        "test result: ok. %d passed; 0 failed; 0 ignored\n"
        "exit 0\n"
    ) % (cid, text, len(names), body, len(names))


def _evidence_for(intent: str) -> str:
    if intent.startswith("check"):
        return (
            "$ make check\n"
            "   Compiling reports v0.3.1\n"
            "    Finished test [unoptimized + debuginfo]\n"
            "     Running unittests src/lib.rs\n\n"
            "running 16 tests\n"
            "test result: ok. 16 passed; 0 failed; 0 ignored\n"
            "exit 0\n"
        )
    if "README" in intent:
        return "$ pandoc README.md -o /tmp/readme.html && echo rendered\nrendered\n"
    if "fixture" in intent or "locale" in intent or "test" in intent:
        return (
            "$ cargo test\n"
            "running 14 tests\n"
            "test parser::quoted_fields ... ok\n"
            "test parser::crlf ... ok\n"
            "test result: ok. 14 passed; 0 failed; 0 ignored\n"
        )
    if "CI" in intent or "cache" in intent or "toolchain" in intent:
        return "$ act -j test --dryrun\n[CI/test] Starting\n[CI/test] ✓ checkout\n[CI/test] ✓ cargo test\nexit 0\n"
    return (
        "$ cargo build --all-targets\n"
        "   Compiling reports v0.3.1\n"
        "    Finished dev [unoptimized + debuginfo] target(s) in 2.41s\n"
        "exit 0\n"
    )


def build(dest: str | Path = ".nightshift-demo") -> Store:
    root = Path(dest)
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    st = Store(root)

    start = util.now() - timedelta(minutes=TOTAL_MINUTES)
    contract = {
        "v": 1,
        "tool": "nightshift demo",
        "goal": DEMO_GOAL,
        "created_at": util.iso(start),
        "budget": {
            "started_at": util.iso(start),
            "deadline": util.iso(start + timedelta(hours=8)),
            "hours": 8.0,
        },
        "done": [
            {"id": cid, "text": text, "cmd": cmd, "evidence_hint": "", "created_at": util.iso(start)}
            for cid, text, cmd in DEMO_CRITERIA
        ],
        "non_goals": ["a web UI", "PDF/A-3 compliance", "localisation beyond en/de"],
        "risks": [
            "CSV fixtures are locale dependent",
            "tarpaulin coverage differs between windows and linux",
        ],
        "stop_conditions": [
            "every done-criterion passes with evidence",
            "budget spent and gate red -> stop and report",
        ],
    }
    st.save_contract(contract)
    st.append({"kind": "init", "intent": DEMO_GOAL, "evidence": []}, ts=start)

    total_weight = sum(float(w) for _, _, w in SCRIPT) or 1.0
    cum = 0.0
    for kind, payload, weight in SCRIPT:
        cum += float(weight)
        t = start + timedelta(minutes=TOTAL_MINUTES * cum / total_weight)
        if kind == "step":
            intent, proof, target = payload  # type: ignore[misc]
            evidence = []
            if proof:
                evidence.append(st.save_evidence(_evidence_for(str(intent)), kind="cmd", label=str(intent)))
            st.append({"kind": "step", "intent": str(intent), "target": str(target),
                       "evidence": evidence}, ts=t)
        elif kind == "check":
            cid = str(payload)
            item = next((d for d in contract["done"] if d["id"] == cid), None)
            ev = st.save_evidence(_check_output(cid, item["text"] if item else ""),
                                  kind="cmd", label=f"check {cid}")
            st.append(
                {
                    "kind": "check",
                    "intent": f"check {cid}: {item['text'] if item else ''}",
                    "target": cid,
                    "check": {"id": cid, "passed": True, "exit": 0, "cmd": item.get("cmd") if item else None},
                    "evidence": [ev],
                },
                ts=t,
            )
        elif kind == "tick":
            st.append({"kind": "tick", "intent": "checkpoint", "progress": float(payload),
                       "target": "", "evidence": []}, ts=t)
        # "wait" only consumes wall-clock
    return st


def main(dest: str = ".nightshift-demo", open_report: bool = False) -> int:
    st = build(dest)
    a = analysis.analyse(st)
    path = report.write_report(st, a, fmt="html", project="reports-cli")
    report.write_report(st, a, fmt="md", project="reports-cli")

    print()
    print("  " + util.bold("NIGHTSHIFT · demo shift") + "  " + util.grey("(scripted run, real tool)"))
    print("  " + util.grey("─" * 62))
    for line in a["brief"]:
        key, _, rest = line.partition(" ")
        print(f"  {util.cyan(util.pad(key, 9))}{rest}")
    print("  " + util.grey("─" * 62))
    print(f"  report → {path}")
    print()
    if open_report:
        import os

        if os.name == "nt":
            try:
                os.startfile(path)  # type: ignore[attr-defined]
            except OSError:
                pass
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
