"""Test suite for NIGHTSHIFT.  Run with:

    python -m unittest discover -s tests -t . -v
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from nightshift import analysis, bench, demo, report, store as store_mod, util  # noqa: E402
from nightshift.store import Store  # noqa: E402


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def ev(i: int, kind: str, intent: str, *, proof: bool = True, target: str = "",
       progress: float | None = None, check: dict | None = None, ts: str | None = None) -> dict:
    row = {
        "v": 1,
        "id": "e%05d" % i,
        "ts": ts or ("2026-10-24T23:%02d:00+08:00" % (i % 60)),
        "kind": kind,
        "intent": intent,
        "target": target,
        "evidence": (
            [{"kind": "cmd", "ref": "evidence/x.txt", "digest": util.digest(intent), "bytes": 10, "label": ""}]
            if proof else []
        ),
    }
    if progress is not None:
        row["progress"] = progress
    if check is not None:
        row["check"] = check
    return row


CONTRACT = {
    "v": 1,
    "goal": "ship the CSV report generator as a CLI with tests",
    "done": [{"id": "d1", "text": "tests pass", "cmd": ["true"]}],
    "non_goals": [],
    "risks": [],
    "budget": {"started_at": "2026-10-24T22:00:00+08:00", "deadline": "2026-10-25T06:00:00+08:00"},
}


# --------------------------------------------------------------------------- #
# util
# --------------------------------------------------------------------------- #

class TestUtil(unittest.TestCase):
    def test_tokenize_latin_stems_plurals(self):
        toks = util.tokenize("the tests are passing files")
        self.assertIn("test", toks)
        self.assertIn("file", toks)
        self.assertNotIn("the", toks)

    def test_tokenize_cjk_bigrams(self):
        toks = util.tokenize("重构结账流程")
        self.assertIn("重构", toks)
        self.assertIn("结账", toks)

    def test_overlap_is_asymmetric(self):
        a = {"csv", "parser"}
        b = {"csv", "parser", "report", "template", "cli"}
        self.assertEqual(util.overlap(a, b), 1.0)
        self.assertEqual(util.overlap(b, a), 0.4)

    def test_parse_deadline_iso_and_clock(self):
        dt = util.parse_deadline("2026-10-25 10:30")
        self.assertEqual((dt.hour, dt.minute), (10, 30))
        dt2 = util.parse_deadline("10:30", base=util.parse_deadline("2026-10-25 08:00"))
        self.assertEqual(dt2.day, 25)
        self.assertEqual(dt2.hour, 10)

    def test_parse_deadline_rejects_out_of_range(self):
        for bad in ("24:00", "10:75", "2026-13-45 10:00", "2026-02-30 10:00", "not-a-date"):
            with self.assertRaises(ValueError, msg=bad) as ctx:
                util.parse_deadline(bad)
            self.assertIn("cannot parse deadline", str(ctx.exception))

    def test_parse_iso_normalises_what_other_tools_write(self):
        self.assertEqual(util.parse_iso("2026-10-25T03:06:43Z").utcoffset().total_seconds(), 0)
        self.assertEqual(util.parse_iso("2026-10-25T03:06:43+0800").utcoffset().total_seconds(), 8 * 3600)
        self.assertEqual(util.parse_iso("2026-10-25T03:06:43.5+08:00").microsecond, 500000)
        with self.assertRaises(ValueError):
            util.parse_iso("")

    def test_human_dur(self):
        self.assertEqual(util.human_dur(0), "0s")
        self.assertEqual(util.human_dur(90), "1m30s")
        self.assertEqual(util.human_dur(3600 + 42 * 60), "1h42m")


# --------------------------------------------------------------------------- #
# gate
# --------------------------------------------------------------------------- #

class TestGate(unittest.TestCase):
    def test_green_when_passed_with_proof(self):
        events = [ev(1, "step", "write tests"),
                  ev(2, "check", "check d1", check={"id": "d1", "passed": True, "exit": 0})]
        g = analysis.gate(CONTRACT, events)
        self.assertTrue(g.ok)

    def test_red_when_never_checked(self):
        g = analysis.gate(CONTRACT, [ev(1, "step", "write tests")])
        self.assertFalse(g.ok)
        self.assertIn("never checked", g.failures[0]["why"])

    def test_red_when_check_failed(self):
        events = [ev(1, "check", "check d1", check={"id": "d1", "passed": False, "exit": 1})]
        g = analysis.gate(CONTRACT, events)
        self.assertFalse(g.ok)
        self.assertIn("failed", g.failures[0]["why"])

    def test_red_when_passed_without_proof(self):
        events = [ev(1, "check", "check d1", proof=False,
                     check={"id": "d1", "passed": True, "exit": 0})]
        g = analysis.gate(CONTRACT, events)
        self.assertFalse(g.ok)
        self.assertIn("no machine-checkable evidence", g.failures[0]["why"])

    def test_notes_are_not_proof(self):
        events = [ev(1, "check", "check d1", proof=False,
                     check={"id": "d1", "passed": True, "exit": 0})]
        events[0]["evidence"] = [{"kind": "note", "ref": "n", "digest": "sha256:x", "bytes": 1, "label": ""}]
        self.assertFalse(analysis.gate(CONTRACT, events).ok)

    def test_no_criteria_fails(self):
        c = dict(CONTRACT, done=[])
        g = analysis.gate(c, [ev(1, "step", "x")])
        self.assertFalse(g.ok)


# --------------------------------------------------------------------------- #
# drift
# --------------------------------------------------------------------------- #

class TestDrift(unittest.TestCase):
    def test_silent_run_detected(self):
        events = [ev(i, "step", "write the CSV parser %d" % i, proof=False) for i in range(1, 8)]
        codes = {f.code for f in analysis.drift(CONTRACT, events)}
        self.assertIn("silent_run", codes)

    def test_short_silence_is_not_flagged(self):
        events = [ev(i, "step", "write the csv parser %d" % i, proof=False) for i in range(1, 4)]
        codes = {f.code for f in analysis.drift(CONTRACT, events)}
        self.assertNotIn("silent_run", codes)

    def test_churn_detected_and_reset_by_check(self):
        churn = [ev(i, "step", "polish the csv parser", target="src/a.rs") for i in range(1, 6)]
        codes = {f.code for f in analysis.drift(CONTRACT, churn)}
        self.assertIn("churn", codes)

        reset = ([ev(i, "step", "polish the csv parser", target="src/a.rs") for i in range(1, 4)]
                 + [ev(9, "check", "check d1", check={"id": "d1", "passed": True, "exit": 0})]
                 + [ev(i, "step", "polish the csv parser", target="src/a.rs") for i in range(10, 13)])
        codes2 = {f.code for f in analysis.drift(CONTRACT, reset)}
        self.assertNotIn("churn", codes2)

    def test_off_topic_detected(self):
        events = ([ev(i, "step", "write the csv parser") for i in range(1, 5)]
                  + [ev(i, "step", w) for i, w in enumerate(
                      ["buy coffee beans", "call the landlord", "read about black holes",
                       "plan a holiday", "tune the guitar", "water the plants"], start=10)])
        codes = {f.code for f in analysis.drift(CONTRACT, events)}
        self.assertIn("off_topic", codes)

    def test_checkpoints_do_not_dilute(self):
        events = ([ev(i, "step", "write the csv report parser") for i in range(1, 8)]
                  + [ev(i, "tick", "checkpoint", progress=10) for i in range(10, 16)])
        codes = {f.code for f in analysis.drift(CONTRACT, events)}
        self.assertNotIn("off_topic", codes)


# --------------------------------------------------------------------------- #
# convergence
# --------------------------------------------------------------------------- #

class TestConvergence(unittest.TestCase):
    def test_plateau(self):
        events = [ev(i, "tick", "tick", progress=90, ts="2026-10-25T0%d:00:00+08:00" % i)
                  for i in range(1, 5)]
        conv = analysis.convergence(events)
        self.assertEqual(conv["state"], "plateau")

    def test_improving(self):
        events = [ev(i, "tick", "tick", progress=p, ts="2026-10-25T0%d:00:00+08:00" % i)
                  for i, p in enumerate([10, 40, 70, 95], start=1)]
        self.assertEqual(analysis.convergence(events)["state"], "improving")

    def test_unknown_without_three_points(self):
        self.assertEqual(analysis.convergence([ev(1, "tick", "t", progress=5)])["state"], "unknown")


# --------------------------------------------------------------------------- #
# store + report
# --------------------------------------------------------------------------- #

class TestStore(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            st = Store(Path(tmp) / ".nightshift")
            st.init(goal="do a thing", hours=8)
            st.add_done("it works", cmd=["true"])
            e = st.append({"kind": "step", "intent": "did it", "evidence": []})
            self.assertEqual(e["id"], "e000002")
            self.assertEqual(len(st.events()), 2)
            self.assertTrue(st.exists())
            self.assertEqual(st.load_contract()["goal"], "do a thing")

    def test_evidence_is_hashed_and_stored(self):
        with tempfile.TemporaryDirectory() as tmp:
            st = Store(Path(tmp) / ".nightshift")
            st.init(goal="x", hours=1)
            item = st.save_evidence("hello world\n", kind="cmd", label="t")
            self.assertTrue(item["digest"].startswith("sha256:"))
            path = st.root / item["ref"]
            self.assertTrue(path.exists())
            self.assertEqual(path.read_text(encoding="utf-8"), "hello world\n")

    def test_evidence_digest_matches_the_stored_bytes(self):
        """The receipt has to be verifiable: hash what you saved, save what you hashed."""
        import hashlib

        with tempfile.TemporaryDirectory() as tmp:
            st = Store(Path(tmp) / ".nightshift")
            st.init(goal="x", hours=1)
            item = st.save_evidence("line one\nline two\n", kind="cmd")
            data = (st.root / item["ref"]).read_bytes()
            self.assertEqual("sha256:" + hashlib.sha256(data).hexdigest(), item["digest"])
            self.assertEqual(len(data), item["bytes"])

    def test_huge_output_is_capped_not_buffered(self):
        with tempfile.TemporaryDirectory() as tmp:
            st = Store(Path(tmp) / ".nightshift")
            st.init(goal="x", hours=1)
            item = st.save_evidence("A" * (store_mod.MAX_CAPTURE * 3), kind="cmd")
            self.assertTrue(item["truncated"])
            self.assertEqual(item["bytes_total"], store_mod.MAX_CAPTURE * 3)
            self.assertLess(item["bytes"], store_mod.MAX_CAPTURE + 200)

    def test_init_twice_needs_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            st = Store(Path(tmp) / ".nightshift")
            st.init(goal="x", hours=1)
            with self.assertRaises(store_mod.NightshiftError):
                st.init(goal="y", hours=1)
            st.init(goal="y", hours=1, force=True)
            self.assertEqual(st.load_contract()["goal"], "y")


class TestReport(unittest.TestCase):
    def test_html_contains_the_verdict_and_the_unproven_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            st = Store(Path(tmp) / ".nightshift")
            st.init(goal="ship it", hours=8)
            st.add_done("tests", cmd=["true"])
            st.append({"kind": "step", "intent": "wrote tests", "evidence": []})
            a = analysis.analyse(st)
            out = report.write_report(st, a, fmt="html")
            text = out.read_text(encoding="utf-8")
            self.assertIn("Flight report", text)
            self.assertIn("Not proven", text)
            self.assertIn("GATE", text.upper())
            self.assertGreater(len(text), 5000)

    def test_html_escapes_event_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            st = Store(Path(tmp) / ".nightshift")
            st.init(goal="ship it <script>alert(1)</script>", hours=8)
            st.add_done("tests", cmd=["true"])
            st.append({"kind": "step", "intent": "<img src=x onerror=alert(1)>", "target": "\"><script>x</script>",
                       "evidence": []})
            a = analysis.analyse(st)
            text = report.write_report(st, a, fmt="html").read_text(encoding="utf-8")
            self.assertNotIn("<script>alert(1)</script>", text)
            self.assertNotIn("<img src=x onerror", text)
            self.assertIn("&lt;script&gt;", text)

    def test_markdown_renders(self):
        with tempfile.TemporaryDirectory() as tmp:
            st = Store(Path(tmp) / ".nightshift")
            st.init(goal="ship it", hours=8)
            a = analysis.analyse(st)
            out = report.write_report(st, a, fmt="md")
            self.assertIn("# NIGHTSHIFT", out.read_text(encoding="utf-8"))

    def test_report_survives_null_timestamps(self):
        with tempfile.TemporaryDirectory() as tmp:
            st = Store(Path(tmp) / ".nightshift")
            st.init(goal="ship it", hours=8)
            st.append({"kind": "step", "intent": "hand edited", "ts": None, "evidence": []})
            a = analysis.analyse(st)
            text = report.write_report(st, a, fmt="html").read_text(encoding="utf-8")
            self.assertIn("Flight report", text)

    def test_malformed_log_lines_are_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            st = Store(Path(tmp) / ".nightshift")
            st.init(goal="ship it", hours=8)
            st.append({"kind": "step", "intent": "one", "evidence": []})
            with open(st.events_path, "a", encoding="utf-8") as fh:
                fh.write("{this is not json}\n\n")
            self.assertEqual(len(st.events()), 2)
            a = analysis.analyse(st)  # must not raise
            self.assertEqual(a["stats"]["actions"] if "actions" in a["stats"] else a["stats"]["events"], 2)


class TestVerify(unittest.TestCase):
    def test_intact_capture_verifies(self):
        with tempfile.TemporaryDirectory() as tmp:
            st = Store(Path(tmp) / ".nightshift")
            st.init(goal="x", hours=1)
            item = st.save_evidence("true output\n", kind="cmd")
            st.append({"kind": "step", "intent": "ran it", "evidence": [item]})
            r = st.verify_evidence()
            self.assertEqual(len(r["ok"]), 1)
            self.assertFalse(r["tampered"])

    def test_tampered_capture_is_caught(self):
        with tempfile.TemporaryDirectory() as tmp:
            st = Store(Path(tmp) / ".nightshift")
            st.init(goal="x", hours=1)
            item = st.save_evidence("true output\n", kind="cmd")
            st.append({"kind": "step", "intent": "ran it", "evidence": [item]})
            (st.root / item["ref"]).write_bytes(b"different bytes")
            r = st.verify_evidence()
            self.assertEqual(len(r["tampered"]), 1)
            self.assertEqual(len(r["ok"]), 0)

    def test_edited_project_file_is_changed_not_tampered(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            st = Store(root / ".nightshift")
            st.init(goal="x", hours=1)
            doc = root / "README.md"
            doc.write_text("first", encoding="utf-8")
            item = st.file_evidence(doc)
            st.append({"kind": "step", "intent": "wrote the readme", "evidence": [item]})
            doc.write_text("second", encoding="utf-8")
            r = st.verify_evidence()
            self.assertEqual(len(r["changed"]), 1)
            self.assertEqual(len(r["tampered"]), 0)


# --------------------------------------------------------------------------- #
# demo + bench
# --------------------------------------------------------------------------- #

class TestDemoAndBench(unittest.TestCase):
    def test_demo_builds_a_complete_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            st = demo.build(Path(tmp) / ".nightshift-demo")
            a = analysis.analyse(st)
            self.assertTrue(a["gate"].ok)
            self.assertGreaterEqual(a["stats"]["steps"], 25)
            self.assertGreaterEqual(a["stats"]["ticks"], 5)
            self.assertTrue(a["findings"])  # the scripted churn + silent run

    def test_bench_has_no_regression_on_labelled_cases(self):
        result = bench.evaluate(bench.build_cases())
        self.assertGreaterEqual(result["drift"]["f1"], 0.85)
        self.assertGreaterEqual(result["gate_accuracy"], 0.95)


# --------------------------------------------------------------------------- #
# CLI (end to end, in a subprocess)
# --------------------------------------------------------------------------- #

class TestCli(unittest.TestCase):
    def _run(self, cwd: str, *args: str) -> subprocess.CompletedProcess:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        env["PYTHONIOENCODING"] = "utf-8"
        env["NO_COLOR"] = "1"
        return subprocess.run(
            [sys.executable, "-m", "nightshift", *args],
            cwd=cwd, env=env, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=120,
        )

    def test_full_shift(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self._run(tmp, "init", "--goal", "ship a tiny CLI", "--hours", "2")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue((Path(tmp) / ".nightshift" / "contract.json").exists())

            r = self._run(tmp, "done", "add", "truth is true", "--",
                          sys.executable, "-c", "import sys; sys.exit(0)")
            self.assertEqual(r.returncode, 0, r.stderr)

            r = self._run(tmp, "gate")
            self.assertEqual(r.returncode, 1, "gate must be red before the check runs")

            r = self._run(tmp, "check", "d1")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

            r = self._run(tmp, "gate")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

            r = self._run(tmp, "tick", "--progress", "50", "--note", "halfway")
            self.assertEqual(r.returncode, 0, r.stderr)

            r = self._run(tmp, "report")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue((Path(tmp) / ".nightshift" / "reports" / "flight-report.html").exists())

            r = self._run(tmp, "status", "--json")
            self.assertEqual(r.returncode, 0, r.stderr)
            payload = json.loads(r.stdout)
            self.assertTrue(payload["gate"]["ok"])

    def test_failing_check_returns_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._run(tmp, "init", "--goal", "x", "--hours", "1")
            self._run(tmp, "done", "add", "must fail", "--",
                      sys.executable, "-c", "import sys; sys.exit(3)")
            r = self._run(tmp, "check", "d1")
            self.assertEqual(r.returncode, 1)

    def test_check_all_runs_every_criterion(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._run(tmp, "init", "--goal", "x", "--hours", "1")
            for name in ("one", "two", "three"):
                self._run(tmp, "done", "add", name, "--", sys.executable, "-c", "print('ok')")
            r = self._run(tmp, "check", "--all")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(r.stdout.count("PASS"), 3)
            gate = self._run(tmp, "gate")
            self.assertEqual(gate.returncode, 0, gate.stdout + gate.stderr)

    def test_run_captures_output_as_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._run(tmp, "init", "--goal", "x", "--hours", "1")
            r = self._run(tmp, "run", "--", sys.executable, "-c", "print('hello-evidence')")
            self.assertEqual(r.returncode, 0, r.stderr)
            events = (Path(tmp) / ".nightshift" / "events.jsonl").read_text(encoding="utf-8")
            self.assertIn("hello-evidence", events)

    def test_gate_without_contract_is_a_user_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self._run(tmp, "gate")
            self.assertEqual(r.returncode, 2)
            self.assertIn("no flight plan", r.stderr)

    def test_verify_returns_one_when_captured_evidence_was_edited(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._run(tmp, "init", "--goal", "x", "--hours", "1")
            self._run(tmp, "run", "--", sys.executable, "-c", "print('evidence')")
            ok = self._run(tmp, "verify")
            self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
            ev_dir = Path(tmp) / ".nightshift" / "evidence"
            for f in ev_dir.glob("*.txt"):
                f.write_bytes(b"tampered")
            bad = self._run(tmp, "verify")
            self.assertEqual(bad.returncode, 1)
            self.assertIn("VERIFY FAILED", bad.stdout)


if __name__ == "__main__":
    unittest.main()
