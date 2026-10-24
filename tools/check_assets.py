"""Verify the demo assets exist and are big enough to be real.

Used as a done-criterion in this repository's own flight plan, and in CI.
Exit 0 only if the gif, the report screenshot and the vertical video are present.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

REQUIRED = [
    ("docs/demo.gif", 150_000, "terminal demo for the README"),
    ("docs/flight-report.png", 40_000, "screenshot of the rendered flight report"),
    ("docs/flight-report-red.png", 40_000, "the report for a failed shift"),
    ("docs/nightshift-vertical.mp4", 500_000, "1080x1920 promo video"),
]


def main() -> int:
    failures = []
    print()
    print("  assets check")
    print("  " + "-" * 60)
    for name, min_bytes, why in REQUIRED:
        path = ROOT / name
        if not path.exists():
            failures.append(f"{name}: missing ({why})")
            print(f"  x  {name:<32} missing")
            continue
        size = path.stat().st_size
        ok = size >= min_bytes
        if not ok:
            failures.append(f"{name}: {size} bytes < {min_bytes}")
        print(f"  {'ok' if ok else 'x '} {name:<32} {size / 1024:8.0f} KiB  {why}")
    print("  " + "-" * 60)
    if failures:
        for f in failures:
            print("  FAIL " + f)
        return 1
    print("  all demo assets present")
    return 0


if __name__ == "__main__":
    sys.exit(main())
