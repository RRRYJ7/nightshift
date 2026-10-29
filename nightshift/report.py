"""Render the flight report — the thing a human reads at 10:30 with coffee.

One self-contained HTML file: no JS, no CDN, no fonts to download, printable.
"""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any, Sequence

from . import __version__, svg, util

CSS = """
:root{
  --ink:#0f172a; --muted:#64748b; --line:#e2e8f0; --paper:#ffffff; --wash:#f8fafc;
  --cyan:#0891b2; --green:#059669; --amber:#d97706; --red:#dc2626;
}
*{box-sizing:border-box}
body{margin:0;background:var(--wash);color:var(--ink);overflow-x:hidden;
  font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:1000px;margin:0 auto;padding:32px 20px 64px}
header{border-radius:18px;padding:26px 28px;background:linear-gradient(135deg,#0f172a 0%,#164e63 100%);color:#e2e8f0}
header h1{margin:0 0 4px;font-size:20px;letter-spacing:.14em;text-transform:uppercase;color:#67e8f9;font-weight:700}
header .goal{font-size:22px;line-height:1.35;font-weight:650;color:#fff;margin:6px 0 14px}
header .meta{font-size:12.5px;color:#94a3b8;display:flex;gap:18px;flex-wrap:wrap}
.badge{display:inline-block;padding:4px 12px;border-radius:999px;font-size:12px;font-weight:700;letter-spacing:.06em}
.badge.good{background:#064e3b;color:#6ee7b7;border:1px solid #059669}
.badge.warn{background:#451a03;color:#fcd34d;border:1px solid #d97706}
.badge.bad{background:#450a0a;color:#fca5a5;border:1px solid #dc2626}
section{margin-top:26px}
h2{font-size:13px;letter-spacing:.16em;text-transform:uppercase;color:var(--muted);margin:0 0 10px;font-weight:700}
.card{background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:18px 20px;overflow-x:auto}
pre.brief{margin:0;font:13px/1.75 ui-monospace,SFMono-Regular,Consolas,"Cascadia Mono",monospace;
  white-space:pre-wrap;overflow-wrap:anywhere;color:#0f172a}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px}
.stat{background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:14px 16px}
.stat .k{font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted)}
.stat .v{font-size:26px;font-weight:750;margin-top:2px}
.stat .s{font-size:12px;color:var(--muted)}
table{width:100%;border-collapse:collapse;table-layout:fixed;font-size:13.5px}
img,svg{max-width:100%}
th{text-align:left;font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);
  border-bottom:1px solid var(--line);padding:8px 10px;font-weight:600}
td{border-bottom:1px solid var(--line);padding:10px;vertical-align:top;overflow-wrap:anywhere}
tr:last-child td{border-bottom:none}
code,.mono{font-family:ui-monospace,SFMono-Regular,Consolas,"Cascadia Mono",monospace;font-size:12.5px}
.ok{color:var(--green);font-weight:700}
.no{color:var(--red);font-weight:700}
.pill{display:inline-block;padding:1px 8px;border-radius:999px;font-size:11px;font-weight:700}
.pill.high{background:#fee2e2;color:#991b1b}
.pill.medium{background:#fef3c7;color:#92400e}
.pill.low{background:#e0f2fe;color:#075985}
.finding{border-left:3px solid var(--amber);padding:8px 0 8px 14px;margin:10px 0}
.finding.high{border-left-color:var(--red)}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media(max-width:760px){.grid2{grid-template-columns:1fr}}
.empty{color:var(--muted);font-style:italic}
@media print{body{background:#fff}.wrap{max-width:none}section{break-inside:avoid}}
footer{margin-top:34px;font-size:12px;color:var(--muted);text-align:center;line-height:1.9}
.tag{font-size:11px;color:var(--muted);border:1px solid var(--line);border-radius:6px;padding:1px 6px}
"""


def _e(x: object) -> str:
    return html.escape(str(x), quote=True)


def _short_digest(d: str) -> str:
    return (d or "").replace("sha256:", "")[:12]


def _when(ts: str) -> str:
    """ISO timestamp -> 'Oct 24 · 23:27' for humans."""
    if not ts:
        return ""
    try:
        dt = util.parse_iso(ts)
        return dt.strftime("%b %d · %H:%M")
    except Exception:
        return ts


def model(analysis: dict[str, Any], project: str = "") -> dict[str, Any]:
    """Flatten the analysis into a render-ready dictionary."""
    contract = analysis["contract"]
    stats = analysis["stats"]
    g = analysis["gate"]
    findings = [f.as_dict() if hasattr(f, "as_dict") else dict(f) for f in analysis["findings"]]
    conv = analysis["convergence"]
    window = ""
    if stats.get("deadline") and stats.get("started_at"):
        try:
            window = "%s → %s" % (util.clock(util.parse_iso(stats["started_at"])),
                                  util.clock(util.parse_iso(stats["deadline"])))
        except (ValueError, TypeError):
            window = ""
    return {
        "project": project or "night shift",
        "goal": contract.get("goal", ""),
        "window": window,
        "started": stats["started_at"],
        "deadline": stats["deadline"],
        "verdict": analysis["verdict"],
        "brief": analysis["brief"],
        "stats": stats,
        "gate": g.as_dict(),
        "findings": findings,
        "convergence": conv,
        "non_goals": contract.get("non_goals") or [],
        "risks": contract.get("risks") or [],
        "events": analysis["events"],
        "hourly": analysis["hourly"],
        "targets": analysis.get("targets", []),
        "changes": analysis.get("changes", {}),
        "coverage": analysis["coverage_series"],
        "generated": util.iso(),
    }


# --------------------------------------------------------------------------- #
# HTML
# --------------------------------------------------------------------------- #

def render_html(m: dict[str, Any]) -> str:
    st = m["stats"]
    g = m["gate"]
    v = m["verdict"]
    findings = m["findings"]
    conv = m["convergence"]

    stats_cards = [
        ("window used", util.human_dur(st["wall_s"]),
         "of " + util.human_dur(st["wall_s"] + st["remaining_s"]) if st["remaining_s"] and st["remaining_s"] > 0 else "no deadline"),
        ("steps", str(st["steps"]), f"{st['checks']} checks · {st['ticks']} checkpoints"),
        ("evidence coverage", util.pct(st["coverage"]),
         f"{st['proven_steps']}/{st['steps']} steps carry proof"),
        ("criteria proven", f"{st['criteria_passed']}/{st['criteria']}",
         "gate green" if g["ok"] else "gate red"),
    ]
    cards_html = "".join(
        f'<div class="stat"><div class="k">{_e(k)}</div><div class="v">{_e(val)}</div>'
        f'<div class="s">{_e(sub)}</div></div>'
        for k, val, sub in stats_cards
    )

    proven_rows = "".join(
        f'<tr><td class="mono">{_e(p["id"])}</td><td>{_e(p["text"])}</td>'
        f'<td class="ok">PASS</td><td class="mono">'
        + "<br>".join(
            f'{_e(ev.get("kind"))} · {_e(_short_digest(ev.get("digest", "")))}'
            for ev in p.get("evidence", [])
        )
        + "</td></tr>"
        for p in g["passes"]
    ) or '<tr><td colspan="4" class="empty">nothing proven yet</td></tr>'

    failed_rows = "".join(
        f'<tr><td class="mono">{_e(f["id"])}</td><td>{_e(f.get("text", ""))}</td>'
        f'<td class="no">UNPROVEN</td><td>{_e(f.get("why", ""))}</td></tr>'
        for f in g["failures"]
    ) or '<tr><td colspan="4" class="empty">none — every criterion is proven</td></tr>'

    if findings:
        findings_html = "".join(
            f'<div class="finding {_e(f["severity"])}">'
            f'<span class="pill {_e(f["severity"])}">{_e(f["severity"])}</span> '
            f'<strong>{_e(f["title"])}</strong>'
            f'<div style="color:#475569;font-size:13px;margin-top:4px">{_e(f["detail"])}</div>'
            f'<div class="mono" style="color:#94a3b8;margin-top:2px">{_e(_when(f.get("at", "")))}</div>'
            f"</div>"
            for f in findings
        )
    else:
        findings_html = '<div class="empty">no drift flags — the log stayed on topic and every run of steps carried evidence</div>'

    conv_html = '<div class="empty">no progress checkpoints were logged</div>'
    if conv.get("points"):
        vals = [v for _, v in conv["points"]]
        conv_html = (
            svg.line_chart(vals, width=560, height=120, color=svg.CYAN, lo=0, hi=100)
            + f'<div style="font-size:13px;color:#475569;margin-top:6px">'
              f'<strong>{_e(conv["state"])}</strong> · {_e(conv.get("why", ""))}</div>'
        )

    target_rows_cells = []
    for t in m.get("targets") or []:
        verified = '<span class="ok">yes</span>' if t["verified_after"] else '<span class="no">no</span>'
        target_rows_cells.append(
            f'<tr><td class="mono">{_e(t["target"])}</td><td>{int(t["touches"])}</td>'
            f'<td class="mono">{_e(_when(t["last"]))}</td><td>{verified}</td></tr>'
        )
    target_rows = "".join(target_rows_cells) or (
        '<tr><td colspan="4" class="empty">no step recorded a --target</td></tr>'
    )

    hourly_html = svg.bar_chart(m["hourly"], width=560, height=110, color=svg.CYAN) if m["hourly"] else ""
    timeline_svg = svg.timeline(m["events"], findings, width=920, height=140)

    rows = []
    for ev in m["events"][-40:]:
        ts = str(ev.get("ts") or "")[11:19]
        evn = len(ev.get("evidence") or [])
        rows.append(
            f'<tr><td class="mono">{_e(ts)}</td><td class="mono">{_e(ev.get("id", ""))}</td>'
            f'<td>{_e(ev.get("kind", ""))}</td><td>{_e(util.one_line(ev.get("intent", ""), 96))}</td>'
            f'<td class="mono">{evn}</td></tr>'
        )
    appendix = "".join(rows) or '<tr><td colspan="5" class="empty">no events</td></tr>'

    non_goals = "".join(f"<li>{_e(x)}</li>" for x in m["non_goals"]) or "<li class='empty'>not declared</li>"
    risks = "".join(f"<li>{_e(x)}</li>" for x in m["risks"]) or "<li class='empty'>not declared</li>"

    ch = m.get("changes") or {}
    if not ch.get("available"):
        changes_html = (
            '<div class="empty">no baseline snapshot was taken at the start of this shift, '
            'so a trustworthy diff is impossible. Take one with <span class="mono">nsh baseline</span> '
            'before the next run.</div>'
        )
    elif not ch.get("rows"):
        changes_html = '<div class="empty">nothing in the project changed during this shift</div>'
    else:
        s = ch["summary"]
        body = []
        for r in ch["rows"]:
            mark = {"added": '<span class="ok">A</span>',
                    "modified": '<span style="color:#d97706;font-weight:700">M</span>',
                    "deleted": '<span class="no">D</span>'}.get(r["status"], "?")
            if r["status"] == "deleted":
                audit = '<span class="empty">n/a</span>'
            else:
                audit = '<span class="ok">checked after</span>' if r["audited_after"] else '<span class="no">not checked after</span>'
            lines = "—" if r["added"] < 0 else f'+{r["added"]} / −{r["removed"]}'
            by = f' <span class="mono" style="color:#94a3b8">{_e(",".join(r["audited_by"]))}</span>' if r.get("audited_by") else ""
            body.append(
                f'<tr><td>{mark}</td><td class="mono">{_e(r["path"])}</td>'
                f'<td class="mono">{_e(lines)}</td><td class="mono">{_e(_when(r.get("last_edit", "")))}</td>'
                f'<td>{audit}{by}</td></tr>'
            )
        changes_html = (
            f'<div style="font-size:13px;color:#475569;margin-bottom:10px">'
            f'{s["modified"]} modified · {s["added"]} added · {s["deleted"]} deleted · '
            f'<strong>{s["unaudited"]}</strong> changed file(s) were never checked afterwards'
            f'</div>'
            '<table><tr><th></th><th>file</th><th>lines</th><th>last edit</th><th>audited after?</th></tr>'
            + "".join(body)
            + "</table>"
            + '<div style="font-size:12px;color:#94a3b8;margin-top:10px">'
              'Diff against the snapshot taken at <span class="mono">nsh init</span>. Line counts come from git '
              'when the project is a repository. "Checked after" means a check event happened after the file\'s '
              'last modification — it is a heuristic, not proof that the check covered that file.</div>'
        )

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>NIGHTSHIFT · flight report · {_e(m['project'])}</title>
<style>{CSS}</style></head>
<body><div class="wrap">

<header>
  <h1>Nightshift · Flight report</h1>
  <div class="goal">{_e(m['goal'])}</div>
  <div class="meta">
    <span class="badge {_e(v['tone'])}">{_e(v['label'])}</span>
    <span>{_e(v['why'])}</span>
    <span>{_e(m['window'])}</span>
    <span>{_e(m['project'])}</span>
  </div>
</header>

<section>
  <h2>Wake-up brief</h2>
  <div class="card"><pre class="brief">{_e(chr(10).join(m['brief']))}</pre></div>
</section>

<section>
  <h2>At a glance</h2>
  <div class="cards">{cards_html}</div>
</section>

<section>
  <h2>Black box · {len(m['events'])} events</h2>
  <div class="card">{timeline_svg}
    <div style="font-size:12px;color:#94a3b8;margin-top:8px">
      ticks = steps · diamonds = checks · circles = checkpoints · red pins = drift flags
    </div>
  </div>
</section>

<section>
  <h2>Proven</h2>
  <div class="card"><table>
    <tr><th>ID</th><th>Done-criterion</th><th>Result</th><th>Evidence (digest)</th></tr>
    {proven_rows}
  </table></div>
</section>

<section>
  <h2>Not proven — read this part even if it stings</h2>
  <div class="card"><table>
    <tr><th>ID</th><th>Done-criterion</th><th>Result</th><th>Why</th></tr>
    {failed_rows}
  </table></div>
</section>

<section>
  <h2>Drift &amp; near-misses</h2>
  <div class="card">{findings_html}</div>
</section>

<section>
  <h2>Where the time went</h2>
  <div class="card"><table>
    <tr><th>target</th><th>touches</th><th>last touched</th><th>verified after?</th></tr>
    {target_rows}
  </table></div>
</section>

<section>
  <h2>What changed, and what looked at it</h2>
  <div class="card">{changes_html}</div>
</section>

<section class="grid2">
  <div><h2>Convergence</h2><div class="card">{conv_html}</div></div>
  <div><h2>Activity by hour</h2><div class="card">{hourly_html or '<div class="empty">nothing logged</div>'}</div></div>
</section>

<section class="grid2">
  <div><h2>Non-goals (respected?)</h2><div class="card"><ul style="margin:0;padding-left:18px">{non_goals}</ul></div></div>
  <div><h2>Known risks</h2><div class="card"><ul style="margin:0;padding-left:18px">{risks}</ul></div></div>
</section>

<section>
  <h2>Appendix · last 40 events</h2>
  <div class="card"><table>
    <tr><th>time</th><th>id</th><th>kind</th><th>intent</th><th>#ev</th></tr>
    {appendix}
  </table></div>
</section>

<footer>
  Generated by <span class="mono">nightshift {_e(__version__)}</span> at {_e(m['generated'])}<br>
  This report is derived from an append-only log. Re-render it yourself:
  <span class="mono">nsh report --html</span> — the digests above are sha256 of captured bytes.
</footer>
</div></body></html>
"""


# --------------------------------------------------------------------------- #
# Markdown
# --------------------------------------------------------------------------- #

def render_md(m: dict[str, Any]) -> str:
    st = m["stats"]
    g = m["gate"]
    v = m["verdict"]
    lines = [
        f"# NIGHTSHIFT — flight report",
        "",
        f"> **{v['label']}** — {v['why']}",
        "",
        f"**Goal:** {m['goal']}",
        "",
        f"**Window:** {m['window']}",
        "",
        "## Wake-up brief",
        "",
        "```",
        *m["brief"],
        "```",
        "",
        "## At a glance",
        "",
        "| metric | value |",
        "| --- | --- |",
        f"| wall clock used | {util.human_dur(st['wall_s'])} |",
        f"| steps | {st['steps']} |",
        f"| evidence coverage | {util.pct(st['coverage'])} ({st['proven_steps']}/{st['steps']}) |",
        f"| checks / checkpoints | {st['checks']} / {st['ticks']} |",
        f"| criteria proven | {st['criteria_passed']}/{st['criteria']} |",
        f"| drift flags | {len(m['findings'])} |",
        "",
        "## Proven",
        "",
    ]
    if g["passes"]:
        for p in g["passes"]:
            digests = ", ".join(f"`{_short_digest(e.get('digest', ''))}`" for e in p.get("evidence", []))
            lines.append(f"- [x] **{p['id']}** {p['text']} — evidence {digests}")
    else:
        lines.append("_nothing proven yet_")
    lines += ["", "## Not proven", ""]
    if g["failures"]:
        for f in g["failures"]:
            lines.append(f"- [ ] **{f['id']}** {f.get('text', '')} — {f.get('why', '')}")
    else:
        lines.append("_none — the gate is green_")
    lines += ["", "## Drift & near-misses", ""]
    if m["findings"]:
        for f in m["findings"]:
            lines.append(f"- **{f['severity']}** · {f['title']} — {f['detail']} ({f.get('at', '')})")
    else:
        lines.append("_no drift flags_")
    lines += ["", "## Where the time went", ""]
    if m.get("targets"):
        lines += ["| target | touches | last touched | verified after |", "| --- | --- | --- | --- |"]
        for t in m["targets"]:
            lines.append(
                "| `%s` | %d | %s | %s |"
                % (t["target"], int(t["touches"]), _when(t["last"]), "yes" if t["verified_after"] else "no")
            )
    else:
        lines.append("_no step recorded a --target_")
    lines += ["", "## What changed, and what looked at it", ""]
    ch = m.get("changes") or {}
    if not ch.get("available"):
        lines.append("_no baseline snapshot was taken at the start of this shift — run `nsh baseline` first_")
    elif not ch.get("rows"):
        lines.append("_nothing in the project changed during this shift_")
    else:
        s = ch["summary"]
        lines.append(
            "**%d modified · %d added · %d deleted · %d never checked afterwards**"
            % (s["modified"], s["added"], s["deleted"], s["unaudited"])
        )
        lines.append("")
        lines += ["| | file | lines | last edit | audited after |", "| --- | --- | --- | --- | --- |"]
        for r in ch["rows"]:
            mark = {"added": "A", "modified": "M", "deleted": "D"}.get(r["status"], "?")
            lines_txt = "—" if r["added"] < 0 else "+%d / −%d" % (r["added"], r["removed"])
            audit = "n/a" if r["status"] == "deleted" else ("yes" if r["audited_after"] else "**no**")
            lines.append("| %s | `%s` | %s | %s | %s |"
                         % (mark, r["path"], lines_txt, _when(r.get("last_edit", "")), audit))
        lines.append("")
        lines.append("_Diff against the snapshot taken at `nsh init`; line counts come from git when available._")
    lines += ["", "## Convergence", "", f"{m['convergence'].get('state')} — {m['convergence'].get('why', '')}", ""]
    lines += ["## Non-goals", ""] + [f"- {x}" for x in m["non_goals"]] + [""]
    lines += ["## Known risks", ""] + [f"- {x}" for x in m["risks"]] + [""]
    lines += ["---", f"_Generated by nightshift {__version__} at {m['generated']}._", ""]
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# entry point
# --------------------------------------------------------------------------- #

def write_report(store, analysis: dict[str, Any], *, fmt: str = "html",
                 out: str | Path | None = None, project: str = "") -> Path:
    m = model(analysis, project=project or store.root.resolve().parent.name)
    store.reports_dir.mkdir(parents=True, exist_ok=True)
    if out is None:
        out = store.reports_dir / ("flight-report.html" if fmt == "html" else "flight-report.md")
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = render_html(m) if fmt == "html" else render_md(m)
    # open() rather than Path.write_text(newline=...): keep one code path for 3.10+
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    return path
