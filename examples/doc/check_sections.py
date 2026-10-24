"""Example done-criterion: every expected section heading is present.

Used in examples/README.md scenario 3. Exits 0 only when all headings exist.

    python examples/doc/check_sections.py proposal.md
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SECTIONS = [
    "Summary",
    "Background",
    "Aims",
    "Methods",
    "Timeline",
    "Budget",
    "Risks",
    "Team",
    "References",
]


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: check_sections.py <markdown file>")
        return 2
    path = Path(argv[1])
    if not path.exists():
        print(f"missing file: {path}")
        return 2

    text = path.read_text(encoding="utf-8", errors="replace")
    headings = {m.group(1).strip().lower() for m in re.finditer(r"^#{1,3}\s+(.+)$", text, re.M)}

    missing = [s for s in SECTIONS if s.lower() not in headings]
    print(f"{len(SECTIONS) - len(missing)}/{len(SECTIONS)} sections present")
    for s in missing:
        print(f"  missing: {s}")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
