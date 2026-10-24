"""Verify the documentation set is present and non-trivial.

Used as a done-criterion in this repository's own flight plan, and in CI.
Exit 0 only if every required document exists and contains its required markers.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

REQUIRED = [
    ("README.md", 4000, ["nsh gate", "flight report", "SKILL.md", "Not proven"]),
    ("README.zh-CN.md", 2000, ["夜班", "nsh gate"]),
    ("SKILL.md", 3000, ["name: nightshift", "seven laws", "nsh tick"]),
    ("docs/PROTOCOL.md", 3000, ["events.jsonl", "gate", "Threat model"]),
    ("docs/WHY.md", 2000, ["receipts", "gate"]),
    ("docs/BENCHMARKS.md", 1500, ["precision", "false negative"]),
    ("docs/WALKTHROUGH.md", 2500, ["nsh gate", "nsh verify"]),
    ("CONTRIBUTING.md", 500, ["bench/cases"]),
    ("LICENSE", 1000, ["MIT License"]),
    ("install.sh", 200, ["nsh init"]),
    ("install.ps1", 200, ["nsh init"]),
]


def main() -> int:
    failures = []
    print()
    print("  docs check")
    print("  " + "-" * 60)
    for name, min_bytes, markers in REQUIRED:
        path = ROOT / name
        if not path.exists():
            failures.append(f"{name}: missing")
            print(f"  x {name:<24} missing")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        size = len(text.encode("utf-8"))
        missing = [m for m in markers if m.lower() not in text.lower()]
        if size < min_bytes:
            failures.append(f"{name}: {size} bytes < {min_bytes}")
        if missing:
            failures.append(f"{name}: missing markers {missing}")
        ok = size >= min_bytes and not missing
        print(f"  {'ok' if ok else 'x '} {name:<24} {size:>7} bytes"
              + ("" if ok else f"  {'size' if size < min_bytes else 'markers'}"))
    print("  " + "-" * 60)
    if failures:
        for f in failures:
            print("  FAIL " + f)
        return 1
    print(f"  {len(REQUIRED)} documents ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
