"""``nsh`` — the command line an agent drives and a human reads.

Design rules:
  * every command is safe to call from an agent loop (no prompts, no pagers);
  * every command that records something prints what it recorded;
  * exit codes are meaningful: 0 ok, 1 gate/check failed, 2 usage error.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Sequence

from . import __version__, analysis, report, store as store_mod, util
from .store import NightshiftError, Store, find_root, run_capture

BANNER = "✈ NIGHTSHIFT"


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def _store(args: argparse.Namespace) -> Store:
    if getattr(args, "dir", None):
        return Store(args.dir)
    root = find_root()
    return Store(root if root else store_mod.DEFAULT_DIR)


def _need(args: argparse.Namespace) -> Store:
    return _store(args).require()


def _rule(width: int = 64, ch: str = "─") -> str:
    return util.grey(ch * width)


def _head(title: str, sub: str = "") -> None:
    print()
    print(util.bold(f"{BANNER} · ") + util.bold(title) + (f"  {util.grey(sub)}" if sub else ""))
    print(_rule())


def _kv(key: str, value: str, width: int = 12) -> str:
    return f"  {util.grey(util.pad(key, width))}{value}"


def _ev_line(ev: dict) -> str:
    n = len(ev.get("evidence") or [])
    mark = util.green("●") if n else util.grey("○")
    return f"  {mark} {util.grey(ev.get('ts', '')[11:19])} {util.grey(ev.get('id', ''))} {util.one_line(ev.get('intent', ''), 88)}"


# --------------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------------- #

def cmd_init(args: argparse.Namespace) -> int:
    st = Store(args.dir or store_mod.DEFAULT_DIR)
    deadline = None
    if args.deadline:
        try:
            deadline = util.parse_deadline(args.deadline)
        except ValueError as exc:
            raise NightshiftError(str(exc))
    contract = st.init(
        goal=args.goal,
        deadline=deadline,
        hours=args.hours,
        non_goals=args.non_goal or [],
        risks=args.risk or [],
        force=args.force,
    )
    _head("flight plan created", str(st.root))
    print(_kv("goal", contract["goal"]))
    budget = contract["budget"]
    print(_kv("deadline", budget["deadline"] or util.yellow("none — long runs need one")))
    print()
    print(util.grey("  next:"))
    print(util.grey('    nsh done add "tests green" -- python -m unittest'))
    print(util.grey('    nsh run -- python build.py'))
    print(util.grey('    nsh tick --progress 20 --note "scaffold done"'))
    print(util.grey("    nsh gate"))
    print()
    return 0


def cmd_done(args: argparse.Namespace) -> int:
    if args.action == "add":
        st = _need(args)
        cmd = _clean_cmd(args.cmd)
        item = st.add_done(args.text, cmd=cmd)
        print(f"  {util.green('+')} {util.bold(item['id'])} {item['text']}"
              + (f"  {util.grey('$ ' + ' '.join(cmd))}" if cmd else f"  {util.yellow('(no check command)')}"))
        return 0
    if args.action == "ls":
        st = _need(args)
        contract = st.load_contract()
        checks = analysis.latest_checks(st.events())
        _head("done-criteria", st.load_contract().get("goal", "")[:60])
        if not contract.get("done"):
            print(util.grey("  none yet — nsh done add \"...\" -- <check command>"))
        for item in contract.get("done", []):
            ev = checks.get(item["id"])
            if ev is None:
                mark, extra = util.grey("○"), util.grey("never checked")
            elif ev.get("check", {}).get("passed") and analysis._has_proof(ev):
                mark, extra = util.green("●"), util.green("proven")
            elif ev.get("check", {}).get("passed"):
                mark, extra = util.yellow("◐"), util.yellow("passed, no evidence attached")
            else:
                mark, extra = util.red("✗"), util.red("failed")
            print(f"  {mark} {util.bold(item['id'])}  {util.pad(item['text'], 58)} {extra}")
            if item.get("cmd"):
                print(util.grey(f"       $ {' '.join(item['cmd'])}"))
        print()
        return 0
    if args.action == "rm":
        st = _need(args)
        ok = st.remove_done(args.text)
        print(("  removed " if ok else "  not found ") + args.text)
        return 0 if ok else 1
    return 2


def cmd_step(args: argparse.Namespace) -> int:
    st = _need(args)
    evidence = []
    for path in args.evidence or []:
        evidence.append(st.file_evidence(path))
    if args.note:
        evidence.append(st.save_evidence(args.note, kind="note", label="note"))
    ev = st.append({
        "kind": "step",
        "intent": " ".join(args.text.split()),
        "target": args.target or "",
        "evidence": evidence,
        "tags": args.tag or [],
    })
    print(_ev_line(ev) + (f"  {util.grey(str(len(evidence)) + ' evidence')}" if evidence else ""))
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    st = _need(args)
    cmd = _clean_cmd(args.cmd)
    if not cmd:
        raise NightshiftError("nothing to run: nsh run -- <command>")
    res = run_capture(cmd, timeout=args.timeout)
    saved = st.save_evidence(res["text"], kind="cmd", label=" ".join(cmd))
    ev_item = {
        "kind": "cmd",
        "ref": saved["ref"],
        "digest": saved["digest"],
        "bytes": saved["bytes"],
        "bytes_total": saved.get("bytes_total"),
        "truncated": saved.get("truncated", False),
        "label": f"exit {res['exit']} · {res['ms']}ms" + (" · capped" if res.get("capped") else ""),
    }
    ev = st.append({
        "kind": "step",
        "intent": (args.intent or " ".join(cmd)),
        "target": args.target or "",
        "action": {"type": "cmd", "cmd": cmd, "exit": res["exit"], "ms": res["ms"]},
        "evidence": [ev_item],
        "tags": args.tag or [],
    })
    status = util.green("ok") if res["exit"] == 0 else util.red("exit %d" % res["exit"])
    took = util.grey("(%s)" % util.human_dur(res["ms"] / 1000.0)) if res["ms"] > 1200 else ""
    print(_ev_line(ev) + f"  {status} {took}")
    tail = [ln for ln in res["text"].splitlines() if ln.strip()][-3:]
    for ln in tail:
        print(util.grey("      │ " + util.one_line(ln, 100)))
    if args.show and res["text"]:
        print(res["text"])
    if res["exit"] != 0 and not args.allow_fail:
        return 1
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    st = _need(args)
    contract = st.load_contract()
    if args.all:
        ids = [d["id"] for d in contract.get("done", [])]
        if not ids:
            raise NightshiftError("no done-criteria to check")
        worst = 0
        for cid in ids:
            worst = max(worst, _run_check(st, contract, cid, [], args.timeout))
        return worst
    if not args.id:
        raise NightshiftError("nothing to check: nsh check <id>  or  nsh check --all")
    return _run_check(st, contract, args.id, _clean_cmd(args.cmd), args.timeout)


def _run_check(st: Store, contract: dict, cid: str, override: list[str], timeout: int) -> int:
    item = next((d for d in contract.get("done", []) if d["id"] == cid), None)
    if item is None:
        raise NightshiftError(f"no done-criterion {cid!r}; try: nsh done ls")
    cmd = override or item.get("cmd")
    if not cmd:
        raise NightshiftError(
            f"{cid} has no check command. pass one: nsh check {cid} -- <command>"
        )
    res = run_capture(cmd, timeout=timeout)
    passed = res["exit"] == 0
    saved = st.save_evidence(res["text"], kind="cmd", label=f"check {cid}")
    evidence = [{
        "kind": "cmd",
        "ref": saved["ref"],
        "digest": saved["digest"],
        "bytes": saved["bytes"],
        "label": f"$ {' '.join(cmd)} → exit {res['exit']}",
    }]
    st.append({
        "kind": "check",
        "intent": f"check {cid}: {item['text']}",
        "target": cid,
        "action": {"type": "cmd", "cmd": cmd, "exit": res["exit"], "ms": res["ms"]},
        "check": {"id": cid, "passed": passed, "exit": res["exit"], "cmd": cmd},
        "evidence": evidence,
    })
    mark = util.green("PASS") if passed else util.red("FAIL")
    print(f"  {mark} {util.bold(cid)} {item['text']}  {util.grey('exit %d' % res['exit'])}")
    for ln in [ln for ln in res["text"].splitlines() if ln.strip()][-4:]:
        print(util.grey("      │ " + util.one_line(ln, 100)))
    return 0 if passed else 1


def cmd_tick(args: argparse.Namespace) -> int:
    st = _need(args)
    if args.progress is not None and not (0 <= args.progress <= 100):
        raise NightshiftError("--progress must be between 0 and 100")
    ev = st.append({
        "kind": "tick",
        "intent": args.note or "checkpoint",
        "progress": args.progress,
        "evidence": [],
        "target": "",
    })
    a = analysis.analyse(st)
    _head("checkpoint", f"#{a['stats']['ticks']}")
    print(_kv("progress", f"{args.progress:g}%" if args.progress is not None else util.grey("not logged")))
    print(_kv("elapsed", util.human_dur(a["stats"]["wall_s"])
              + (f"  {util.grey('· ' + util.human_dur(a['stats']['remaining_s']) + ' left')}"
                 if a["stats"]["remaining_s"] and a["stats"]["remaining_s"] > 0 else "")))
    print(_kv("gate", (util.green("GREEN") if a["gate"].ok else util.red("RED"))
              + f"  {a['stats']['criteria_passed']}/{a['stats']['criteria']} criteria"))
    print(_kv("coverage", util.pct(a["stats"]["coverage"])))
    structural = [f for f in a["findings"] if f.severity in ("high", "medium")]
    advisory = [f for f in a["findings"] if f.severity == "low"]
    if structural:
        print(_kv("drift", util.yellow(f"{len(structural)} flag(s)")))
        for f in structural[-3:]:
            col = util.red if f.severity == "high" else util.yellow
            print(f"      {col('▸')} {f.title}")
    else:
        print(_kv("drift", util.green("clean")))
    if advisory:
        print(_kv("advisory", util.grey(f"{len(advisory)} low-confidence: {advisory[0].title}")))
    conv = a["convergence"]
    if conv.get("state") == "plateau":
        print(_kv("trend", util.yellow("plateau — " + conv.get("why", ""))))
    elif conv.get("state") in ("improving", "regressing"):
        print(_kv("trend", conv["state"] + " — " + conv.get("why", "")))
    print()
    return 0


def cmd_gate(args: argparse.Namespace) -> int:
    st = _need(args)
    a = analysis.analyse(st)
    g = a["gate"]
    if args.json:
        import json

        print(json.dumps(g.as_dict(), ensure_ascii=False, indent=2))
        return 0 if g.ok else 1
    _head("completion gate", a["verdict"]["label"])
    for p in g.passes:
        print(f"  {util.green('✓')} {util.bold(p['id'])}  {util.pad(p['text'], 60)} {util.green('proven')}")
    for f in g.failures:
        print(f"  {util.red('✗')} {util.bold(f['id'])}  {util.pad(f.get('text', ''), 60)} {util.red(f.get('why', ''))}")
    for w in g.warnings:
        print(f"  {util.yellow('⚠')} {util.grey(w)}")
    print()
    if g.ok:
        print(f"  {util.green('GATE GREEN')} — every criterion is proven with evidence.")
    elif a["stats"]["criteria"] == 0:
        # keep the quotes out of the f-string expression: a backslash inside
        # braces is a SyntaxError before Python 3.12
        hint = util.grey('add some: nsh done add "..." -- <command>')
        print(f"  {util.red('GATE RED')} — the flight plan has no done-criteria. {hint}")
    else:
        print(f"  {util.red('GATE RED')} — do not call this done."
              f" {util.plural(len(g.failures), 'criterion', 'criteria')} unproven.")
    print()
    return 0 if g.ok else 1


def cmd_status(args: argparse.Namespace) -> int:
    st = _need(args)
    a = analysis.analyse(st)
    if args.json:
        import json

        payload = {
            "verdict": a["verdict"],
            "stats": a["stats"],
            "gate": a["gate"].as_dict(),
            "findings": [f.as_dict() for f in a["findings"]],
            "convergence": a["convergence"],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        return 0
    v = a["verdict"]
    tone = {"good": util.green, "warn": util.yellow, "bad": util.red}[v["tone"]]
    print()
    print(f"{util.bold('✈ NIGHTSHIFT')} {util.grey('·')} {util.bold(util.one_line(a['contract']['goal'], 58))}")
    print(f"  {tone(v['label'])}  {util.grey(v['why'])}")
    st_ = a["stats"]
    window = ""
    if st_["remaining_s"] is not None:
        if st_["remaining_s"] >= 0:
            window = f"{util.human_dur(st_['wall_s'])} used · {util.human_dur(st_['remaining_s'])} left"
        else:
            window = f"{util.human_dur(-st_['remaining_s'])} past deadline"
    else:
        window = f"{util.human_dur(st_['wall_s'])} used"
    print(f"  {util.grey(window)}")
    print(_rule())
    print(f"  steps {util.bold(str(st_['steps']))}   evidence {util.bold(util.pct(st_['coverage']))}"
          f"   checks {st_['checks']}   checkpoints {st_['ticks']}   events {st_['events']}")
    structural = [f for f in a["findings"] if f.severity in ("high", "medium")]
    advisory = [f for f in a["findings"] if f.severity == "low"]
    if structural:
        worst = max(structural, key=lambda f: {"high": 0, "medium": 1, "low": 2}[f.severity])
        col = util.red if worst.severity == "high" else util.yellow
        print(f"  drift {col(str(len(structural)) + ' flag(s)')}  {util.grey(util.one_line(worst.title, 64))}")
    elif advisory:
        print(f"  drift {util.green('clean')}  {util.grey(str(len(advisory)) + ' advisory: ' + util.one_line(advisory[0].title, 50))}")
    else:
        print(f"  drift {util.green('clean')}")
    conv = a["convergence"]
    if conv.get("state") != "unknown":
        print(f"  trend {conv['state']}  {util.grey(util.one_line(conv.get('why', ''), 60))}")
    if not a["gate"].ok and a["gate"].failures:
        print(_rule())
        for f in a["gate"].failures[:5]:
            print(f"  {util.red('✗')} {util.bold(f['id'])} {util.pad(f.get('text', ''), 46)} {util.grey(f.get('why', ''))}")
    print(_rule(64, "─"))
    print(util.grey("  nsh tick --progress N   ·   nsh gate   ·   nsh report --open"))
    print()
    return 0


def cmd_brief(args: argparse.Namespace) -> int:
    st = _need(args)
    a = analysis.analyse(st)
    print()
    for line in a["brief"]:
        key, _, rest = line.partition(" ")
        print(f"  {util.cyan(util.pad(key, 9))}{rest}")
    print()
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    st = _need(args)
    a = analysis.analyse(st)
    paths = []
    if not args.md_only:
        p = report.write_report(st, a, fmt="html", out=args.out, project=args.project)
        paths.append(p)
    if args.md or args.md_only:
        p = report.write_report(st, a, fmt="md", out=(args.out_md or None), project=args.project)
        paths.append(p)
    for p in paths:
        print(f"  {util.green('✓')} wrote {p}" + f"  {util.grey(f'({p.stat().st_size} bytes)')}")

    if args.print_md or args.github_summary:
        md = report.render_md(report.model(a, project=args.project))
        if args.print_md:
            print()
            print(md)
        if args.github_summary:
            summary = os.environ.get("GITHUB_STEP_SUMMARY")
            if summary:
                with open(summary, "a", encoding="utf-8") as fh:
                    fh.write(md + "\n")
                print(f"  {util.green('✓')} appended to $GITHUB_STEP_SUMMARY")
            else:
                print(f"  {util.yellow('!')} --github-summary set but $GITHUB_STEP_SUMMARY is empty")

    if args.open and paths and os.name == "nt":
        try:
            os.startfile(paths[0])  # type: ignore[attr-defined]
        except OSError:
            pass
    return 0


def cmd_log(args: argparse.Namespace) -> int:
    st = _need(args)
    events = st.events()
    for ev in events[-args.n:]:
        print(_ev_line(ev))
        for item in ev.get("evidence") or []:
            print(util.grey(f"        └ {item.get('kind')} {item.get('ref')} {str(item.get('digest', ''))[:19]}"))
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    st = _need(args)
    r = st.verify_evidence()
    failed = bool(r["tampered"]) or (args.strict and (r["changed"] or r["missing"]))
    if args.json:
        import json

        payload = {k: v for k, v in r.items() if k != "ok"}
        payload["ok_count"] = len(r["ok"])
        payload["failed"] = failed
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1 if failed else 0
    _head("evidence verification", f"{r['total']} artefact(s) referenced by the log")
    for row in r["tampered"][:12]:
        print(f"  {util.red('✗')} {row['kind']} {util.one_line(row['ref'], 46)}")
        print(util.grey(f"      log says {row['digest'][:26]}  file is {row['actual'][:26]}"))
    for row in r["changed"][:6]:
        print(f"  {util.cyan('~')} {util.one_line(row['ref'], 46)}  {util.grey('changed since it was recorded')}")
    for row in r["missing"][:6]:
        print(f"  {util.yellow('!')} {util.one_line(row['ref'], 46)}  {util.grey('missing')}")
    print()
    print(f"  {util.green(str(len(r['ok'])))} intact · "
          f"{util.red(str(len(r['tampered'])))} tampered · "
          f"{util.cyan(str(len(r['changed'])))} changed · "
          f"{util.yellow(str(len(r['missing'])))} missing · "
          f"{util.grey(str(r['skipped']) + ' without a digest')}")
    if r["tampered"]:
        print(f"  {util.red('VERIFY FAILED')} — evidence inside the store no longer matches its digest.")
    elif failed:
        print(f"  {util.red('VERIFY FAILED')} — strict mode.")
    elif r["changed"]:
        print(f"  {util.green('VERIFY OK')} — every captured artefact is intact; "
              f"{len(r['changed'])} project file(s) moved on since they were snapshotted.")
    else:
        print(f"  {util.green('VERIFY OK')} — every digest still matches the bytes on disk.")
    print()
    return 1 if failed else 0


def cmd_doctor(args: argparse.Namespace) -> int:
    _head("doctor", f"nightshift {__version__} · python {sys.version.split()[0]}")
    checks = [
        ("python >= 3.10", sys.version_info >= (3, 10)),
        ("utf-8 stdout", True),
        ("write access", _can_write(Path("."))),
    ]
    for label, ok in checks:
        print(f"  {util.green('✓') if ok else util.red('✗')} {label}")
    colour = "on" if util.color_enabled() else "off (NO_COLOR, or stdout is not a tty)"
    print(f"  {util.grey('·')} colour: {colour}")
    root = find_root()
    print(f"  {util.grey('·')} flight plan: {root if root else 'none here (nsh init)'}")
    print()
    return 0


def _can_write(p: Path) -> bool:
    probe = p / ".nsh-probe"
    try:
        probe.write_text("x", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def cmd_bench(args: argparse.Namespace) -> int:
    from . import bench

    return bench.main(verbose=not args.quiet, as_json=args.json)


def cmd_demo(args: argparse.Namespace) -> int:
    from . import demo

    red = bool(getattr(args, "red", False))
    dest = args.dir or (".nightshift-demo-red" if red else ".nightshift-demo")
    return demo.main(dest, open_report=args.open, outcome="red" if red else "green")


# --------------------------------------------------------------------------- #
# argument parsing
# --------------------------------------------------------------------------- #

def _clean_cmd(cmd: Sequence[str] | None) -> list[str]:
    out = [c for c in (cmd or [])]
    if out and out[0] == "--":
        out = out[1:]
    return out


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="nsh",
        description="NIGHTSHIFT — run an AI agent through a long unattended shift "
                    "and wake up to a flight report.",
        epilog="docs: https://github.com/  ·  every command is agent-safe (no prompts)",
    )
    p.add_argument("--version", action="version", version=f"nightshift {__version__}")
    p.add_argument("--dir", help="path to the .nightshift directory (default: auto-discover)")
    p.add_argument("--no-color", action="store_true", help="disable ANSI colour")
    sub = p.add_subparsers(dest="command", required=True)

    q = sub.add_parser("init", help="create a flight plan")
    q.add_argument("--goal", required=True)
    q.add_argument("--deadline", help="'10:30', '2026-10-25 10:30' or ISO")
    q.add_argument("--hours", type=float, help="alternative to --deadline: shift length in hours")
    q.add_argument("--non-goal", action="append", help="explicitly out of scope (repeatable)")
    q.add_argument("--risk", action="append", help="known risk (repeatable)")
    q.add_argument("--force", action="store_true")
    q.set_defaults(func=cmd_init)

    q = sub.add_parser("done", help="manage done-criteria")
    qsub = q.add_subparsers(dest="action", required=True)
    qa = qsub.add_parser("add", help="add a done-criterion with an optional check command")
    qa.add_argument("text")
    qa.add_argument("cmd", nargs=argparse.REMAINDER, help="-- <check command>")
    ql = qsub.add_parser("ls", help="list done-criteria and their state")
    qr = qsub.add_parser("rm", help="remove a done-criterion")
    qr.add_argument("text")
    q.set_defaults(func=cmd_done)

    q = sub.add_parser("step", help="record a step (what you did + what proves it)")
    q.add_argument("text")
    q.add_argument("-e", "--evidence", action="append", help="path to a file that proves it (repeatable)")
    q.add_argument("--target", help="file/area being changed (used for churn detection)")
    q.add_argument("--tag", action="append")
    q.add_argument("--note", help="free-text note stored as evidence")
    q.set_defaults(func=cmd_step)

    q = sub.add_parser("run", help="run a command, capture its output as evidence, log it")
    q.add_argument("cmd", nargs=argparse.REMAINDER)
    q.add_argument("--intent", help="what this step was for")
    q.add_argument("--target")
    q.add_argument("--tag", action="append")
    q.add_argument("--timeout", type=int, default=1800)
    q.add_argument("--allow-fail", action="store_true", help="exit 0 even if the command failed")
    q.add_argument("--show", action="store_true", help="echo full output")
    q.set_defaults(func=cmd_run)

    q = sub.add_parser("check", help="run a done-criterion's check command and record pass/fail")
    q.add_argument("id", nargs="?")
    q.add_argument("cmd", nargs=argparse.REMAINDER)
    q.add_argument("--all", action="store_true", help="re-run every criterion (use before you sleep)")
    q.add_argument("--timeout", type=int, default=1800)
    q.set_defaults(func=cmd_check)

    q = sub.add_parser("tick", help="write a checkpoint (progress + drift + convergence)")
    q.add_argument("--progress", type=float, help="0-100, your honest estimate of completion")
    q.add_argument("--note", default="")
    q.set_defaults(func=cmd_tick)

    q = sub.add_parser("gate", help="exit 0 only if every criterion is proven with evidence")
    q.add_argument("--json", action="store_true")
    q.set_defaults(func=cmd_gate)

    q = sub.add_parser("status", help="one-screen state of the shift")
    q.add_argument("--json", action="store_true")
    q.set_defaults(func=cmd_status)

    q = sub.add_parser("brief", help="the ten lines a human reads in the morning")
    q.set_defaults(func=cmd_brief)

    q = sub.add_parser("report", help="render the flight report")
    q.add_argument("--md", action="store_true", help="also write markdown")
    q.add_argument("--md-only", action="store_true")
    q.add_argument("--out")
    q.add_argument("--out-md")
    q.add_argument("--project", default="")
    q.add_argument("--print", dest="print_md", action="store_true", help="print the markdown to stdout")
    q.add_argument("--github-summary", action="store_true",
                   help="append the markdown to $GITHUB_STEP_SUMMARY (for CI)")
    q.add_argument("--open", action="store_true")
    q.set_defaults(func=cmd_report)

    q = sub.add_parser("log", help="print the last N events")
    q.add_argument("-n", type=int, default=20)
    q.set_defaults(func=cmd_log)

    q = sub.add_parser("bench", help="score the drift detector on the labelled corpus")
    q.add_argument("--json", action="store_true")
    q.add_argument("--quiet", action="store_true")
    q.set_defaults(func=cmd_bench)

    q = sub.add_parser("demo", help="build a deterministic demo run and open its report")
    q.add_argument("--red", action="store_true", help="demo a shift that failed its gate")
    q.add_argument("--open", action="store_true")
    q.set_defaults(func=cmd_demo)

    q = sub.add_parser("verify", help="recompute every evidence digest and compare it to the file")
    q.add_argument("--json", action="store_true")
    q.add_argument("--strict", action="store_true", help="also fail when an artefact is missing")
    q.set_defaults(func=cmd_verify)

    q = sub.add_parser("doctor", help="check the environment")
    q.set_defaults(func=cmd_doctor)
    return p


def main(argv: Sequence[str] | None = None) -> int:
    util.enable_windows_vt()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "no_color", False) or os.environ.get("NO_COLOR"):
        util.set_color(False)
    elif not sys.stdout.isatty() and os.environ.get("NSH_FORCE_COLOR") != "1":
        util.set_color(False)

    try:
        return int(args.func(args) or 0)
    except NightshiftError as exc:
        print(f"\n  {util.red('error')} {exc}\n", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\n  interrupted\n", file=sys.stderr)
        return 130


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
