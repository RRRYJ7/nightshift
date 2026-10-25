"""Render the English landscape trailer (1920x1080) for X / YouTube / HN.

    python tools/make_video_wide.py            # docs/nightshift-wide.mp4
    python tools/make_video_wide.py --stills

Same rules as the vertical cut: no audio (add a track where you post it), no
external fonts beyond the ones shipped with Windows, and blending done by hand
because converting RGBA to RGB throws the alpha away.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "nightshift-wide.mp4"
REPO = "github.com/RRRYJ7/nightshift"

W, H = 1920, 1080
FPS = 30
DUR = 31.0

BG = (7, 9, 14)
PANEL = (15, 20, 28)
INK = (233, 238, 244)
DIM = (146, 156, 168)
FAINT = (58, 70, 86)
CYAN = (34, 211, 238)
GREEN = (52, 211, 153)
RED = (248, 113, 113)
AMBER = (251, 191, 36)

SANS_B = r"C:\Windows\Fonts\segoeuib.ttf"
SANS = r"C:\Windows\Fonts\segoeui.ttf"
MONO = r"C:\Windows\Fonts\consola.ttf"
MONO_B = r"C:\Windows\Fonts\consolab.ttf"

F_EYE = ImageFont.truetype(MONO_B, 26)
F_H1 = ImageFont.truetype(SANS_B, 66)
F_H2 = ImageFont.truetype(SANS_B, 54)
F_SUB = ImageFont.truetype(SANS, 34)
F_SMALL = ImageFont.truetype(SANS, 26)
F_MONO = ImageFont.truetype(MONO, 30)
F_MONO_B = ImageFont.truetype(MONO_B, 30)
F_MONO_S = ImageFont.truetype(MONO, 25)
F_MONO_L = ImageFont.truetype(MONO_B, 44)
F_BIG = ImageFont.truetype(MONO_B, 96)

LX = 120          # left column x
CW_X0, CW_X1 = 1040, 1800   # card box
CW_Y0, CW_Y1 = 300, 880


# --------------------------------------------------------------------------- #

def env(t: float, dur: float, fin: float = 0.4, fout: float = 0.35) -> float:
    a = min(1.0, t / fin) if fin > 0 else 1.0
    b = min(1.0, (dur - t) / fout) if fout > 0 else 1.0
    return max(0.0, min(a, b))


def blend(color, alpha: float, bg=BG):
    a = max(0.0, min(1.0, alpha))
    return tuple(int(c * a + b * (1 - a)) for c, b in zip(color, bg))


def put(d, xy, text, font, color, alpha=1.0, anchor="la", bg=BG):
    if alpha <= 0.02:
        return
    d.text(xy, text, font=font, fill=blend(color, alpha, bg), anchor=anchor)


def card(d, alpha, bg=BG):
    if alpha <= 0.02:
        return
    d.rounded_rectangle([CW_X0, CW_Y0, CW_X1, CW_Y1], radius=28,
                        fill=blend(PANEL, alpha * 0.97, bg),
                        outline=blend((40, 50, 64), alpha, bg), width=2)


def scene_head(d, num, eyebrow, headline, sub, a, sub_a=None):
    put(d, (LX, 340), "%s  ·  %s" % (num, eyebrow), F_EYE, CYAN, a)
    put(d, (LX, 392), headline, F_H1, INK, a)
    if sub:
        put(d, (LX, 496), sub, F_SUB, DIM, sub_a if sub_a is not None else a)


# --------------------------------------------------------------------------- #
# scenes
# --------------------------------------------------------------------------- #

def scene1(d, t, dur):
    a = env(t, dur)
    scene_head(d, "01", "02:41", "You're asleep.", "The agent is not.", a, env(t - 0.6, dur - 0.6))
    card(d, a)
    y = CW_Y0 + 70
    lines = [
        ("$ nsh init --goal \"ship the CSV exporter\"", CYAN),
        ("  flight plan created, deadline 06:30", DIM),
        ("$ nsh run -- python -m pytest -q", CYAN),
        ("  running 14 tests ... ok    exit 0", GREEN),
        ("$ nsh tick --progress 40", CYAN),
        ("  drift: clean", GREEN),
    ]
    for i, (text, color) in enumerate(lines):
        la = env(t - 0.5 - i * 0.35, dur, 0.3, 0.2)
        put(d, (CW_X0 + 50, y), text, F_MONO_S, color, la, bg=PANEL)
        y += 74
    if int(t * 2) % 2 == 0:
        d.rectangle([CW_X0 + 50, y - 26, CW_X0 + 64, y - 6], fill=blend(INK, a, PANEL))


def scene2(d, t, dur):
    a = env(t, dur)
    scene_head(d, "02", "the morning", "It says it's done.", "Nothing in that sentence is checkable.", a)
    card(d, a)
    # chat bubble
    d.rounded_rectangle([CW_X0 + 40, CW_Y0 + 60, CW_X1 - 40, CW_Y0 + 300], radius=22,
                        fill=blend((24, 30, 40), a, PANEL), outline=blend(FAINT, a, PANEL), width=2)
    put(d, (CW_X0 + 70, CW_Y0 + 92), "agent", F_MONO_S, DIM, a, bg=(24, 30, 40))
    put(d, (CW_X0 + 70, CW_Y0 + 136), "Done! I refactored the parser", F_MONO, INK, a, bg=(24, 30, 40))
    put(d, (CW_X0 + 70, CW_Y0 + 182), "and added tests. They might", F_MONO, INK, a, bg=(24, 30, 40))
    put(d, (CW_X0 + 70, CW_Y0 + 228), "need a small tweak.", F_MONO, INK, a, bg=(24, 30, 40))
    marks = [("checkable", "no"), ("which tests?", "no"), ("ran when?", "no")]
    y = CW_Y0 + 360
    for i, (label, verdict) in enumerate(marks):
        la = env(t - 1.0 - i * 0.35, dur, 0.35, 0.2)
        put(d, (CW_X0 + 60, y), label, F_MONO, DIM, la, bg=PANEL)
        put(d, (CW_X1 - 150, y), verdict, F_MONO_B, RED, la, bg=PANEL)
        y += 70


def scene3(d, t, dur):
    a = env(t, dur)
    scene_head(d, "03", "the plan", "So \"done\" gets defined.", "3-6 criteria. Each one a command.", a)
    card(d, a)
    put(d, (CW_X0 + 50, CW_Y0 + 46), "flight plan", F_MONO_S, DIM, a, bg=PANEL)
    rows = [
        ("d1", "tests pass", "python -m pytest -q"),
        ("d2", "the CLI builds", "npm run build"),
        ("d3", "quickstart exists", "python check_readme.py"),
    ]
    y = CW_Y0 + 130
    for i, (cid, label, cmd) in enumerate(rows):
        ra = env(t - 0.4 - i * 0.4, dur, 0.4, 0.2)
        if ra > 0.02:
            d.rounded_rectangle([CW_X0 + 40, y, CW_X1 - 40, y + 150], radius=16,
                                fill=blend((20, 26, 36), ra, PANEL),
                                outline=blend(FAINT, ra, PANEL), width=2)
            put(d, (CW_X0 + 70, y + 28), cid, F_MONO_L, CYAN, ra, bg=(20, 26, 36))
            put(d, (CW_X0 + 160, y + 22), label, F_SUB, INK, ra, bg=(20, 26, 36))
            put(d, (CW_X0 + 160, y + 84), cmd, F_MONO_S, DIM, ra, bg=(20, 26, 36))
        y += 180


def scene4(d, t, dur):
    a = env(t, dur)
    green_phase = t > 2.6
    scene_head(d, "04", "the gate",
               "Prove it, or say you didn't." if not green_phase else "Green, or an honest red.",
               "The agent does not get to grade its own homework.", a)
    card(d, a)
    if not green_phase:
        ra = env(t, dur)
        put(d, (CW_X0 + 60, CW_Y0 + 70), "GATE RED", F_BIG, RED, ra, bg=PANEL)
        put(d, (CW_X0 + 60, CW_Y0 + 200), "2 of 5 criteria unproven", F_MONO, INK, ra * env(t - 0.5, dur - 0.5), bg=PANEL)
        rows = [("X", "d3  three templates render", "check failed (exit 1)"),
                ("X", "d5  CI is green", "never checked")]
        y = CW_Y0 + 300
        for i, (m, what, why) in enumerate(rows):
            la = env(t - 0.9 - i * 0.3, dur, 0.3, 0.2)
            put(d, (CW_X0 + 60, y), m, F_MONO, RED, la, bg=PANEL)
            put(d, (CW_X0 + 105, y), what, F_MONO_S, INK, la, bg=PANEL)
            put(d, (CW_X0 + 105, y + 44), why, F_MONO_S, DIM, la, bg=PANEL)
            y += 120
    else:
        ra = env(t - 2.6, dur - 2.6, 0.35, 0.2)
        put(d, (CW_X0 + 60, CW_Y0 + 70), "GATE GREEN", F_BIG, GREEN, ra, bg=PANEL)
        put(d, (CW_X0 + 60, CW_Y0 + 200), "5 / 5 criteria proven with evidence", F_MONO, INK, ra, bg=PANEL)
        rows = [("5/5", "criteria"), ("100%", "of steps carry proof"), ("16", "artefacts hashed")]
        y = CW_Y0 + 300
        for i, (v, k) in enumerate(rows):
            la = env(t - 3.0 - i * 0.15, dur, 0.3, 0.2)
            put(d, (CW_X0 + 60, y), v, F_MONO_L, CYAN, la, bg=PANEL)
            put(d, (CW_X0 + 230, y + 12), k, F_MONO_S, DIM, la, bg=PANEL)
            y += 90


def scene5(d, t, dur):
    a = env(t, dur)
    scene_head(d, "05", "the report", "Ten lines, not a fantasy.", "One HTML file. No JS, no CDN.", a)
    card(d, a)
    brief = [
        ("GOAL", "ship the report CLI"),
        ("WINDOW", "7h32m used · 27m left"),
        ("EVIDENCE", "85% of steps carry proof"),
        ("GATE", "GREEN · 5/5 proven"),
        ("RISK", "2 medium drift flags"),
        ("TREND", "improving · +68 pts"),
    ]
    y = CW_Y0 + 70
    for i, (k, v) in enumerate(brief):
        la = env(t - 0.4 - i * 0.22, dur, 0.3, 0.2)
        put(d, (CW_X0 + 55, y), k, F_MONO_S, CYAN, la, bg=PANEL)
        put(d, (CW_X0 + 260, y - 4), v, F_MONO, INK, la, bg=PANEL)
        y += 92


def scene6(d, t, dur):
    a = env(t, dur, 0.5, 0.4)
    put(d, (W / 2, 380), "Give your agent a night shift.", F_H1, INK, a, anchor="ma")
    put(d, (W / 2, 500), "Wake up to a flight report, not a fantasy.", F_H2, DIM, env(t - 0.4, dur - 0.4), anchor="ma")
    if t > 0.9:
        ra = env(t - 0.9, dur - 0.9, 0.5, 0.3)
        put(d, (W / 2, 670), "NIGHTSHIFT", ImageFont.truetype(MONO_B, 110), CYAN, ra, anchor="ma")
        put(d, (W / 2, 820), REPO, F_MONO, DIM, ra, anchor="ma")
        put(d, (W / 2, 890), "MIT  ·  zero dependencies  ·  a skill + a CLI", F_SMALL, FAINT, ra, anchor="ma")


SCENES = [
    (0.0, 4.6, scene1),
    (4.6, 10.2, scene2),
    (10.2, 15.4, scene3),
    (15.4, 21.6, scene4),
    (21.6, 26.0, scene5),
    (26.0, DUR, scene6),
]


# --------------------------------------------------------------------------- #

def frame_at(t: float) -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    for start, end, fn in SCENES:
        if start <= t < end:
            fn(d, t - start, end - start)
            break
    # wordmark + progress
    put(d, (64, 54), "NIGHTSHIFT", ImageFont.truetype(MONO_B, 22), CYAN, 0.55)
    d.rectangle([0, H - 8, W, H], fill=FAINT)
    d.rectangle([0, H - 8, int(W * min(1.0, t / DUR)), H], fill=CYAN)
    return img


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stills", action="store_true")
    args = ap.parse_args()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    total = int(DUR * FPS)
    print(f"rendering {total} frames at {W}x{H} ...")
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(OUT),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    assert proc.stdin is not None
    stills = {int(total * f) for f in (0.08, 0.28, 0.45, 0.62, 0.78, 0.94)} if args.stills else set()
    for i in range(total):
        img = frame_at(i / FPS)
        if i in stills:
            p = ROOT / "docs" / "frames" / f"wide-{i:05d}.png"
            p.parent.mkdir(exist_ok=True)
            img.save(p)
        proc.stdin.write(img.tobytes())
        if i % 150 == 0:
            print(f"  {i}/{total}", flush=True)
    proc.stdin.close()
    err = proc.stderr.read().decode("utf-8", "replace") if proc.stderr else ""
    if proc.wait() != 0:
        print(err, file=sys.stderr)
        return 1
    print(f"wrote {OUT}  ({OUT.stat().st_size / 1024 / 1024:.1f} MiB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
