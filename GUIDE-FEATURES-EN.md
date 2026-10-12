# PSE-Kali — New features guide

Five additions on top of the governed console. Everything here works locally with
no extra hardware (offline / `--backend mock` too).

## 1 · Engagement report — a shareable deliverable
After a run, turn the audit log into one self-contained, printable HTML report:
```sh
python3 report.py                 # -> report.html   (or: make report)
python3 report.py --audit audit/engagement.jsonl --out client_report.html
```
It contains: summary tiles (actions / passed / held / units), the Care-invariant
simplex with every action, **per-unit posture with θ**, the held/escalated list,
and the full audit table. Open `report.html` in a browser or print to PDF — it's a
clean pentest deliverable, reproducible from the audit log.

## 2 · θ live readout — the theory, made visible
Every monitor (native GUI, web console) now shows **θ per unit** under the simplex.
- **θ = the other/w_o share** of a unit's latest passing action (the PSE θ, mapped
  into our 3-way state).
- **Colour:** green (θ<15) healthy · amber (15–30) watch · red (>30) trends
  **Codependent**. In this security regime a *low* θ (little capitulation) is
  healthy — the opposite of the clinical care regime, where ~30% is optimal.
- It updates live as units act; the report (feature 1) shows the run's mean θ.

## 3 · Authorized scope panel + web token
**Widening scope** is the one thing the commander cannot do — only you, deliberately,
and it's always logged.
- **Native GUI / web console:** the *Authorized scope* panel shows the current scope;
  type a target (e.g. `10.10.10.9/32`) and hit **Authorize** → the kernel's floor
  now allows it, and a `scope_change` line goes into the audit.
- **Never** widen scope to something you're not authorized to test.

**Web token (for public hosting):** protect the hosted server so it isn't open to
everyone:
```sh
PSE_TOKEN=your-secret python3 webapp/server.py     # or set PSE_TOKEN in the host's secrets
# then open:  http://<host>/?t=your-secret
```
Without the token the page still loads but the API returns 401 — nobody can drive
it. (On Hugging Face: Space Settings → add `PSE_TOKEN` as a secret.)

## 4 · Mission presets + live activity
- **Preset buttons** (native GUI + web console): **Full · Recon · Passive · Stop all**
  — one click retasks the units instantly (no model needed). *Passive* = recon +
  sniffer only (no cracking, no access); *Stop all* idles everything.
- **Live activity:** every action a unit takes now streams into the **Command log**
  (`recon ✓ nmap 10.10.10.5`, `⛔ … DENIED`, escalations) so you can watch the
  engagement move in words, not just on the simplex.

## 5 · Attack / Defend panel — hands-on, per tool (native GUI)
A left-hand column adds an **Attack** and a **Defend** menu for each unit
(recon · password · sniff · access) — the teaching surface for a live class.
- **Attack ▾** lists concrete governed commands (e.g. `nmap -sV → lab`, and the
  same against `8.8.8.8` so you watch the kernel **HOLD** it out of scope).
- **Defend ▾** lists the matching countermeasure: recon→`ufw` (hide ports),
  password→strong password, sniff→encryption note, access→ssh key-only / `fail2ban`.
- **The console runs nothing itself.** A click opens a terminal, shows the exact
  command, and it executes only after you press **ENTER and type your Ubuntu
  password** — every command, no exceptions (`sudo -k` clears any cached credential).
- The list pops up at the left↔centre boundary; the result still lands in the
  audit log / simplex like any other action.
- **Targets:** edit `LAB` and `PEER` at the top of `monitor/pse_monitor_qt.py`
  — `PEER` is the *other* machine's IP for the ssh lesson (yours for Smer A,
  Margaret's for Smer B). Needs a terminal emulator (`gnome-terminal`, present by default).

---

### Quick reference
| Feature | Where | How |
|---|---|---|
| Report | CLI | `make report` → `report.html` |
| θ readout | GUI + web | under the simplex, live |
| Scope widen | GUI + web | *Authorized scope* → Authorize (logged) |
| Web token | hosting | `PSE_TOKEN=…` + `?t=…` |
| Presets | GUI + web | Full / Recon / Passive / Stop all |
| Activity log | GUI + web | Command log |
| Attack / Defend | GUI (native) | left column → Attack ▾ / Defend ▾ (password-gated) |
