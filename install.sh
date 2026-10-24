#!/usr/bin/env bash
# Install the NIGHTSHIFT skill into an agent's skills directory.
#   ./install.sh                 -> ~/.claude/skills/nightshift
#   ./install.sh ~/.dsh/skills   -> custom target
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${1:-$HOME/.claude/skills}"
DEST="$TARGET/nightshift"

mkdir -p "$DEST"
cp -R "$HERE/nightshift" "$DEST/"
for f in SKILL.md README.md LICENSE pyproject.toml; do
  [ -f "$HERE/$f" ] && cp "$HERE/$f" "$DEST/"
done

echo "skill  -> $DEST"
echo
echo "put the CLI on PATH (pick one):"
echo "  pipx install \"$HERE\"          # isolated, recommended"
echo "  python -m pip install --user -e \"$HERE\""
echo "  alias nsh='python -m nightshift'   # no install at all"
echo
echo "then, in any project:   nsh init --goal \"...\" --deadline 06:30"
