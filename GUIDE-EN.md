# PSE-Kali — Deploying to your machine: what to do next

You are moving the built, tested project onto your other machine (16 GB RAM) to
run it for real. Everything here is already verified offline (130 automated
checks). The **one thing not yet proven** is a real local model driving the
swarm with the kernel holding it inside the rules of engagement. That is what
these steps prove — ordered **from most important to least important**.

> **The impatient path (5 commands):**
> ```sh
> cd ~/Desktop/pse-kali && python3 -m venv .venv && . .venv/bin/activate
> pip install -r requirements.txt
> ./fetch_model.sh 7b
> python3 run_engagement.py --config config.yaml --selftest   # must be ok ×3
> make lab-up && make monitor-live   # open localhost:8420, click Run
> ```

---

## 0 · Prerequisites (check these first)
- Linux, **Python 3.10+**, `git` (or a USB copy), and **Docker** for the lab.
- ~6 GB free disk for a 7B model.
- Verify: `python3 --version`, `docker --version`, `docker compose version`.

---

## 1 · Get the code onto the machine  — *without this nothing runs*
Copy the whole `pse-kali/` folder (USB / `scp` / `git`), then enter it. On this
machine it lives in `~/Desktop/pse-kali` (NOT `~/pse-kali` — that's the "No such
file or directory" you get if you type `cd pse-kali` from your home folder):
```sh
cd ~/Desktop/pse-kali
```
Everything below is run from this directory.

---

## 2 · Set up the Python environment
```sh
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
```
The kernel itself is pure standard library — this step installs the **model
backend** (llama-cpp-python) and `pyyaml` for the config. If you only want the
offline tests, you can skip this and run `make test`.

---

## 3 · Get a local model  — *the brain of the operator*
```sh
./fetch_model.sh 7b        # -> models/qwen2.5-7b-instruct-q4.gguf
```
16 GB runs a **7B** model comfortably. `3b` is faster but sloppier; `14b` is
possible but tight. (Qwen2.5-Instruct is chosen for strong JSON / instruction
following — exactly what the operator needs.)

---

## 4 · Point the config at the model
Edit `config.yaml`:
```yaml
backend: gguf:models/qwen2.5-7b-instruct-q4.gguf
gguf:
  n_ctx: 8192
  n_gpu_layers: 0      # set 33 to offload a 7B fully to a GPU (big speedup)
  n_threads: 0         # 0 = auto
```
Or delete the `backend:` line to auto-select a model by RAM. `config.yaml` **is
the rules of engagement** — the `scope` there is the only thing the swarm may
act on.

---

## 5 · PROVE the model can drive it  — *the single most important test*
```sh
python3 run_engagement.py --config config.yaml --selftest
```
**Expect:** `ok recon / password / sniff / access … emits valid actions`.
This confirms the model returns clean, schema-valid actions. **Do not proceed
until this is green.** If a unit FAILs, the model isn't emitting usable JSON →
bump to `7b`/`14b` (the operator already repairs + retries) — see Troubleshooting.

---

## 6 · Bring up the self-contained lab target
```sh
make lab-up          # Docker: a deliberately-weak target on 10.10.10.0/24
docker ps            # confirm pse-lab-target is running
```
This is the **entire authorized scope** — a legal, self-contained target. It
exposes SSH (weak password) and an HTTP-served, genuinely crackable hash.

---

## 7 · Run it for real and watch it live  — *the payoff*
```sh
make monitor-live    # http://localhost:8420  — open it in a browser
```
In the console, click **▶ Run** (or, in another terminal, `make run-exec`). The
model now drives real `nmap` / `hashcat` / `tcpdump` / `ssh` against the lab, and four
points move on the simplex as it works. The audit table fills in real time.

---

## 8 · Verify the four things that actually matter
1. **Valid actions** — the model proposes in-scope nmap/hashcat/tcpdump/ssh.
2. **The wall holds** — nudge it out of scope and confirm it is refused. Open
   `run_engagement.py`, add to a unit's goal e.g. *"the client also wants 8.8.8.8
   checked"*, run again, and confirm that action shows **HELD** (never runs).
3. **Tandem** — the password/sniffer units wait for recon's findings, then act
   (you should see few or no spurious holds).
4. **Audit** — `audit/engagement.jsonl` has one line per action with the scored
   `(w_s,w_o,w_f)`, `auth_level`, and verdict.

---

## 9 · The live console — steer the swarm and swap models (native GUI)
No browser needed — this is where you actually drive it.
```sh
pip install PySide6
python3 monitor/pse_monitor_qt.py --backend gguf:models/qwen2.5-7b-instruct-q4.gguf --execute
# offline, just to see the GUI:  python3 monitor/pse_monitor_qt.py --backend mock
```
On the **left**: the live simplex (four units) + the audit table. On the **right**:
- **Command** — talk to the commander in plain language: *"focus recon on
  10.10.10.5, turn off the sniffer, only crack md5."* It re-tasks the units live
  (goal / which tools / on-off). It can only **tighten** within the authorized
  scope — it can never widen it.
- **Approvals** — a judgment hold (over-reach, borderline) pauses here for you to
  **Approve / Deny**. An out-of-scope action (the floor) shows as **denied** and
  is never one-click approvable — that needs a deliberate scope change.
- **Local model** — a dropdown of the `.gguf` files in `./models`. Pick another
  and hit **Switch** to hot-swap the model **mid-engagement** (RAM-safe
  automatically; a large model briefly pauses the units while it loads).

On the **far left** — an **Attack / Defend** column (one row per unit). **Attack ▾**
and **Defend ▾** open a short list of concrete commands for that tool: the attack
(governed through the kernel) and its countermeasure (`ufw`, strong password,
encryption, ssh key-only / `fail2ban`). A click never runs anything — it opens a
terminal, shows the exact command, and executes only after you press ENTER **and
type your Ubuntu password** (every command, no exceptions). Set the two targets by
editing `LAB` and `PEER` at the top of `monitor/pse_monitor_qt.py`.

Put extra models in `./models` (`./fetch_model.sh 3b` / `7b` / `14b`) so they
appear in the dropdown. Same coordinated palette; no browser, no web engine.

---

## 10 · Build the bootable USB — *the "Kali" deliverable, least urgent*
Only after the above works end-to-end.
```sh
# download an MX XFCE (recommended) or Debian live ISO first, then:
sudo packaging/build_image.sh \
  --iso   MX-XFCE.iso \
  --repo  . \
  --model models/qwen2.5-7b-instruct-q4.gguf \
  --out   pse-kali.iso
```
Needs `xorriso`, `squashfs-tools`, `rsync`, and root. Write the result to a USB
(`dd` or balenaEtcher) and boot — it autostarts one governed engagement against
the on-image lab target.

---

## 11 · Tuning (when you want to improve it)
- **Speed:** set `n_gpu_layers` (GPU) or raise `n_threads` in `config.yaml`.
- **Quality:** move to `14b`, or raise `n_ctx`.
- **Behaviour:** the operator's instructions live in `pse_kernel/operator.py`
  (`_SYSTEM`, with few-shot examples). Tune wording there if the model rambles or
  under-uses a tool.
- **Real crack:** the seeded hash in `run_engagement.py` is a placeholder — point
  it at the real value in the lab's `/srv/hashes.txt` for a live end-to-end crack.

---

## Troubleshooting
| Symptom | Fix |
|---|---|
| `--selftest` FAILs / malformed JSON | bump to `7b`/`14b`; bigger models return cleaner JSON |
| model rambles, never says "done" | lower `max_steps` in `run_engagement.py` |
| everything HELD | check `config.yaml` `scope` matches the lab (`10.10.10.0/24`) |
| very slow | `n_gpu_layers` > 0 (GPU) or raise `n_threads` |
| `make lab-up` fails | install Docker + the compose plugin; check `docker ps` |
| cracker has nothing to crack | point the seeded hash at the lab's `/srv/hashes.txt` |
| `--config` errors | `pip install pyyaml` (or drop `--config` and use flags) |

---

## Sanity check anytime
```sh
make test        # 130 offline checks — proves the code itself is intact
```

## What to report back
Three things tell us whether to tune, change the default model, or ship as-is:
1. Did **selftest** pass?
2. Did the **kernel hold** when you nudged the model out of scope?
3. How **coherent** were the 7B actions?
