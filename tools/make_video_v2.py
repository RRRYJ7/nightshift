"""Render the vertical promo (1080x1920) with a mascot, in a night-city neon style.

    python tools/make_video_v2.py            # docs/nightshift-vertical.mp4
    python tools/make_video_v2.py --stills   # + docs/frames/v2-*.png

The pitch is "who is this for and why is it good", not "here is how the gate
works". The mascot is a small whale working the night shift; everything is drawn
with Pillow (no assets, no network), and the whole thing is piped straight into
ffmpeg so no frames touch the disk.
"""

from __future__ import annotations

import argparse
import math
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "nightshift-vertical.mp4"
REPO = "github.com/RRRYJ7/nightshift"

W, H = 1080, 1920
FPS = 30
DUR = 31.0

# palette
NIGHT = (7, 10, 24)
DEEP = (11, 17, 40)
INK = (240, 246, 255)
DIM = (150, 165, 190)
CYAN = (56, 224, 255)
TEAL = (45, 212, 191)
PINK = (255, 122, 162)
AMBER = (255, 190, 92)
RED = (255, 96, 110)
GREEN = (74, 222, 128)
VIOLET = (150, 120, 255)

YB = r"C:\Windows\Fonts\msyhbd.ttc"
YR = r"C:\Windows\Fonts\msyh.ttc"
MO = r"C:\Windows\Fonts\consola.ttf"
MOB = r"C:\Windows\Fonts\consolab.ttf"

F_MEGA = ImageFont.truetype(YB, 132)
F_H1 = ImageFont.truetype(YB, 96)
F_H2 = ImageFont.truetype(YB, 66)
F_BODY = ImageFont.truetype(YR, 44)
F_SMALL = ImageFont.truetype(YR, 32)
F_TINY = ImageFont.truetype(YR, 26)
F_MONO = ImageFont.truetype(MO, 34)
F_MONO_S = ImageFont.truetype(MO, 26)

_GLOW_CACHE: dict = {}


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def ease_out(x: float) -> float:
    return 1 - (1 - clamp01(x)) ** 3


def ease_in_out(x: float) -> float:
    x = clamp01(x)
    return 3 * x * x - 2 * x * x * x


def env(t: float, a: float, b: float, fin: float = 0.45, fout: float = 0.35) -> float:
    if t < a or t > b:
        return 0.0
    return min(clamp01((t - a) / fin), clamp01((b - t) / fout))


def blend(c1, c2, k: float):
    k = clamp01(k)
    return tuple(int(a + (b - a) * k) for a, b in zip(c1, c2))


def glow(size: int, color, strength: float = 1.0) -> Image.Image:
    """A cached radial glow sprite (RGBA)."""
    key = (size, color, round(strength, 2))
    if key in _GLOW_CACHE:
        return _GLOW_CACHE[key]
    s = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(s)
    steps = 24
    for i in range(steps, 0, -1):
        r = size / 2 * i / steps
        a = int(255 * (1 - i / steps) ** 2 * strength)
        d.ellipse([size / 2 - r, size / 2 - r, size / 2 + r, size / 2 + r], fill=a)
    s = s.filter(ImageFilter.GaussianBlur(size / 12))
    sprite = Image.new("RGBA", (size, size), (*color, 0))
    sprite.putalpha(s)
    _GLOW_CACHE[key] = sprite
    return sprite


def add_glow(img: Image.Image, cx: float, cy: float, radius: int, color, strength=1.0):
    g = glow(radius * 2, color, strength)
    img.alpha_composite(g, (int(cx - radius), int(cy - radius)))


def put(d, xy, text, font, color, alpha=1.0, anchor="la", shadow=None):
    if alpha <= 0.01:
        return
    a = int(255 * clamp01(alpha))
    if shadow:
        d.text((xy[0] + 3, xy[1] + 4), text, font=font, fill=(0, 0, 0, int(a * 0.55)), anchor=anchor)
    d.text(xy, text, font=font, fill=(*color, a), anchor=anchor)


def put_glow(img, xy, text, font, color, alpha=1.0, anchor="la", radius=26):
    """Text with a soft neon halo behind it."""
    if alpha <= 0.02:
        return
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.text(xy, text, font=font, fill=(*color, int(200 * alpha)), anchor=anchor)
    halo = layer.filter(ImageFilter.GaussianBlur(radius))
    img.alpha_composite(halo)
    img.alpha_composite(halo)
    d2 = ImageDraw.Draw(img)
    d2.text(xy, text, font=font, fill=(*color, int(255 * alpha)), anchor=anchor)


def vignette(img: Image.Image, strength: int = 110):
    v = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(v)
    d.ellipse([-W * 0.35, -H * 0.25, W * 1.35, H * 1.25], fill=255)
    v = v.filter(ImageFilter.GaussianBlur(220))
    dark = Image.new("RGBA", (W, H), (0, 0, 0, strength))
    dark.putalpha(Image.eval(v, lambda p: int((255 - p) * strength / 255)))
    img.alpha_composite(dark)


def particles(img: Image.Image, t: float, n: int = 46, color=CYAN, alpha=1.0):
    d = ImageDraw.Draw(img)
    for i in range(n):
        seed = i * 7919
        px = (seed * 37 + t * (14 + (i % 5) * 9)) % (W + 200) - 100
        py = (seed * 53 - t * (18 + (i % 7) * 7)) % (H + 200) - 100
        r = 1.2 + (i % 4) * 0.9
        a = int((40 + (i % 5) * 20) * alpha)
        d.ellipse([px - r, py - r, px + r, py + r], fill=(*color, a))


def speed_lines(img: Image.Image, cx: float, cy: float, t: float, alpha=1.0):
    d = ImageDraw.Draw(img)
    for i in range(28):
        ang = i * (math.pi * 2 / 28) + t * 0.6
        r0 = 320 + (i % 5) * 40
        r1 = r0 + 220 + 120 * math.sin(t * 3 + i)
        x0, y0 = cx + math.cos(ang) * r0, cy + math.sin(ang) * r0
        x1, y1 = cx + math.cos(ang) * r1, cy + math.sin(ang) * r1
        d.line([x0, y0, x1, y1], fill=(*CYAN, int(90 * alpha)), width=2)


# --------------------------------------------------------------------------- #
# the mascot: a small whale on the night shift
# --------------------------------------------------------------------------- #

def pop_font(path: str, size: int, t: float, dur: float = 0.45) -> ImageFont.FreeTypeFont:
    """Font size that overshoots then settles: the cheapest 'punch-in' there is."""
    k = 1.0 + 0.22 * (1 - ease_out(clamp01(t / dur)))
    return ImageFont.truetype(path, max(8, int(size * k)))


def sparkles(img: Image.Image, cx: float, cy: float, r: float, t: float, alpha=1.0, n=5):
    d = ImageDraw.Draw(img)
    for i in range(n):
        a = t * 1.6 + i * (math.pi * 2 / n)
        px, py = cx + math.cos(a) * r, cy + math.sin(a) * r * 0.7
        s = 3 + 3 * (0.5 + 0.5 * math.sin(t * 6 + i))
        col = (255, 255, 255, int(150 * alpha)) if i % 2 else (*CYAN, int(160 * alpha))
        d.line([px - s, py, px + s, py], fill=col, width=2)
        d.line([px, py - s, px, py + s], fill=col, width=2)


def whale(img: Image.Image, cx: float, cy: float, scale: float, t: float,
          mood: str = "work", alpha: float = 1.0, sleeping: bool = False):
    """A chibi whale, front-facing: big head, two big eyes, blush, tiny body.

    Drawn at 2x into its own layer and downscaled, so the curves stay clean.
    """
    if alpha <= 0.02:
        return
    s = max(0.2, scale)
    SS = 2
    VW, VH = 1000, 820
    lw, lh = int(VW * s * SS / 2), int(VH * s * SS / 2)
    layer = Image.new("RGBA", (lw, lh), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    k = lw / VW

    def X(v):
        return v * k

    def Y(v):
        return v * k

    # squash & stretch
    bob = math.sin(t * 2.4) * 14
    squash = 1.0 + math.sin(t * 2.4 + math.pi / 2) * 0.035

    def P(pts):
        return [(X(x), Y(cy0 + (y - cy0) * squash + bob)) for x, y in pts]

    cy0 = 470
    body_c = (400, 470)

    # tail (behind the body, right side)
    flap = math.sin(t * 3.0) * 12
    d.polygon(P([(860, 470), (975, 360 + flap), (975, 590 - flap)]),
              fill=(*blend(TEAL, DEEP, 0.34), 255))

    # body
    d.ellipse([X(560), Y(430 + bob), X(930), Y(715 + bob)], fill=(*blend(TEAL, DEEP, 0.18), 255))
    # head
    head = [X(200), Y(215 + bob), X(620), Y(635 + bob)]
    d.ellipse(head, fill=(*TEAL, 255))
    # rim light
    d.arc(head, start=190, end=290, fill=(*CYAN, 170), width=max(3, int(X(10))))
    # belly patch
    d.ellipse([X(610), Y(560 + bob), X(880), Y(700 + bob)], fill=(*blend(TEAL, (255, 255, 255), 0.50), 255))

    # eyes
    er = X(66)
    blink = 1.0
    if sleeping or math.sin(t * 1.3) > 0.978:
        blink = 0.08
    for ex in (X(340), X(500)):
        ey = Y(455 + bob)
        if blink > 0.5:
            d.ellipse([ex - er, ey - er * blink, ex + er, ey + er * blink], fill=(*INK, 255))
            pr = er * 0.66
            d.ellipse([ex - pr, ey - pr, ex + pr, ey + pr], fill=(22, 28, 46, 255))
            d.ellipse([ex - pr * 0.62, ey - pr * 0.86, ex + pr * 0.06, ey - pr * 0.12],
                      fill=(255, 255, 255, 255))
            d.ellipse([ex + pr * 0.18, ey + pr * 0.18, ex + pr * 0.5, ey + pr * 0.52],
                      fill=(255, 255, 255, 190))
        else:
            d.arc([ex - er, ey - er * 0.5, ex + er, ey + er * 0.5], 200, 340,
                  fill=(22, 28, 46, 255), width=max(3, int(X(10))))

    # tiny mouth
    my = Y(575 + bob)
    d.arc([X(385), my - X(24), X(455), my + X(24)], 20, 160, fill=(22, 28, 46, 235), width=max(3, int(X(9))))

    # night cap
    d.polygon(P([(262, 268), (410, 158), (548, 268)]), fill=(*AMBER, 252))
    d.ellipse([X(382), Y(134 + bob), X(440), Y(192 + bob)], fill=(*blend(AMBER, (255, 255, 255), 0.55), 255))

    layer = layer.resize((lw // SS, lh // SS), Image.LANCZOS)
    if alpha < 0.99:
        a = layer.getchannel("A").point(lambda p: int(p * alpha))
        layer.putalpha(a)
    img.alpha_composite(layer, (int(cx - lw / (2 * SS)), int(cy - lh / (2 * SS))))

    # soft cheeks + aura, on top of the composited layer
    if mood == "work":
        add_glow(img, cx, cy + 150 * s, int(150 * s), CYAN, 0.30)
        sparkles(img, cx, cy - 40 * s, 190 * s, t, 0.8 * alpha)
    if sleeping:
        put(ImageDraw.Draw(img), (cx + 150 * s, cy - 190 * s), "z z Z", F_H2, DIM, 0.9 * alpha)


def sky(img: Image.Image, t: float, warm: float = 0.0):
    d = ImageDraw.Draw(img)
    top = blend(DEEP, (28, 20, 48), warm * 0.6)
    bot = blend(NIGHT, (120, 70, 60), warm * 0.8)
    for y in range(0, H, 6):
        k = y / H
        d.rectangle([0, y, W, y + 6], fill=blend(top, bot, k))
    # horizon glow
    add_glow(img, W * 0.5, H * 0.92, 520, blend(CYAN, AMBER, warm), 0.55)
    # grid floor
    for i in range(1, 9):
        y = H * 0.9 + i * 26
        if y < H:
            d.line([0, y, W, y], fill=(*CYAN, max(0, 40 - i * 4)))


def scene1(img, d, lt, dur):
    t = lt
    sky(img, t)
    particles(img, t)
    a = env(t, 0, dur)
    # moon
    add_glow(img, 820, 300, 200, (200, 220, 255), 0.45)
    d.ellipse([770, 250, 870, 350], fill=(226, 236, 255, 230))

    put_glow(img, (W / 2, 470), "02:41", ImageFont.truetype(MOB, 96), CYAN, a, anchor="ma")
    put(d, (W / 2, 600), "你睡了。", pop_font(YB, 96, t - 0.5), INK, env(t, 0.5, dur), anchor="ma", shadow=True)
    put(d, (W / 2, 730), "它还在干。", F_H2, DIM, env(t, 1.2, dur), anchor="ma")

    whale(img, W / 2, 1250, 1.28, t, mood="work", alpha=env(t, 0.2, dur))

    if t > 1.8:
        put(d, (W / 2, 1560), "一整夜，没人看着", F_SMALL, DIM, env(t, 1.8, dur) * 0.9, anchor="ma")


def scene2(img, d, lt, dur):
    t = lt
    sky(img, t, warm=0.1)
    particles(img, t, color=AMBER)
    a = env(t, 0, dur)

    put(d, (W / 2, 300), "早上七点", F_SMALL, DIM, a, anchor="ma")

    # chat bubble
    if t > 0.2:
        pop = ease_out((t - 0.2) / 0.4)
        bw, bh = 760, 190
        bx0, by0 = (W - bw) / 2, 400
        d.rounded_rectangle([bx0, by0, bx0 + bw, by0 + bh], radius=36,
                            fill=(30, 38, 58, int(240 * pop)), outline=(*CYAN, int(180 * pop)), width=3)
        put(d, (bx0 + 44, by0 + 34), "agent", F_TINY, DIM, pop)
        put(d, (bx0 + 44, by0 + 78), "搞定了！", F_H2, INK, pop)

    if t > 1.6:
        ga = env(t, 1.6, dur, 0.3, 0.2)
        # glitch the bubble
        for i in range(3):
            off = (i - 1) * 7
            d.rounded_rectangle([bx0 + off, by0 + i * 4, bx0 + bw + off, by0 + bh + i * 4], radius=36,
                                outline=(*RED, int(70 * ga)), width=2)
        put_glow(img, (W / 2, 690), "真的吗？", pop_font(YB, 96, t - 1.6), RED, ga, anchor="ma")

    if t > 2.6:
        chips = [("完成没定义", RED), ("证据没留下", RED), ("早就跑偏了", AMBER)]
        for i, (txt, col) in enumerate(chips):
            ca = env(t, 2.6 + i * 0.3, dur, 0.3, 0.2)
            y = 880 + i * 110
            d.rounded_rectangle([190, y, W - 190, y + 82], radius=41,
                                fill=(*col, int(28 * ca)), outline=(*col, int(200 * ca)), width=2)
            put(d, (W / 2, y + 16), txt, F_BODY, col, ca, anchor="ma")

    whale(img, W / 2, 1520, 0.85, t, mood="sleep", alpha=env(t, 0.6, dur) * 0.95, sleeping=True)


def scene3(img, d, lt, dur):
    t = lt
    sky(img, t)
    speed_lines(img, W / 2, H * 0.5, t, 0.5)
    particles(img, t, color=TEAL)

    put(d, (W / 2, 220), "所以它先写下", F_SMALL, DIM, env(t, 0, dur), anchor="ma")
    put_glow(img, (W / 2, 300), "什么算完成", F_H1, INK, env(t, 0.1, dur), anchor="ma")

    cards = [
        ("01", "飞行计划", "3~6 条完成标准\n每条都能被命令判真假", CYAN),
        ("02", "证据收据", "每条输出带 sha256\n事后补的收据不算", TEAL),
        ("03", "证据门", "全绿才叫完成\n红了就写红", GREEN),
    ]
    for i, (num, title, body, col) in enumerate(cards):
        ca = env(t, 0.5 + i * 0.5, dur, 0.45, 0.25)
        slide = (1 - ease_out((t - 0.5 - i * 0.5) / 0.5)) * 120
        y = 470 + i * 330
        d.rounded_rectangle([90 + slide, y, W - 90 + slide, y + 280], radius=32,
                            fill=(*blend(DEEP, col, 0.10), int(235 * ca)),
                            outline=(*col, int(200 * ca)), width=3)
        put(d, (140 + slide, y + 34), num, F_MONO, col, ca)
        put(d, (240 + slide, y + 26), title, F_H2, INK, ca)
        for j, line in enumerate(body.split("\n")):
            put(d, (240 + slide, y + 120 + j * 56), line, F_SMALL, DIM, ca)

    whale(img, W - 150, 1500, 0.5, t, mood="work", alpha=env(t, 1.2, dur) * 0.9)


def scene4(img, d, lt, dur):
    t = lt
    sky(img, t, warm=min(1.0, t / 2.0))
    particles(img, t, color=AMBER, alpha=0.8)
    a = env(t, 0, dur)

    put(d, (W / 2, 210), "06:30", F_SMALL, DIM, a, anchor="ma")
    put_glow(img, (W / 2, 280), "你醒来。", F_H1, INK, a, anchor="ma")

    # report scroll
    if t > 0.5:
        ra = env(t, 0.5, dur, 0.5, 0.25)
        top = 430 + (1 - ease_out((t - 0.5) / 0.7)) * 60
        d.rounded_rectangle([90, top, W - 90, top + 650], radius=36,
                            fill=(14, 20, 34, int(245 * ra)), outline=(*CYAN, int(150 * ra)), width=2)
        put(d, (130, top + 34), "flight report", F_MONO_S, DIM, ra)
        put(d, (130, top + 80), "DONE & PROVEN", ImageFont.truetype(MOB, 54), GREEN, ra)
        rows = [
            ("GATE", "5/5 条标准，全部带证据", GREEN),
            ("EVIDENCE", "每一步都有收据", CYAN),
            ("RISK", "两次漂移，当场抓回", AMBER),
            ("TREND", "还在往上走", TEAL),
        ]
        for i, (k, v, col) in enumerate(rows):
            la = env(t, 0.9 + i * 0.25, dur, 0.3, 0.2)
            y = top + 190 + i * 96
            put(d, (130, y), k, F_MONO_S, col, la)
            put(d, (330, y - 6), v, F_SMALL, INK, la)
        # stamp
        if t > 2.0:
            sa = env(t, 2.0, dur, 0.25, 0.2)
            d.rounded_rectangle([W - 330, top + 150, W - 110, top + 240], radius=16,
                                outline=(*GREEN, int(220 * sa)), width=4)
            put(d, (W - 220, top + 172), "已证明 5/5", ImageFont.truetype(YB, 40), GREEN, sa, anchor="ma")

    whale(img, 190, 1450, 0.62, t, mood="wave", alpha=env(t, 0.3, dur))


def scene5(img, d, lt, dur):
    t = lt
    sky(img, t)
    speed_lines(img, W / 2, H * 0.55, t * 0.6, 0.18)
    particles(img, t, color=VIOLET)

    put_glow(img, (W / 2, 230), "不只是程序员", F_H1, INK, env(t, 0, dur), anchor="ma")
    put(d, (W / 2, 372), "只要“完成”能被一条命令判真假", F_SMALL, DIM, env(t, 0.4, dur), anchor="ma")

    people = [
        ("程序员", "测试全绿 · 能构建", CYAN),
        ("科研", "流水线跑完 · 结果文件在", TEAL),
        ("数据分析", "行数对 · 无重复 · 日期对", VIOLET),
        ("写作 / 设计", "PDF 能渲染 · 九节齐全", PINK),
        ("运营 / 产品", "报表能打开 · 数据对得上", AMBER),
        ("学生", "知道它昨晚到底干了什么", GREEN),
    ]
    for i, (who, what, col) in enumerate(people):
        ca = env(t, 0.5 + i * 0.28, dur, 0.35, 0.2)
        col_i, row = i % 2, i // 2
        x = 80 + col_i * 470
        y = 470 + row * 240
        d.rounded_rectangle([x, y, x + 440, y + 200], radius=28,
                            fill=(*blend(DEEP, col, 0.12), int(235 * ca)),
                            outline=(*col, int(190 * ca)), width=2)
        put(d, (x + 34, y + 30), who, F_H2, col, ca)
        put(d, (x + 34, y + 126), what, F_TINY, DIM, ca)

        whale(img, W / 2, 1700, 0.5, t, mood="work", alpha=env(t, 2.2, dur) * 0.85) if i == 5 else None


def scene6(img, d, lt, dur):
    t = lt
    sky(img, t, warm=0.15)
    particles(img, t, color=CYAN)
    add_glow(img, W / 2, 700, 420, CYAN, 0.5)
    a = env(t, 0, dur, 0.5, 0.4)

    put_glow(img, (W / 2, 520), "给你的 Agent", pop_font(YB, 132, t), INK, a, anchor="ma")
    put_glow(img, (W / 2, 680), "一个夜班", pop_font(YB, 132, t - 0.12), CYAN, a, anchor="ma")
    put(d, (W / 2, 850), "醒来读报告，不是读幻觉", F_BODY, DIM, env(t, 0.5, dur), anchor="ma")

    whale(img, W / 2, 1150, 1.0, t, mood="wave", alpha=env(t, 0.3, dur))

    if t > 1.2:
        ra = env(t, 1.2, dur, 0.5, 0.3)
        put(d, (W / 2, 1450), REPO, F_MONO, CYAN, ra, anchor="ma")
        put(d, (W / 2, 1520), "开源 · 零依赖 · 一个 skill + 一个 CLI", F_SMALL, DIM, ra, anchor="ma")


SCENES = [
    (0.0, 4.2, scene1),
    (4.2, 8.4, scene2),
    (8.4, 14.0, scene3),
    (14.0, 19.6, scene4),
    (19.6, 25.6, scene5),
    (25.6, DUR, scene6),
]


def frame_at(t: float) -> Image.Image:
    img = Image.new("RGBA", (W, H), (*NIGHT, 255))
    d = ImageDraw.Draw(img)
    for start, end, fn in SCENES:
        if start <= t < end:
            fn(img, d, t - start, end - start)
            break
    vignette(img)
    # progress bar
    d = ImageDraw.Draw(img)
    d.rectangle([0, H - 6, W, H], fill=(255, 255, 255, 26))
    d.rectangle([0, H - 6, int(W * clamp01(t / DUR)), H], fill=(*CYAN, 200))
    return img.convert("RGB")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stills", action="store_true")
    ap.add_argument("--frame", type=float, default=None, help="render one frame at this many seconds")
    args = ap.parse_args()

    if args.frame is not None:
        p = ROOT / "docs" / "frames" / f"v2-single-{args.frame:05.2f}.png"
        p.parent.mkdir(exist_ok=True)
        frame_at(args.frame).save(p)
        print(f"wrote {p}")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    total = int(DUR * FPS)
    print(f"rendering {total} frames at {W}x{H} ...")
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "19",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(OUT),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    assert proc.stdin is not None
    stills = {int(total * f) for f in (0.06, 0.20, 0.34, 0.50, 0.68, 0.84, 0.96)} if args.stills else set()
    for i in range(total):
        img = frame_at(i / FPS)
        if i in stills:
            p = ROOT / "docs" / "frames" / f"v2-{i:05d}.png"
            p.parent.mkdir(exist_ok=True)
            img.save(p)
        proc.stdin.write(img.tobytes())
        if i % 120 == 0:
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
