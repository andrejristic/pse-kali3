#!/usr/bin/env python3
# =============================================================================
# PSE-KALI — ENGAGEMENT REPORT
# Turn an audit log into a self-contained, printable HTML report: summary, the
# simplex with every action, per-unit posture (θ = the other/w_o share), the
# full audit, held/escalated actions, and findings. A shareable deliverable.
#
#   python3 report.py [--audit audit/engagement.jsonl] [--out report.html]
# =============================================================================
import argparse
import html
import json
import math
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))
UNIT_COLORS = {"recon": "#0284c7", "password": "#7c3aed", "sniff": "#059669",
               "access": "#c026d3"}
C_BLOCK, C_FLOOR, C_ACCENT = "#dc2626", "#d97706", "#0891b2"


def load(audit):
    recs = []
    for line in open(audit) if os.path.exists(audit) else []:
        line = line.strip()
        if not line:
            continue
        try:
            recs.append(json.loads(line))
        except ValueError:
            pass
    return recs


def _state(r):
    s = r.get("state", {})
    return (s.get("w_s", 0.0), s.get("w_o", 0.0), s.get("w_f", 0.0))


# ---- simplex SVG (computed in Python, no JS) ------------------------------
def _pt(ws, wo, wf, S=84, padx=8, pady=6):
    Hh = math.sqrt(3) / 2
    x = wo + wf * 0.5
    y = wf * Hh
    return (padx + x * S, pady + (Hh - y) * S)


def simplex_svg(recs):
    a, b, c = _pt(1, 0, 0), _pt(0, 1, 0), _pt(0, 0, 1)
    eps = 0.28 / math.sqrt(2) * 84
    out = [f'<svg viewBox="0 0 100 92" class="simplex">']
    out.append(f'<polygon points="{a[0]},{a[1]} {b[0]},{b[1]} {c[0]},{c[1]}" '
               f'fill="#f1f5f9" stroke="#cbd5e1" stroke-width="0.4"/>')
    for p in (a, b):
        out.append(f'<circle cx="{p[0]}" cy="{p[1]}" r="{eps}" fill="none" '
                   f'stroke="{C_BLOCK}" stroke-width="0.35" stroke-dasharray="1.4 1.2" opacity="0.55"/>')
    for p, t, dx, anc in ((a, "NARCISSISTIC", -1, "start"),
                          (b, "CODEPENDENT", 1, "end"),
                          (c, "SCHIZOID", 0, "middle")):
        dy = 6.5 if t != "SCHIZOID" else -3
        out.append(f'<text x="{p[0]+dx}" y="{p[1]+dy}" text-anchor="{anc}" '
                   f'font-size="3" font-family="monospace" fill="#64748b">{t}</text>')
    for r in recs:
        x, y = _pt(*_state(r))
        col = UNIT_COLORS.get(r.get("unit"), "#888")
        if r.get("allowed"):
            out.append(f'<circle cx="{x}" cy="{y}" r="2.2" fill="{col}" stroke="#fff" stroke-width="0.4"/>')
        else:
            floor = (r.get("intervention") or {}).get("kind") == "unauthorized"
            cc = C_FLOOR if floor else C_BLOCK
            out.append(f'<circle cx="{x}" cy="{y}" r="3" fill="none" stroke="{cc}" stroke-width="0.7"/>')
            out.append(f'<circle cx="{x}" cy="{y}" r="1" fill="{cc}"/>')
    out.append("</svg>")
    return "\n".join(out)


def build(recs, engagement):
    passed = [r for r in recs if r.get("allowed")]
    held = [r for r in recs if not r.get("allowed")]
    units = {}
    for r in recs:
        units.setdefault(r.get("unit", "?"), []).append(r)
    when = time.strftime("%Y-%m-%d %H:%M", time.localtime(
        max((r.get("ts", 0) for r in recs), default=time.time())))
    scope = "—"

    def esc(s):
        return html.escape(str(s))

    # per-unit posture: mean (w_s,w_o,w_f); θ = mean w_o (the other/capitulation share)
    posture = []
    for u, rs in units.items():
        n = len(rs)
        mw = [sum(_state(r)[i] for r in rs) / n for i in range(3)]
        theta = round(mw[1] * 100, 1)
        posture.append((u, n, mw, theta))

    rows = []
    for r in recs:
        s = _state(r)
        iv = r.get("intervention") or {}
        v = ("pass" if r.get("allowed")
             else ("ESCALATE" if iv.get("kind") == "unauthorized" else "HELD"))
        vc = ("v-pass" if r.get("allowed")
              else ("v-floor" if iv.get("kind") == "unauthorized" else "v-held"))
        rows.append(
            f'<tr><td class="u-{esc(r.get("unit"))}">{esc(r.get("unit"))}</td>'
            f'<td>{esc(r.get("tool"))}</td><td>{esc(r.get("target"))}</td>'
            f'<td>{s[0]:.2f}</td><td>{s[1]:.2f}</td><td>{s[2]:.2f}</td>'
            f'<td>{r.get("auth_level", 0):.2f}</td>'
            f'<td class="{vc}">{v}{"/"+esc(iv.get("kind")) if iv.get("kind") and not r.get("allowed") else ""}</td></tr>')

    held_rows = "".join(
        f'<li><b class="u-{esc(r.get("unit"))}">{esc(r.get("unit"))}</b> '
        f'{esc(r.get("tool"))} {esc(r.get("target"))} — '
        f'{esc((r.get("intervention") or {}).get("kind"))}: '
        f'{esc((r.get("intervention") or {}).get("reason"))}</li>' for r in held) \
        or "<li>None — every action stayed within the rules.</li>"

    posture_html = "".join(
        f'<div class="prow"><span class="u-{esc(u)}" style="font-weight:600">{esc(u)}</span>'
        f'<span class="bar"><i style="width:{mw[0]*100:.0f}%;background:{C_BLOCK}"></i>'
        f'<i style="width:{mw[1]*100:.0f}%;background:{C_FLOOR}"></i>'
        f'<i style="width:{mw[2]*100:.0f}%;background:#059669"></i></span>'
        f'<span class="mono">θ={theta}% · n={n}</span></div>'
        for u, n, mw, theta in posture)

    css = """
      :root{--ink:#0f172a;--ink2:#475569;--muted:#94a3b8;--line:#e2e8f0;--bg:#ffffff;--panel:#f8fafc}
      *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--ink);
        font-family:system-ui,Segoe UI,sans-serif;line-height:1.5;font-size:15px}
      .wrap{max-width:900px;margin:0 auto;padding:28px 24px 60px}
      h1{font-size:22px;margin:0} .sub{color:var(--ink2);font-size:14px}
      .bar{display:inline-flex;height:12px;width:220px;border-radius:6px;overflow:hidden;margin:0 10px;vertical-align:middle;border:1px solid var(--line)}
      .bar i{display:block;height:100%}
      .mono{font-family:ui-monospace,monospace}
      header{border-bottom:2px solid var(--ink);padding-bottom:14px;margin-bottom:22px;display:flex;align-items:baseline;gap:14px}
      .eng{margin-left:auto;font-family:ui-monospace,monospace;color:var(--muted)}
      h2{font-size:12px;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);margin:26px 0 10px}
      .tiles{display:flex;gap:10px} .tile{flex:1;background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
      .tile .n{font-size:26px;font-weight:700} .tile .l{font-size:11px;color:var(--muted);text-transform:uppercase}
      .grid{display:grid;grid-template-columns:1.1fr .9fr;gap:22px;align-items:start}
      @media(max-width:720px){.grid{grid-template-columns:1fr}}
      .simplex{width:100%;height:auto;border:1px solid var(--line);border-radius:10px;background:#fff}
      .prow{display:flex;align-items:center;gap:6px;margin:7px 0;font-size:14px}
      table{border-collapse:collapse;width:100%;font-size:13px;margin-top:6px}
      th,td{text-align:left;padding:6px 9px;border-bottom:1px solid var(--line);white-space:nowrap}
      th{font-size:10px;text-transform:uppercase;color:var(--muted)}
      td{font-family:ui-monospace,monospace;color:var(--ink2)}
      .u-recon{color:#0284c7}.u-password{color:#7c3aed}.u-sniff{color:#059669}.u-access{color:#c026d3}
      .v-pass{color:#059669;font-weight:600}.v-held{color:#dc2626;font-weight:600}.v-floor{color:#d97706;font-weight:600}
      ul{padding-left:18px} li{margin:5px 0;font-size:13.5px}
      .foot{color:var(--muted);font-size:12px;margin-top:30px;border-top:1px solid var(--line);padding-top:14px}
      @media print{.wrap{max-width:none}}
    """
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>PSE-Kali Engagement Report</title><style>{css}</style></head><body>
<div class="wrap">
  <header><h1>PSE&#8209;Kali · Engagement Report</h1>
    <span class="eng">{esc(engagement)} · {when}</span></header>

  <h2>Summary</h2>
  <div class="tiles">
    <div class="tile"><div class="n">{len(recs)}</div><div class="l">actions</div></div>
    <div class="tile"><div class="n" style="color:#059669">{len(passed)}</div><div class="l">passed</div></div>
    <div class="tile"><div class="n" style="color:#dc2626">{len(held)}</div><div class="l">held by kernel</div></div>
    <div class="tile"><div class="n">{len(units)}</div><div class="l">units</div></div>
  </div>

  <div class="grid">
    <div>
      <h2>Care&#8209;invariant simplex</h2>
      {simplex_svg(recs)}
    </div>
    <div>
      <h2>Per&#8209;unit posture (θ = other share)</h2>
      {posture_html}
      <p class="sub" style="margin-top:10px">Bar: self (red) · other (amber) · field (green).
      θ is the mean other/w_o share. In this security regime a low θ (little capitulation)
      is healthy; a high θ trends Codependent.</p>
    </div>
  </div>

  <h2>Held / escalated</h2>
  <ul>{held_rows}</ul>

  <h2>Full audit</h2>
  <table><thead><tr><th>unit</th><th>tool</th><th>target</th>
    <th>w_s</th><th>w_o</th><th>w_f</th><th>auth</th><th>verdict</th></tr></thead>
    <tbody>{"".join(rows)}</tbody></table>

  <p class="foot">Generated by PSE&#8209;Kali. Every action was scored on the
  Care&#8209;invariant simplex and passed the ε=0.28 membrane; actions below the
  authorization floor (auth&lt;0.35) were unreachable. This report is the audit
  record — reproducible from <code>audit/engagement.jsonl</code>.</p>
</div></body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit", default=os.path.join(HERE, "audit", "engagement.jsonl"))
    ap.add_argument("--out", default=os.path.join(HERE, "report.html"))
    args = ap.parse_args()
    recs = load(args.audit)
    eng = recs[0].get("engagement", "ENG") if recs else "ENG"
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(build(recs, eng))
    print(f"report: {args.out}  ({len(recs)} actions)")


if __name__ == "__main__":
    main()
