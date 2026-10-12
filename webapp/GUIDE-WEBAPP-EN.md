# PSE-Kali Web Console — User Guide

The same governed console as the native app, but in a **browser** — so you can
use it from any device (laptop, phone), and host it so others can too. A small
Python server drives the live swarm; the page is the front-end.

## Run it locally
```sh
cd pse-kali
pip install pyyaml                       # kernel is stdlib; this is for config
python3 webapp/server.py --backend mock  # demo (no tools run) — safe
# open http://localhost:8420 in a browser
```
Backends (same as everywhere):
```sh
python3 webapp/server.py --backend gguf:models/qwen2.5-7b-instruct-q4.gguf
python3 webapp/server.py --backend claude:claude-opus-4-8      # needs ANTHROPIC_API_KEY
PSE_EXECUTE=1 python3 webapp/server.py --backend gguf:...      # REAL tools, LOCAL LAB ONLY
```
> This machine ("Moj") has no browser installed. Either install one
> (`sudo apt install firefox-esr`) and open `localhost:8420`, use the **native**
> app (`monitor/pse_monitor_qt.py`), or **host it** (see the hosting guide) and
> open the public URL from your phone.

## What you see
- **Command** — talk to the commander in plain language:
  *"focus recon on 10.10.10.5, turn off the sniffer, only crack md5."* It
  re-tasks the units live. It can only **narrow** within the authorized scope —
  never widen it.
- **Approvals** — a judgment hold (over-reach, borderline) waits here for
  **Approve / Deny**. An out-of-scope action (the floor) is shown **denied** in
  the audit and is never one-click approvable.
- **Local model** — a dropdown of the `.gguf` files in `./models`; pick one and
  **Switch** to hot-swap the model mid-engagement (only meaningful when the
  backend is a local model).
- **Simplex + audit stream** — the four units live, and every scored action.

## Modes
- **Demo mode** (default, `--backend mock` or an API backend, no `PSE_EXECUTE`):
  nothing executes on the machine — it shows the governance and the UI. This is
  the mode to host publicly.
- **Real mode** (`PSE_EXECUTE=1`, local only): runs real tools against the
  shipped lab target on `10.10.10.0/24`. Never do this on a public server.

## API (if you want to script it)
`GET /events` · `GET /log?since=N` · `GET /escalations` · `GET /models` ·
`POST /command {text}` · `POST /escalation {id,decision}` · `POST /switch {path,fits}`.
