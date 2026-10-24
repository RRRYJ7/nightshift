"""Render the vertical promo video (1080x1920) and pipe it straight into ffmpeg.

    python tools/make_video.py                 # docs/nightshift-vertical.mp4
    python tools/make_video.py --stills        # + docs/frames/video-*.png

No audio track on purpose: on Douyin/TikTok you add the trending sound in the
app, and a bad synthesized voice is worse than silence.

Note on fading: we blend colours against the known background by hand instead of
drawing RGBA and converting. Converting an RGBA image to RGB throws the alpha
channel away, which turns "10 % opacity" into "100 % opacity" — a bug that looks
like a design choice.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "nightshift-vertical.mp4"
REPO = "github.com/chchliu/nightshift"

W, H = 1080, 1920
FPS = 30
DUR = 33.0

BG = (6, 8, 13)
PANEL = (15, 20, 28)
INK = (231, 237, 243)
DIM = (139, 148, 158)
FAINT = (58, 70, 86)
CYAN = (34, 211, 238)
GREEN = (52, 211, 153)
RED = (248, 113, 113)
AMBER = (251, 191, 36)

YB = r"C:\Windows\Fonts\msyhbd.ttc"
YR = r"C:\Windows\Fonts\msyh.ttc"
MO = r"C:\Windows\Fonts\consola.ttf"
MOB = r"C:\Windows\Fonts\consolab.ttf"

F_CLOCK = ImageFont.truetype(MOB, 170)
F_H1 = ImageFont.truetype(YB, 84)
F_H2 = ImageFont.truetype(YB, 60)
F_BODY = ImageFont.truetype(YR, 44)
F_SMALL = ImageFont.truetype(YR, 32)
F_Y_S = ImageFont.truetype(YR, 27)
F_MONO = ImageFont.truetype(MO, 32)
F_MONO_S = ImageFont.truetype(MO, 25)
F_MONO_B = ImageFont.truetype(MOB, 36)
F_MARK = ImageFont.truetype(MOB, 20)
F_GIANT = ImageFont.truetype(MOB, 150)


# --------------------------------------------------------------------------- #
# primitives
# --------------------------------------------------------------------------- #

def env(t: float, dur: float, fin: float = 0.35, fout: float = 0.3) -> float:
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


def card(d, box, alpha, bg=BG):
    if alpha <= 0.02:
        return
    d.rounded_rectangle(box, radius=28, fill=blend(PANEL, alpha * 0.96, bg),
                        outline=blend((38, 48, 62), alpha, bg), width=2)


def header(d, idx, label, alpha=1.0):
    put(d, (W / 2, 178), "%02d  ·  %s" % (idx, label), F_Y_S, CYAN, alpha, anchor="ma")


def caption(d, y, text, color=DIM, alpha=1.0, font=None):
    put(d, (W / 2, y), text, font or F_BODY, color, alpha, anchor="ma")


def progress(d, t):
    d.rectangle([0, H - 7, W, H], fill=FAINT)
    d.rectangle([0, H - 7, int(W * min(1.0, t / DUR)), H], fill=CYAN)


def wordmark(d, alpha=1.0):
    put(d, (64, 54), "NIGHTSHIFT", F_MARK, CYAN, alpha)
    put(d, (64 + 166, 54), "·  a flight recorder for long agent runs", F_MARK, DIM, alpha * 0.85)


# --------------------------------------------------------------------------- #
# scenes
# --------------------------------------------------------------------------- #

def scene1(d, t, dur):
    a = env(t, dur)
    put(d, (W / 2, 300), "10 月 25 日 · 周六", F_SMALL, DIM, a, anchor="ma")
    pulse = 0.55 + 0.45 * (1.0 if int(t * 2) % 2 == 0 else 0.55)
    put(d, (W / 2, 420), "02:41", F_CLOCK, CYAN, a * pulse, anchor="ma")
    if t > 0.8:
        put(d, (W / 2, 800), "你睡了。", F_H1, INK, env(t - 0.8, dur - 0.8), anchor="ma")
    if t > 1.8:
        put(d, (W / 2, 930), "Agent 还在跑。", F_H2, DIM, env(t - 1.8, dur - 1.8), anchor="ma")
    if t > 2.7:
        caption(d, 1500, "—— 但你不知道它跑成什么样", FAINT, env(t - 2.7, dur - 2.7), F_SMALL)


def scene2(d, t, dur):
    a = env(t, dur)
    header(d, 2, "记录", a)
    put(d, (W / 2, 300), "它记得自己很努力。", F_H1, INK, a, anchor="ma")
    card(d, (80, 520, W - 80, 1430), a)
    put(d, (120, 556), "black box · .nightshift/events.jsonl", F_MONO_S, DIM, a * 0.9, bg=PANEL)
    lines = [
        ("$ nsh run -- cargo test", CYAN),
        ("  running 14 tests ... ok   exit 0", DIM),
        ("$ nsh step \"refactor parser\" -e src/parser.rs", CYAN),
        ("  evidence sha256:9f2c1a3b ...", DIM),
        ("$ nsh tick --progress 40", CYAN),
        ("  drift: clean", GREEN),
        ("$ nsh tick --progress 41", CYAN),
        ("  drift: medium  src/render.rs x4", AMBER),
    ]
    y = 630
    shown = min(len(lines), int(max(0, t - 0.3) * 3.2) + 1)
    for text, color in lines[:shown]:
        put(d, (125, y), text[:52], F_MONO_S, color, 0.95, bg=PANEL)
        y += 96
    caption(d, 1510, "日志里没有一句“我觉得做完了”。", DIM, env(t - 3.6, dur - 3.6))


def scene3(d, t, dur):
    a = env(t, dur)
    header(d, 3, "约定", a)
    put(d, (W / 2, 290), "先写清楚：什么算完成。", F_H1, INK, a, anchor="ma")
    card(d, (80, 480, W - 80, 1400), a)
    put(d, (120, 516), "flight plan  /  飞行计划", F_Y_S, DIM, a * 0.9, bg=PANEL)
    rows = [
        ("d1", "测试全绿", "python -m pytest -q"),
        ("d2", "能构建", "npm run build"),
        ("d3", "有快速上手", "python check_readme.py"),
    ]
    y = 600
    for i, (cid, label, cmd) in enumerate(rows):
        ra = env(t - 0.3 - i * 0.35, dur, 0.4, 0.2)
        if ra > 0.02:
            d.rounded_rectangle([120, y, W - 120, y + 220], radius=18,
                                fill=blend((20, 26, 36), ra, PANEL),
                                outline=blend(FAINT, ra), width=2)
            put(d, (152, y + 40), cid, F_MONO_B, CYAN, ra, bg=(20, 26, 36))
            put(d, (232, y + 30), label, F_BODY, INK, ra, bg=(20, 26, 36))
            put(d, (232, y + 128), cmd, F_MONO_S, DIM, ra, bg=(20, 26, 36))
        y += 250
    caption(d, 1470, "每条标准，都能被一条命令判真假。", GREEN, env(t - 1.9, dur - 1.9))
    caption(d, 1545, "判不了真假的，不算标准。", DIM, env(t - 2.3, dur - 2.3), F_SMALL)


def scene4(d, t, dur):
    a = env(t, dur)
    header(d, 4, "漂移", a)
    put(d, (W / 2, 290), "然后它开始漂。", F_H1, INK, a, anchor="ma")

    x0, x1, y = 110, W - 110, 720
    d.line([x0, y, x1, y], fill=blend(FAINT, a), width=3)
    for i in range(9):
        hour = (22 + i) % 24
        put(d, (x0 + (x1 - x0) * i / 8, y + 22), "%02d:00" % hour, F_MONO_S, DIM, a * 0.65, anchor="ma")

    n = int(max(0, t - 0.3) * 11)
    for i in range(min(n, 60)):
        x = x0 + (x1 - x0) * i / 60
        d.line([x, y, x, y - (44 if i % 5 == 0 else 26)], fill=blend(INK, a * 0.55), width=2)

    if t > 0.7:
        ra = env(t - 0.7, dur - 0.7)
        card(d, (80, 870, W - 80, 1320), ra)
        put(d, (120, 902), "live", F_MONO_S, DIM, ra, bg=PANEL)
        log = [
            ("01:58  step   run the fixture suite", DIM),
            ("02:26  step   polish renderer spacing", DIM),
            ("03:02  step   polish renderer again", AMBER),
            ("03:12  flag   churn  src/render.rs x4", RED),
        ]
        yy = 960
        for j, (text, color) in enumerate(log):
            la = env(t - 0.7 - j * 0.45, dur, 0.3, 0.2)
            if la > 0.02:
                put(d, (125, yy), text, F_MONO_S, color, la, bg=PANEL)
            yy += 86

    if t > 1.5:
        pa = env(t - 1.5, dur - 1.5, 0.3, 0.2)
        px = x0 + (x1 - x0) * 0.46
        r = int(15 * min(1.0, (t - 1.5) / 0.3)) or 1
        d.ellipse([px - r, y - 96 - r, px + r, y - 96 + r], fill=blend(RED, pa))
        put(d, (px, y - 152), "D3 churn", F_MONO_S, RED, pa, anchor="ma")
        caption(d, 1410, "03:12  它花了 40 分钟，改一个你没要的落地页。", AMBER, pa, F_SMALL)
        caption(d, 1480, "每一步都合理，加起来是灾难。", DIM, pa, F_SMALL)


def scene5(d, t, dur):
    a = env(t, dur)
    header(d, 5, "拦截", a)
    put(d, (W / 2, 430), "GATE RED", F_GIANT, RED, a, anchor="ma")
    if t > 0.5:
        put(d, (W / 2, 660), "2 项完成标准，没有证据。", ImageFont.truetype(YB, 76), INK, env(t - 0.5, dur - 0.5), anchor="ma")
    if t > 1.2:
        put(d, (W / 2, 810), "所以它不能说「搞定了」。", F_H2, DIM, env(t - 1.2, dur - 1.2), anchor="ma")
    if t > 1.6:
        ra = env(t - 1.6, dur - 1.6)
        card(d, (80, 1000, W - 80, 1330), ra)
        put(d, (120, 1036), "$ nsh gate", F_MONO, CYAN, ra, bg=PANEL)
        put(d, (120, 1116), "X  d3   README has a quickstart", F_MONO, RED, ra, bg=PANEL)
        put(d, (165, 1176), "never checked", F_MONO_S, DIM, ra, bg=PANEL)
        put(d, (120, 1236), "GATE RED - do not call this done.", F_MONO_S, RED, ra * 0.9, bg=PANEL)
    caption(d, 1460, "红门不是这一夜的失败，红门是这一夜的产物。", DIM, env(t - 2.4, dur - 2.4), F_SMALL)


def scene6(d, t, dur):
    a = env(t, dur)
    header(d, 6, "结算", a)
    put(d, (W / 2, 350), "GATE GREEN", ImageFont.truetype(MOB, 118), GREEN, a, anchor="ma")
    if t > 0.5:
        put(d, (W / 2, 520), "5 / 5 条标准，都带证据通过。", F_H2, INK, env(t - 0.5, dur - 0.5), anchor="ma")
    chips = [("7h32m", "用时"), ("33", "步"), ("85%", "有证据"), ("2", "漂移告警")]
    if t > 0.45:
        for i, (v, k) in enumerate(chips):
            ca = env(t - 0.45 - i * 0.1, dur - 0.45, 0.3, 0.2)
            if ca <= 0.02:
                continue
            x = 80 + i * 236
            d.rounded_rectangle([x, 630, x + 216, 830], radius=22,
                                fill=blend(PANEL, ca), outline=blend(FAINT, ca), width=2)
            put(d, (x + 108, 664), v, F_H2, AMBER if i == 3 else CYAN, ca, anchor="ma", bg=PANEL)
            put(d, (x + 108, 762), k, F_SMALL, DIM, ca, anchor="ma", bg=PANEL)
    if t > 0.9:
        ra = env(t - 0.9, dur - 0.9)
        card(d, (80, 890, W - 80, 1450), ra)
        put(d, (120, 926), "brief  ·  你早上真正会读的十行", F_Y_S, DIM, ra, bg=PANEL)
        brief = [
            ("WINDOW", "7h32m used · 27m left"),
            ("EVIDENCE", "85% of steps carry proof"),
            ("GATE", "GREEN · 5/5 proven"),
            ("RISK", "2 medium drift flags"),
            ("TREND", "improving · +68 pts"),
        ]
        y = 1000
        for k, v in brief:
            put(d, (125, y), k, F_MONO_S, CYAN, ra * 0.95, bg=PANEL)
            put(d, (345, y - 5), v, F_MONO, INK, ra, bg=PANEL)
            y += 88


def scene7(d, t, dur):
    a = env(t, dur, 0.5, 0.4)
    put(d, (W / 2, 680), "给你的 Agent 一个夜班。", F_H1, INK, a, anchor="ma")
    put(d, (W / 2, 840), "醒来读报告，不是读幻觉。", F_H2, DIM, env(t - 0.5, dur - 0.5), anchor="ma")
    if t > 1.0:
        ra = env(t - 1.0, dur - 1.0, 0.5, 0.3)
        put(d, (W / 2, 1080), "NIGHTSHIFT", ImageFont.truetype(MOB, 100), CYAN, ra, anchor="ma")
        put(d, (W / 2, 1220), REPO, F_MONO, DIM, ra, anchor="ma")
        put(d, (W / 2, 1300), "MIT · 零依赖 · 一个 skill + 一个 CLI", F_SMALL, FAINT, ra, anchor="ma")


SCENES = [
    (0.0, 3.8, scene1),
    (3.8, 9.0, scene2),
    (9.0, 14.2, scene3),
    (14.2, 19.8, scene4),
    (19.8, 24.4, scene5),
    (24.4, 29.2, scene6),
    (29.2, DUR, scene7),
]


# --------------------------------------------------------------------------- #

def frame_at(t: float) -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    for start, end, fn in SCENES:
        if start <= t < end:
            fn(d, t - start, end - start)
            break
    wordmark(d, 0.5)
    progress(d, t)
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
    stills = {int(total * f) for f in (0.12, 0.30, 0.48, 0.66, 0.80, 0.94)} if args.stills else set()
    for i in range(total):
        img = frame_at(i / FPS)
        if i in stills:
            p = ROOT / "docs" / "frames" / f"video-{i:05d}.png"
            p.parent.mkdir(exist_ok=True)
            img.save(p)
        proc.stdin.write(img.tobytes())
        if i % 120 == 0:
            print(f"  {i}/{total}", flush=True)
    proc.stdin.close()
    err = proc.stderr.read().decode("utf-8", "replace") if proc.stderr else ""
    code = proc.wait()
    if code != 0:
        print(err, file=sys.stderr)
        return code
    print(f"wrote {OUT}  ({OUT.stat().st_size / 1024 / 1024:.1f} MiB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
