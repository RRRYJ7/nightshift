"""Small, dependency-free helpers shared by the rest of NIGHTSHIFT."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Sequence

# --------------------------------------------------------------------------- #
# terminal colour
# --------------------------------------------------------------------------- #

_COLOR = True


def set_color(enabled: bool) -> None:
    """Turn ANSI colour on/off for the whole process."""
    global _COLOR
    _COLOR = bool(enabled)


def color_enabled() -> bool:
    return _COLOR


def c(code: str, text: str) -> str:
    """Wrap *text* in an ANSI SGR sequence when colour is enabled."""
    if not _COLOR:
        return text
    return f"\x1b[{code}m{text}\x1b[0m"


def dim(t: str) -> str:
    return c("2", t)


def bold(t: str) -> str:
    return c("1", t)


def red(t: str) -> str:
    return c("31", t)


def green(t: str) -> str:
    return c("32", t)


def yellow(t: str) -> str:
    return c("33", t)


def blue(t: str) -> str:
    return c("34", t)


def magenta(t: str) -> str:
    return c("35", t)


def cyan(t: str) -> str:
    return c("36", t)


def grey(t: str) -> str:
    return c("90", t)


def enable_windows_vt() -> None:
    """Best-effort: make the Windows console understand ANSI escapes."""
    if os.name != "nt":
        return
    try:  # pragma: no cover - platform specific
        import ctypes

        kernel32 = ctypes.windll.kernel32
        for handle in (-11, -12):  # stdout, stderr
            h = kernel32.GetStdHandle(handle)
            mode = ctypes.c_uint32()
            if kernel32.GetConsoleMode(h, ctypes.byref(mode)):
                kernel32.SetConsoleMode(h, mode.value | 0x0004)
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# text -> tokens (bilingual, no external NLP)
# --------------------------------------------------------------------------- #

_CJK = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+")
_LATIN = re.compile(r"[A-Za-z][A-Za-z0-9_.\-]{0,40}")

_STOP_EN = {
    "the", "a", "an", "and", "or", "but", "if", "then", "else", "for", "of", "to", "in", "on",
    "at", "by", "with", "is", "are", "was", "were", "be", "been", "being", "it", "its", "this",
    "that", "these", "those", "as", "from", "we", "i", "you", "he", "she", "they", "them", "our",
    "your", "my", "me", "us", "do", "does", "did", "done", "can", "could", "should", "would",
    "will", "may", "might", "must", "not", "no", "yes", "all", "any", "some", "one", "two", "into",
    "over", "under", "about", "than", "so", "up", "down", "out", "off", "just", "also", "very",
    "please", "need", "want", "make", "use", "using", "get", "got", "now", "new", "more",
}

_STOP_ZH = set("的了和与是在我你他她它们就都而及或一个这个那个之后之前然后把被给对从到很更最也还又才只么呢吧啊")


def tokenize(text: str) -> set[str]:
    """Return a language-agnostic bag of features.

    Latin words become lowercase tokens; CJK runs become character bigrams
    (single characters when the run is one glyph long).  Character bigrams are
    a cheap, dependency-free stand-in for Chinese word segmentation and they
    behave well for the only thing we need here: *is this step still about the
    same thing as the contract?*
    """
    if not text:
        return set()
    tokens: set[str] = set()
    for m in _LATIN.finditer(text):
        w = m.group(0).lower().strip(".-_")
        if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        if len(w) > 1 and w not in _STOP_EN:
            tokens.add(w)
    for run in _CJK.findall(text):
        if len(run) == 1:
            if run not in _STOP_ZH:
                tokens.add(run)
            continue
        for i in range(len(run) - 1):
            a, b = run[i], run[i + 1]
            if a in _STOP_ZH and b in _STOP_ZH:
                continue
            tokens.add(a + b)
    return tokens


def jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    inter = len(sa & sb)
    return inter / float(len(sa | sb))


def overlap(a: Iterable[str], b: Iterable[str]) -> float:
    """Share of *a* that also appears in *b* (asymmetric containment)."""
    sa, sb = set(a), set(b)
    if not sa:
        return 0.0
    return len(sa & sb) / float(len(sa))


# --------------------------------------------------------------------------- #
# time
# --------------------------------------------------------------------------- #

def now() -> datetime:
    return datetime.now().astimezone()


def iso(dt: datetime | None = None) -> str:
    return (dt or now()).isoformat(timespec="seconds")


def parse_iso(s: str) -> datetime:
    """Parse a timestamp from a log that may have been written by another tool.

    ``datetime.fromisoformat`` is strict: it rejects ``Z``, offsets without a
    colon and fractional seconds that are not 3 or 6 digits. Normalise first
    instead of failing on data we did not write.
    """
    if not isinstance(s, str) or not s.strip():
        raise ValueError(f"empty timestamp: {s!r}")
    text = s.strip()
    if text.endswith("Z") or text.endswith("z"):
        text = text[:-1] + "+00:00"
    m = re.search(r"([+-]\d{2})(\d{2})$", text)
    if m:
        text = text[: m.start()] + m.group(1) + ":" + m.group(2)
    m = re.search(r"\.(\d+)(?=[+-]|$)", text)
    if m:
        text = text[: m.start()] + "." + (m.group(1) + "000000")[:6] + text[m.end():]
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.astimezone()
    return dt


def parse_deadline(s: str, base: datetime | None = None) -> datetime:
    """Accept ``10:30``, ``2026-10-25 10:30``, ``2026-10-25T10:30`` or ISO with offset."""
    s = s.strip()
    base = base or now()

    def _bad(why: str) -> ValueError:
        return ValueError(f"cannot parse deadline {s!r}: {why} (try '2026-10-25 10:30' or '10:30')")

    m = re.fullmatch(r"(\d{1,2}):(\d{2})(?::(\d{2}))?", s)
    if m:
        hh, mm, ss = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
        if not (0 <= hh <= 23 and 0 <= mm <= 59 and 0 <= ss <= 59):
            raise _bad("time out of range")
        cand = base.replace(hour=hh, minute=mm, second=ss, microsecond=0)
        if cand <= base:
            cand += timedelta(days=1)
        return cand
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})[ T](\d{1,2}):(\d{2})(?::(\d{2}))?", s)
    if m:
        y, mo, d, hh, mm, ss = (int(x or 0) for x in m.groups())
        if not (1 <= mo <= 12 and 1 <= d <= 31 and 0 <= hh <= 23 and 0 <= mm <= 59 and 0 <= ss <= 59):
            raise _bad("date or time out of range")
        try:
            return base.replace(year=y, month=mo, day=d, hour=hh, minute=mm, second=ss, microsecond=0)
        except ValueError as exc:  # e.g. 2026-02-30
            raise _bad(str(exc))
    try:
        return parse_iso(s)
    except ValueError:
        raise _bad("unrecognised format")


def human_dur(seconds: float) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h{m:02d}m"
    if m:
        return f"{m}m{s:02d}s"
    return f"{s}s"


def human_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M")


def clock(dt: datetime) -> str:
    return dt.strftime("%H:%M")


# --------------------------------------------------------------------------- #
# hashing
# --------------------------------------------------------------------------- #

def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8", "replace"))


def sha256_file(path: Path | str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def digest(text: str) -> str:
    return "sha256:" + sha256_text(text)


def digest_bytes(b: bytes) -> str:
    return "sha256:" + sha256_bytes(b)


# --------------------------------------------------------------------------- #
# json / jsonl
# --------------------------------------------------------------------------- #

def read_json(path: Path | str, default: Any = None) -> Any:
    p = Path(path)
    if not p.exists():
        return default
    with open(p, "r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path | str, obj: Any, indent: int = 2) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=indent, sort_keys=False)
        fh.write("\n")
    os.replace(tmp, p)


def append_jsonl(path: Path | str, obj: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False) + "\n")


def read_jsonl(path: Path | str) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    out: list[dict] = []
    with open(p, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


# --------------------------------------------------------------------------- #
# display helpers
# --------------------------------------------------------------------------- #

def one_line(text: str, limit: int = 0) -> str:
    s = " ".join(str(text).split())
    if limit and len(s) > limit:
        s = s[: max(0, limit - 1)] + "…"
    return s


def pad(text: str, width: int) -> str:
    """Pad by *display* width (CJK counts as two columns)."""
    w = display_width(text)
    if w >= width:
        return text
    return text + " " * (width - w)


def display_width(text: str) -> int:
    import unicodedata

    total = 0
    for ch in text:
        total += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return total


def pct(x: float, digits: int = 0) -> str:
    return f"{x * 100:.{digits}f}%"


def plural(n: int, singular: str, plural_form: str | None = None) -> str:
    """'1 step', '3 steps', '1 criterion', '2 criteria'."""
    return f"{n} {singular if n == 1 else (plural_form or singular + 's')}"


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def terminal_width(default: int = 100) -> int:
    try:
        return max(40, min(160, os.get_terminal_size().columns))
    except OSError:
        return default


def safe_slug(text: str, limit: int = 60) -> str:
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", text).strip("-")
    return (s or "item")[:limit]


def monotonic() -> float:
    return time.monotonic()
