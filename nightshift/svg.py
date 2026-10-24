"""Tiny SVG chart primitives.

The flight report must render offline, inside a single file, on a machine with
no JavaScript and no CDN.  So: hand-rolled SVG, no libraries.
"""

from __future__ import annotations

import html
import math
from typing import Iterable, Sequence

# palette — readable on light and dark backgrounds
CYAN = "#0891b2"
CYAN_SOFT = "#67e8f9"
GREEN = "#059669"
AMBER = "#d97706"
RED = "#dc2626"
GREY = "#94a3b8"
INK = "#0f172a"
PAPER = "#ffffff"
GRID = "#e2e8f0"


def esc(text: object) -> str:
    return html.escape(str(text), quote=True)


def _pts(values: Sequence[float], w: float, h: float, pad: float = 6.0,
         lo: float | None = None, hi: float | None = None) -> list[tuple[float, float]]:
    if not values:
        return []
    lo = min(values) if lo is None else lo
    hi = max(values) if hi is None else hi
    if hi - lo < 1e-9:
        hi = lo + 1.0
    n = len(values)
    span_x = w - 2 * pad
    span_y = h - 2 * pad
    out = []
    for i, v in enumerate(values):
        x = pad + (span_x * i / (n - 1)) if n > 1 else pad + span_x / 2
        y = pad + span_y * (1.0 - (v - lo) / (hi - lo))
        out.append((round(x, 2), round(y, 2)))
    return out


def line_chart(
    values: Sequence[float],
    width: int = 520,
    height: int = 120,
    color: str = CYAN,
    fill: bool = True,
    lo: float | None = None,
    hi: float | None = None,
) -> str:
    if not values:
        return f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}"></svg>'
    pts = _pts(values, width, height, lo=lo, hi=hi)
    d = " ".join(f"{'M' if i == 0 else 'L'}{x},{y}" for i, (x, y) in enumerate(pts))
    area = ""
    if fill:
        area = (
            f'<path d="{d} L{pts[-1][0]},{height - 4} L{pts[0][0]},{height - 4} Z" '
            f'fill="{color}" fill-opacity="0.10" stroke="none"/>'
        )
    dots = "".join(
        f'<circle cx="{x}" cy="{y}" r="2.4" fill="{color}"/>' for x, y in pts[-40:]
    )
    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" '
        f'preserveAspectRatio="none" role="img">'
        f'{area}<path d="{d}" fill="none" stroke="{color}" stroke-width="2" '
        f'stroke-linejoin="round" stroke-linecap="round"/>{dots}</svg>'
    )


def bar_chart(
    pairs: Sequence[tuple[str, float]],
    width: int = 520,
    height: int = 120,
    color: str = CYAN,
) -> str:
    if not pairs:
        return f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}"></svg>'
    n = len(pairs)
    top = max(v for _, v in pairs) or 1.0
    pad_b = 18
    slot = width / n
    bw = max(3.0, slot * 0.55)
    bars = []
    for i, (label, v) in enumerate(pairs):
        bh = (height - pad_b - 6) * (v / top)
        x = i * slot + (slot - bw) / 2
        y = height - pad_b - bh
        bars.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="2" '
            f'fill="{color}" fill-opacity="0.85"><title>{esc(label)}: {v}</title></rect>'
        )
        if n <= 14:
            bars.append(
                f'<text x="{x + bw / 2:.1f}" y="{height - 5}" font-size="9" fill="{GREY}" '
                f'text-anchor="middle">{esc(label)}</text>'
            )
    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" role="img">'
        + "".join(bars)
        + "</svg>"
    )


def ring(ratio: float, size: int = 84, stroke: int = 9, color: str = CYAN) -> str:
    ratio = max(0.0, min(1.0, ratio))
    r = (size - stroke) / 2
    circ = 2 * math.pi * r
    dash = circ * ratio
    return (
        f'<svg viewBox="0 0 {size} {size}" width="{size}" height="{size}" role="img">'
        f'<circle cx="{size / 2}" cy="{size / 2}" r="{r}" fill="none" stroke="{GRID}" stroke-width="{stroke}"/>'
        f'<circle cx="{size / 2}" cy="{size / 2}" r="{r}" fill="none" stroke="{color}" stroke-width="{stroke}" '
        f'stroke-linecap="round" stroke-dasharray="{dash:.1f} {circ:.1f}" '
        f'transform="rotate(-90 {size / 2} {size / 2})"/>'
        f'<text x="{size / 2}" y="{size / 2 + 5}" text-anchor="middle" font-size="17" '
        f'font-weight="700" fill="{INK}">{ratio * 100:.0f}%</text>'
        f"</svg>"
    )


_KIND_STYLE = {
    "step": (INK, 3.0),
    "check": (GREEN, 4.0),
    "tick": (CYAN, 4.0),
    "note": (GREY, 2.0),
    "init": (GREY, 2.0),
    "gate": (AMBER, 4.0),
}


def timeline(
    events: Sequence[dict],
    findings: Sequence[dict] = (),
    width: int = 900,
    height: int = 132,
) -> str:
    """One horizontal strip: every event a tick, checks as diamonds, flags as red pins."""
    if not events:
        return f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}"></svg>'

    from . import util  # local import keeps this module import-light

    times = []
    for ev in events:
        try:
            times.append(util.parse_iso(ev.get("ts", "")))
        except Exception:
            times.append(util.now())
    t0, t1 = times[0], times[-1]
    span = max(1.0, (t1 - t0).total_seconds())
    base_y = height - 24

    def x_of(moment) -> float:
        return 8 + (width - 16) * max(0.0, min(1.0, (moment - t0).total_seconds() / span))

    parts = [
        f'<line x1="8" y1="{base_y}" x2="{width - 8}" y2="{base_y}" stroke="{GRID}" stroke-width="2"/>'
    ]

    # hour grid, capped: a log with a bogus timestamp years away must not emit
    # one node per hour.
    from datetime import timedelta as _td

    span_hours = max(1.0, span / 3600.0)
    step_hours = max(1, int(span_hours // 12) or 1)
    cursor = t0.replace(minute=0, second=0, microsecond=0)
    guard = 0
    while cursor <= t1 and guard < 60:
        if cursor >= t0:
            x = x_of(cursor)
            parts.append(
                f'<line x1="{x:.1f}" y1="{base_y - 46}" x2="{x:.1f}" y2="{base_y}" '
                f'stroke="{GRID}" stroke-width="1" stroke-dasharray="2 4"/>'
                f'<text x="{x:.1f}" y="{height - 7}" font-size="10" fill="{GREY}" '
                f'text-anchor="middle">{cursor.strftime("%H:%M")}</text>'
            )
        cursor += _td(hours=step_hours)
        guard += 1

    for ev, t in zip(events, times):
        x = x_of(t)
        kind = ev.get("kind", "step")
        if kind == "check":
            y = base_y - 22
            parts.append(
                f'<rect x="{x - 4:.1f}" y="{y - 4:.1f}" width="8" height="8" fill="{GREEN}" '
                f'transform="rotate(45 {x:.1f} {y:.1f})"><title>check {esc(ev.get("intent", ""))}</title></rect>'
            )
            parts.append(f'<line x1="{x:.1f}" y1="{y + 6:.1f}" x2="{x:.1f}" y2="{base_y}" stroke="{GREEN}" stroke-opacity="0.35"/>')
        elif kind == "tick":
            y = base_y - 30
            parts.append(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{CYAN}"><title>checkpoint {esc(ev.get("intent", ""))}</title></circle>'
            )
            parts.append(f'<line x1="{x:.1f}" y1="{y + 5:.1f}" x2="{x:.1f}" y2="{base_y}" stroke="{CYAN}" stroke-opacity="0.3"/>')
        elif kind == "init":
            parts.append(f'<line x1="{x:.1f}" y1="{base_y - 10}" x2="{x:.1f}" y2="{base_y}" stroke="{GREY}" stroke-width="2"/>')
        else:
            h = 10 if ev.get("evidence") else 5
            parts.append(
                f'<line x1="{x:.1f}" y1="{base_y}" x2="{x:.1f}" y2="{base_y - h:.1f}" '
                f'stroke="{INK}" stroke-width="1.6" stroke-opacity="0.45"><title>{esc(util.one_line(ev.get("intent", ""), 60))}</title></line>'
            )

    for f in findings:
        try:
            t = util.parse_iso(f.get("at", "") or events[-1].get("ts", ""))
        except Exception:
            t = t1
        x = x_of(t)
        col = RED if f.get("severity") == "high" else AMBER
        parts.append(
            f'<polygon points="{x:.1f},{base_y - 44} {x - 5:.1f},{base_y - 54} {x + 5:.1f},{base_y - 54}" '
            f'fill="{col}"><title>{esc(f.get("title", ""))}</title></polygon>'
            f'<line x1="{x:.1f}" y1="{base_y - 44}" x2="{x:.1f}" y2="{base_y - 34}" stroke="{col}" stroke-width="1"/>'
        )

    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" role="img">'
        + "".join(parts)
        + "</svg>"
    )
