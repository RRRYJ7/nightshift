"""The black box: an append-only event log, a flight plan, and captured evidence.

Everything NIGHTSHIFT knows about a run lives in one directory (``.nightshift``
by default):

    .nightshift/
        contract.json     the flight plan (goal, done-criteria, budget)
        events.jsonl      append-only black box, one JSON object per line
        evidence/         captured command output, hashed
        reports/          generated flight reports

The log is append-only on purpose. A run that can rewrite its own history
cannot be audited.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Sequence

from . import __version__, util

MAX_CAPTURE = 64 * 1024
DEFAULT_DIR = ".nightshift"


class NightshiftError(RuntimeError):
    """A user-facing failure: printed without a traceback."""


# --------------------------------------------------------------------------- #
# command capture
# --------------------------------------------------------------------------- #

def _decode(raw: bytes) -> str:
    if not raw:
        return ""
    for enc in ("utf-8", "gb18030", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def run_capture(
    cmd: Sequence[str],
    cwd: str | os.PathLike | None = None,
    timeout: int = 1800,
    max_bytes: int = MAX_CAPTURE,
) -> dict[str, Any]:
    """Run *cmd*, return exit code, duration and (capped) output.

    Output goes to temporary files rather than pipes, so a runaway command that
    prints gigabytes cannot exhaust this process's memory. Only the first
    *max_bytes* of each stream is read back.
    """
    cmd = [str(x) for x in cmd]
    t0 = time.monotonic()
    timed_out = False
    out_tmp = tempfile.TemporaryFile()
    err_tmp = tempfile.TemporaryFile()
    try:
        try:
            cp = subprocess.run(cmd, cwd=str(cwd) if cwd else None,
                                stdout=out_tmp, stderr=err_tmp, timeout=timeout)
            code = cp.returncode
        except FileNotFoundError:
            return {
                "cmd": cmd,
                "exit": 127,
                "ms": int((time.monotonic() - t0) * 1000),
                "text": f"command not found: {cmd[0] if cmd else ''}",
                "timed_out": False,
                "capped": False,
            }
        except subprocess.TimeoutExpired:
            code, timed_out = 124, True

        out_tmp.seek(0)
        err_tmp.seek(0)
        out = out_tmp.read(max_bytes + 1)
        err = err_tmp.read(max_bytes + 1)
    finally:
        out_tmp.close()
        err_tmp.close()

    capped = len(out) > max_bytes or len(err) > max_bytes
    text = _decode(out[:max_bytes])
    err_text = _decode(err[:max_bytes])
    if err_text.strip():
        text += ("\n" if text else "") + "--- stderr ---\n" + err_text
    if capped:
        text += "\n... [output capped at %d bytes per stream]" % max_bytes
    ms = int((time.monotonic() - t0) * 1000)
    return {"cmd": cmd, "exit": code, "ms": ms, "text": text,
            "timed_out": timed_out, "capped": capped}


# --------------------------------------------------------------------------- #
# the store
# --------------------------------------------------------------------------- #

class Store:
    """Reads and writes one night shift's worth of state."""

    def __init__(self, root: str | os.PathLike = DEFAULT_DIR):
        self.root = Path(root)

    # -- locations -----------------------------------------------------------

    @property
    def contract_path(self) -> Path:
        return self.root / "contract.json"

    @property
    def events_path(self) -> Path:
        return self.root / "events.jsonl"

    @property
    def evidence_dir(self) -> Path:
        return self.root / "evidence"

    @property
    def reports_dir(self) -> Path:
        return self.root / "reports"

    def exists(self) -> bool:
        return self.contract_path.exists()

    def require(self) -> "Store":
        if not self.exists():
            raise NightshiftError(
                f"no flight plan at {self.root}.  start one with:  nsh init --goal \"...\""
            )
        return self

    # -- flight plan ---------------------------------------------------------

    def load_contract(self) -> dict[str, Any]:
        data = util.read_json(self.contract_path)
        if not isinstance(data, dict):
            raise NightshiftError(f"{self.contract_path} is missing or corrupt")
        return data

    def save_contract(self, contract: dict[str, Any]) -> None:
        util.write_json(self.contract_path, contract)

    def init(
        self,
        goal: str,
        deadline: Any = None,
        hours: float | None = None,
        non_goals: Sequence[str] = (),
        risks: Sequence[str] = (),
        force: bool = False,
    ) -> dict[str, Any]:
        if self.exists() and not force:
            raise NightshiftError(
                f"{self.root} already has a flight plan (use --force to start over)"
            )
        self.root.mkdir(parents=True, exist_ok=True)
        self.evidence_dir.mkdir(exist_ok=True)
        self.reports_dir.mkdir(exist_ok=True)

        started = util.now()
        if deadline is None and hours:
            deadline = started + __import__("datetime").timedelta(hours=float(hours))
        contract = {
            "v": 1,
            "tool": f"nightshift {__version__}",
            "goal": " ".join(goal.split()),
            "created_at": util.iso(started),
            "budget": {
                "started_at": util.iso(started),
                "deadline": util.iso(deadline) if deadline else None,
                "hours": float(hours) if hours else None,
            },
            "done": [],
            "non_goals": [_norm(x) for x in non_goals if _norm(x)],
            "risks": [_norm(x) for x in risks if _norm(x)],
            "stop_conditions": [
                "every done-criterion passes with evidence (gate is green)",
                "budget is spent and the gate is red -> stop and report, do not fake it",
                "the same blocker survives 3 checkpoints -> stop and report",
                "three checkpoints in a row add no measurable improvement -> stop polishing",
            ],
        }
        self.save_contract(contract)
        self.append(
            {
                "kind": "init",
                "intent": contract["goal"],
                "note": f"flight plan created, deadline={contract['budget']['deadline']}",
                "evidence": [],
            }
        )
        return contract

    def add_done(self, text: str, cmd: Sequence[str] | None = None, evidence_hint: str = "") -> dict:
        contract = self.load_contract()
        cid = _next_done_id(contract)
        item = {
            "id": cid,
            "text": " ".join(str(text).split()),
            "cmd": [str(x) for x in cmd] if cmd else None,
            "evidence_hint": evidence_hint,
            "created_at": util.iso(),
        }
        contract["done"].append(item)
        self.save_contract(contract)
        return item

    def remove_done(self, cid: str) -> bool:
        contract = self.load_contract()
        before = len(contract["done"])
        contract["done"] = [d for d in contract["done"] if d["id"] != cid]
        self.save_contract(contract)
        return len(contract["done"]) != before

    # -- black box -----------------------------------------------------------

    def events(self) -> list[dict[str, Any]]:
        return util.read_jsonl(self.events_path)

    def next_id(self) -> str:
        return f"e{len(self.events()) + 1:06d}"

    def append(self, event: dict[str, Any], ts: Any = None) -> dict[str, Any]:
        self.root.mkdir(parents=True, exist_ok=True)
        record: dict[str, Any] = {
            "v": 1,
            "id": self.next_id(),
            "ts": util.iso(ts) if ts is not None else util.iso(),
        }
        record.update(event)
        record.setdefault("kind", "note")
        record.setdefault("evidence", [])
        util.append_jsonl(self.events_path, record)
        return record

    # -- evidence ------------------------------------------------------------

    def save_evidence(self, text: str, kind: str = "cmd", label: str = "") -> dict[str, Any]:
        """Store captured bytes and hash *exactly what was stored*.

        The digest must match the file on disk, otherwise "replay the receipt"
        is a promise the tool cannot keep. When output is longer than the cap we
        say so in the file and record the original size separately.
        """
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        raw_bytes = len(text.encode("utf-8", "replace"))
        truncated = raw_bytes > MAX_CAPTURE
        if truncated:
            text = text[:MAX_CAPTURE] + f"\n... [truncated, {raw_bytes} bytes total]"
        dig = util.digest(text)
        name = f"{int(time.time() * 1000)}-{dig[7:15]}.txt"
        path = self.evidence_dir / name
        # write bytes, not text: Windows newline translation would change the
        # bytes and break "the digest matches the file".
        data = text.encode("utf-8", "replace")
        path.write_bytes(data)
        return {
            "kind": kind,
            "ref": path.relative_to(self.root).as_posix(),
            "digest": dig,
            "bytes": len(data),
            "bytes_total": raw_bytes,
            "truncated": truncated,
            "label": label,
        }

    def file_evidence(self, path: str | os.PathLike, label: str = "") -> dict[str, Any]:
        p = Path(path)
        if not p.exists():
            raise NightshiftError(f"evidence file does not exist: {p}")
        return {
            "kind": "file",
            # posix separators so a log written on Windows still resolves on CI
            "ref": p.as_posix(),
            "digest": "sha256:" + util.sha256_file(p),
            "bytes": p.stat().st_size,
            "label": label or p.name,
        }

    def url_evidence(self, url: str, label: str = "") -> dict[str, Any]:
        return {"kind": "url", "ref": url, "digest": "", "bytes": 0, "label": label or url}

    def note_evidence(self, text: str) -> dict[str, Any]:
        return self.save_evidence(text, kind="note", label="typed note")

    # -- verification --------------------------------------------------------

    def _resolve(self, kind: str, ref: str) -> Path | None:
        """Where an evidence item's bytes are supposed to be."""
        if not ref:
            return None
        # logs written on Windows carry backslashes; normalise before resolving
        ref = ref.replace("\\", "/")
        candidate = Path(ref)
        if candidate.is_absolute():
            return candidate
        if kind == "file":
            # file evidence points at the project, not at the store
            project_root = self.root.resolve().parent
            via_project = project_root / candidate
            return via_project if via_project.exists() else (Path.cwd() / candidate)
        return self.root / candidate

    def verify_evidence(self) -> dict[str, Any]:
        """Recompute every digest in the log and compare it to the artefact.

        Two different things look identical if you only compare hashes:

        * ``cmd`` / ``test`` evidence lives inside the store and is never
          supposed to change. A mismatch there means the receipt was edited —
          that is tampering, and it fails.
        * ``file`` evidence is a snapshot of a project file at a moment in time.
          A mismatch means the project moved on, which is what projects do. It
          is reported as *changed*, not as fraud.

        Without that distinction the command cries wolf on every run that edits
        a file after recording it, and a check that always fails is a check
        nobody reads.
        """
        ok: list[dict] = []
        tampered: list[dict] = []
        changed: list[dict] = []
        missing: list[dict] = []
        skipped = 0
        for ev in self.events():
            for item in ev.get("evidence") or []:
                kind = item.get("kind") or ""
                dig = item.get("digest") or ""
                ref = item.get("ref") or ""
                if kind == "url" or not dig:
                    skipped += 1
                    continue
                path = self._resolve(kind, ref)
                row = {"id": ev.get("id", ""), "kind": kind, "ref": ref, "digest": dig}
                if path is None or not path.exists():
                    missing.append(row)
                    continue
                actual = "sha256:" + util.sha256_file(path)
                if actual == dig:
                    ok.append(row)
                elif kind == "file":
                    changed.append({**row, "actual": actual})
                else:
                    tampered.append({**row, "actual": actual})
        return {
            "total": len(ok) + len(tampered) + len(changed) + len(missing),
            "ok": ok,
            "tampered": tampered,
            "changed": changed,
            "missing": missing,
            "skipped": skipped,
        }


def _norm(text: str) -> str:
    return " ".join(str(text).split())


def _next_done_id(contract: dict[str, Any]) -> str:
    used = {d.get("id") for d in contract.get("done", [])}
    i = 1
    while f"d{i}" in used:
        i += 1
    return f"d{i}"


def find_root(start: str | os.PathLike | None = None, name: str = DEFAULT_DIR) -> Path | None:
    """Walk up from *start* looking for an existing ``.nightshift`` directory."""
    here = Path(start or os.getcwd()).resolve()
    for parent in [here, *here.parents]:
        candidate = parent / name
        if (candidate / "contract.json").exists():
            return candidate
    return None
