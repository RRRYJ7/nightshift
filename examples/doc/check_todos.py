"""Example done-criterion: no TODO / FIXME / TBD placeholders survive.

    python examples/doc/check_todos.py proposal.md
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PATTERN = re.compile(r"\b(TODO|FIXME|TBD|XXX)\b")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: check_todos.py <markdown file>")
        return 2
    path = Path(argv[1])
    if not path.exists():
        print(f"missing file: {path}")
        return 2

    hits = []
    for i, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if PATTERN.search(line):
            hits.append((i, line.strip()[:90]))

    if not hits:
        print("no placeholders left")
        return 0
    print(f"{len(hits)} placeholder(s):")
    for i, line in hits[:20]:
        print(f"  {path}:{i}: {line}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
