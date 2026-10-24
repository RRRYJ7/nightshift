"""Render docs/demo.gif — a terminal recording of a real NIGHTSHIFT session.

The output in the gif is not written by hand: every frame is built from the
stdout of an actual `python -m nightshift ...` run inside a throwaway directory,
with a check that fails first and passes after the fix.

    python tools/make_demo_gif.py            # writes docs/demo.gif
    python tools/make_demo_gif.py --stills   # also writes docs/frames/*.png
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "demo.gif"

W, H = 860, 500
BG = (13, 17, 23)
BAR = (22, 27, 34)
INK = (230, 237, 243)
DIM = (139, 148, 158)
GREEN = (126, 231, 135)
RED = (248, 81, 73)
CYAN = (121, 192, 255)
YELLOW = (210, 168, 255)

FONT = ImageFont.truetype(r"C:\Windows\Fonts\consola.ttf", 15)
FONT_B = ImageFont.truetype(r"C:\Windows\Fonts\consolab.ttf", 15)
FONT_T = ImageFont.truetype(r"C:\Windows\Fonts\consola.ttf", 13)

LINE_H = 22
PAD_X = 26
TOP = 58
MAX_LINES = (H - TOP - 18) // LINE_H


def run(cwd: str, *args: str) -> str:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    env["PYTHONIOENCODING"] = "utf-8"
    env["NO_COLOR"] = "1"
    cp = subprocess.run([sys.executable, "-m", "nightshift", *args], cwd=cwd, env=env,
                        capture_output=True, text=True, encoding="utf-8", errors="replace")
    text = (cp.stdout or "") + (cp.stderr or "")
    return text.strip("\n")


def build_session() -> list[tuple[str, list[str]]]:
    """Run a real session and return [(displayed command, output lines)]."""
    tmp = tempfile.mkdtemp(prefix="nsh-gif-")
    try:
        # a done-criterion that is false until README.md exists
        Path(tmp, "check_readme.py").write_text(
            "import os, sys\nsys.exit(0 if os.path.exists('README.md') else 1)\n",
            encoding="utf-8",
        )
        Path(tmp, "make_readme.py").write_text(
            "open('README.md', 'w').write('# NIGHTSHIFT\\n')\n", encoding="utf-8"
        )
        Path(tmp, "tests_pass.py").write_text("print('12 passed')\n", encoding="utf-8")

        scenes: list[tuple[str, list[str]]] = []

        def add(cmd: str, *args: str) -> None:
            out = run(tmp, *args)
            scenes.append((cmd, [ln for ln in out.splitlines() if ln.strip()]))

        add('nsh init --goal "ship the report CLI" --deadline 06:40', "init",
            "--goal", "ship the report CLI", "--deadline", "06:40")
        add('nsh done add "tests pass" -- python tests_pass.py', "done", "add", "tests pass", "--",
            "python", "tests_pass.py")
        add('nsh done add "README ships" -- python check_readme.py', "done", "add", "README ships", "--",
            "python", "check_readme.py")
        add("nsh gate", "gate")
        add("nsh check d1", "check", "d1")
        add("nsh check d2", "check", "d2")
        add("nsh run -- python make_readme.py", "run", "--", "python", "make_readme.py")
        add("nsh check d2", "check", "d2")
        add("nsh gate", "gate")
        add("nsh brief", "brief")
        return scenes
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --------------------------------------------------------------------------- #
# rendering
# --------------------------------------------------------------------------- #

def sanitize(text: str) -> str:
    """Consolas has no glyphs for these; a tofu box in a demo gif is a bug."""
    for bad, good in (
        ("✈ ", ""), ("✈", ""),
        ("✓", "OK"), ("✗", "X"), ("⚠", "!"), ("◐", "~"),
        ("●", "*"), ("○", "-"), ("▸", ">"), ("·", "-"),
        ("—", "-"), ("→", "->"), ("…", "..."),
    ):
        text = text.replace(bad, good)
    return text


def line_style(text: str) -> tuple[tuple[int, int, int], ImageFont.FreeTypeFont]:
    t = text.strip()
    if "PASS" in t or "GATE GREEN" in t or "proven" == t.lower():
        return GREEN, FONT
    if "FAIL" in t or "GATE RED" in t or t.startswith("X"):
        return RED, FONT
    if t.startswith("$") or t.startswith("nsh "):
        return INK, FONT
    if t.split(" ")[0] in ("GATE", "EVIDENCE", "WINDOW", "GOAL", "ACTIVITY", "RISK", "TREND", "NOT"):
        return CYAN, FONT_B
    if t.startswith("GATE") or t.startswith("EVIDENCE") or t.startswith("WINDOW"):
        return CYAN, FONT_B
    return DIM, FONT


def draw_frame(lines: list[tuple[str, tuple[int, int, int], ImageFont.FreeTypeFont]],
               cursor: tuple[int, int] | None, subtitle: str = "") -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    d.rectangle([0, 0, W, 34], fill=BAR)
    for i, col in enumerate([(255, 95, 87), (254, 188, 46), (40, 200, 64)]):
        d.ellipse([16 + i * 18, 12, 28 + i * 18, 24], fill=col)
    d.text((80, 10), "nightshift  ·  02:41  ·  .nightshift/", font=FONT_T, fill=DIM)

    y = TOP
    for text, color, font in lines[-MAX_LINES:]:
        d.text((PAD_X, y), text, font=font, fill=color)
        y += LINE_H

    if cursor is not None:
        cx, cy = cursor
        d.rectangle([cx, cy + 3, cx + 9, cy + 16], fill=INK)

    if subtitle:
        d.text((PAD_X, H - 22), subtitle, font=FONT_T, fill=(90, 100, 115))
    return img


def make_frames(scenes: list[tuple[str, list[str]]]) -> tuple[list[Image.Image], list[list]]:
    frames: list[Image.Image] = []
    history: list[tuple[str, tuple[int, int, int], ImageFont.FreeTypeFont]] = []

    history.append(("  NIGHTSHIFT - a flight recorder for long agent runs", CYAN, FONT_T))
    history.append(("", DIM, FONT))
    for _ in range(6):
        frames.append(draw_frame(history, (PAD_X, TOP + len(history) * LINE_H - 18)))

    for idx, (cmd, out_lines) in enumerate(scenes, start=1):
        prompt = ("$ ", GREEN, FONT_B)
        # typing
        for i in range(1, len(cmd) + 1, 2):
            partial = cmd[:i]
            shown = history + [(prompt[0] + partial, INK, FONT)]
            y = TOP + (len(history)) * LINE_H
            frames.append(draw_frame(shown, (PAD_X + 12 + i * 8, y + 2)))
        # commit the command
        history.append(("$ " + cmd, INK, FONT))
        for k, raw in enumerate(out_lines):
            raw = sanitize(raw)
            color, font = line_style(raw)
            text = raw if len(raw) <= 92 else raw[:91] + "..."
            history.append(("  " + text, color, font))
            if k % 2 == 0 or k == len(out_lines) - 1:
                y = TOP + len(history) * LINE_H
                frames.append(draw_frame(history, (PAD_X + 9, min(y, TOP + MAX_LINES * LINE_H))))
        for _ in range(9):
            frames.append(draw_frame(history, None))
        history.append(("", DIM, FONT))

    # outro
    history.append(("", DIM, FONT))
    history.append(("  every claim: a receipt.   every receipt: replayable.", CYAN, FONT_B))
    for _ in range(22):
        frames.append(draw_frame(history, None))
    return frames, history


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stills", action="store_true")
    args = ap.parse_args()

    print("running a real session ...")
    scenes = build_session()
    for cmd, out in scenes:
        print(f"  $ {cmd}  ({len(out)} lines)")

    frames, _ = make_frames(scenes)
    print(f"rendering {len(frames)} frames ...")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    pal = [f.quantize(colors=64, method=Image.MEDIANCUT) for f in frames]
    pal[0].save(OUT, save_all=True, append_images=pal[1:], duration=90, loop=0, optimize=True)
    print(f"wrote {OUT}  ({OUT.stat().st_size / 1024:.0f} KiB)")

    if args.stills:
        outdir = ROOT / "docs" / "frames"
        outdir.mkdir(exist_ok=True)
        for i in (10, len(frames) // 2, len(frames) - 8):
            frames[i].save(outdir / f"frame-{i:04d}.png")
            print(f"  still: docs/frames/frame-{i:04d}.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
