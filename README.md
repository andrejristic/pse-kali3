# PSE-Kali

A minimal, bootable **AI version of Kali** — a local model drives four governed
security tools, and the **PSE kernel physically holds the operator inside the
rules of engagement**. Safety is a wall, not a prompt: an out-of-scope action is
not discouraged, it is geometrically unreachable.

Built from the ZeravaTech PSE (Partial Self-Extension) corpus. Posture is
**defensive / authorized-assessment**; v1 runs against a shipped lab target only.

## The idea in one picture
```
   model proposes action ─▶ KERNEL scores it (w_s,w_o,w_f) + authorization floor
                                   │
                    allow ◀────────┼────────▶ escalate to human (out of scope,
                     │                          over-reach, capitulation, borderline)
                     ▼
             tool runs in the lab ─▶ findings ─▶ shared store ─▶ (feeds the other units)
                                                                  all logged to one audit
```
Four units — **recon** (nmap/theHarvester), **password** (hashcat/john),
**sniffer** (tcpdump/bettercap), **access** (ssh) — run **concurrently** on one kernel, one shared
engagement context, one audit log.

## Quickstart
```sh
make test                     # full offline suite (no deps, no network)
python3 run_engagement.py --backend mock          # offline narrated demo
make monitor                  # build the live-constraint monitor (HTML)
```
Real run (on your machine):
```sh
pip install -r requirements.txt        # or just the backend you use
make lab-up                            # self-contained target on 10.10.10.0/24
python3 run_engagement.py --config config.yaml --selftest   # check the model
make run-exec                          # model drives real tools against the lab
make lab-down
```

## Layout
| Path | What |
|------|------|
| `pse_kernel/` | the moat — `score` · `membrane` (+ authorization floor) · `context` · `orchestrator` · `operator` (Claude/Mistral/GGUF) · `adapters` |
| `packs/` | per-tool config: recon / password / sniff / access. **Zero kernel edits.** |
| `monitor/` | live-constraint monitor — HTML/SVG (browser) **and** native PySide6 (`pse_monitor_qt.py`, QPainter, no web engine) |
| `lab/` | self-contained Docker target (`docker compose up`) |
| `config.yaml` | the rules of engagement (scope, grants, model) |
| `packaging/` | systemd autostart for the boot image |
| `tests/` | 130 offline checks — all green |

## Discipline
- The **kernel is domain-agnostic**; behaviour is configured by packs. If adding
  a tool needs a kernel edit, the pack schema is wrong.
- **Two walls:** the kernel refuses out-of-scope actions; the adapters re-check
  scope in code and run only allow-listed binaries.
- **Lab only in v1.** `config.yaml` scope is the shipped target. Don't add a real
  host without written authorization.

See `../123/PSE_Kali_MinimalOS_Plan.md` for the full build plan.
