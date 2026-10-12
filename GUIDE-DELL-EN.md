# PSE-Kali on the Dell (16 GB) — hardware operations

Everything that needs a real machine: the lab target, running real tools, building
the bootable USB, and putting the web app online. Do these on the Dell (the
offline tests + the native GUI work anywhere; this guide is the hardware half).

Assumes the repo is at `~/Desktop/pse-kali` and you've done the base setup
(`python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt`
and `./fetch_model.sh 7b`). See RUNBOOK-16GB.md / GUIDE-EN.md for that.

---

## 1 · The Docker lab (the safe target to hit)
A self-contained, deliberately-weak target on `10.10.10.0/24` (host `10.10.10.5`).
This is the whole authorized scope — legal, offline, disposable.

**Install Docker (once):**
```sh
sudo apt install -y docker.io docker-compose-plugin
sudo usermod -aG docker $USER      # then log out / back in so `docker` works without sudo
```
**Up / down:**
```sh
make lab-up          # builds + starts pse-lab-target (ssh:22, http:8000 with a crackable hash)
docker ps            # confirm it's running
make lab-down
```
**Gotchas:** the subnet `10.10.10.0/24` must not clash with your real Wi-Fi/LAN
(if it does, change it in `lab/docker-compose.yml` **and** `config.yaml` together).
First build pulls `debian:stable-slim` (needs internet). Time: ~5 min first run.

## 2 · Run the swarm with REAL tools
```sh
sudo apt install -y nmap tcpdump hashcat john openssh-client   # the real binaries
make lab-up
python3 run_engagement.py --config config.yaml --execute       # model drives real tools at the lab
make report                                                    # -> report.html deliverable
```
Or drive it live from the native console and watch it:
```sh
python3 monitor/pse_monitor_qt.py --backend gguf:models/qwen2.5-7b-instruct-q4.gguf --execute
```
**Note:** `--execute` runs real binaries. Keep `config.yaml` scope on the lab
(`10.10.10.0/24`) unless you deliberately, and with authorization, widen it.

## 3 · Build the bootable USB ("AI-Kali")
Turns an existing live ISO into a self-contained `pse-kali.iso` that boots into the
governed engagement.

**Needs:** root, `xorriso squashfs-tools rsync`, ~10–15 GB free disk, a base ISO
(MX XFCE recommended, or Debian live), and the model file.
```sh
sudo apt install -y xorriso squashfs-tools rsync
# download MX-XFCE.iso first, then:
sudo packaging/build_image.sh \
  --iso MX-XFCE.iso --repo . \
  --model models/qwen2.5-7b-instruct-q4.gguf --out pse-kali.iso
# write it to a USB:
sudo dd if=pse-kali.iso of=/dev/sdX bs=4M status=progress oflag=sync   # or use balenaEtcher
```
**Gotchas:** the chroot `apt install` step needs internet; the model makes the ISO
~5 GB+; on the target machine watch UEFI/Secure Boot; test-boot in a VM
(VirtualBox/GNOME Boxes) before trusting a real machine. Time: ~30–60 min with
downloads.

## 4 · Put the web app online (Hugging Face — free)
So you can open the console from your phone or any browser (the Dell can host or
just push; the build runs on HF).

```sh
# 1) push the repo to GitHub
git init && git add . && git commit -m "pse-kali" && git branch -M main
git remote add origin https://github.com/<you>/pse-kali.git && git push -u origin main
# 2) huggingface.co -> New Space -> SDK: Docker -> connect/push this repo
#    HF builds the root Dockerfile and serves on port 7860 -> public URL
```
**Make it safe + live:**
- It runs in **demo mode** (no real tools) — correct for public.
- Set a token so it's not open to the world: Space **Settings → Variables/secrets**
  → `PSE_TOKEN` = a secret; then open `https://<space>.hf.space/?t=<secret>`.
- For a lively demo add `PSE_BACKEND=claude:claude-opus-4-8` + secret
  `ANTHROPIC_API_KEY` (uncomment `pip install anthropic` in the Dockerfile).
See `webapp/GUIDE-HOSTING-EN.md` for the full walkthrough.

---

## Troubleshooting
| Symptom | Fix |
|---|---|
| `docker: permission denied` | `sudo usermod -aG docker $USER`, then re-login |
| lab subnet clash | change `10.10.10.0/24` in `lab/docker-compose.yml` **and** `config.yaml` |
| `--execute` finds nothing | install the real binaries (`nmap tcpdump hashcat`) |
| ISO build: `missing tool` | `sudo apt install xorriso squashfs-tools rsync` |
| ISO won't boot | disable Secure Boot on the target; re-write the USB; test in a VM first |
| HF Space build fails | check the root `Dockerfile` is present; read the Space build logs |

## What runs where
| Task | Needs the Dell? |
|---|---|
| offline tests (`make test`), native GUI, report | no (any machine) |
| Docker lab + real-tool run (`--execute`) | **yes** (Docker) |
| build the bootable ISO | **yes** (root + disk) |
| deploy web app on HF | your accounts (build runs on HF) |
