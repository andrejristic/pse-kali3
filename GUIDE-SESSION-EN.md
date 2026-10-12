# PSE-Kali — Session Runbook (bidirectional attack ↔ defend with Margaret)

The complete, ordered checklist to prepare and run the hands-on class where **both
directions** are demonstrated on two real machines, plus the lab lessons. Do the
steps top to bottom. Each step says **which machine** it runs on.

- **Your machine** — Ubuntu 24.04, user `a`, IP **`10.0.0.109`** (the OptiPlex).
  Role: runs the lab lessons, is the **target** in Smer A, and the **attacker** in
  Smer B.
- **Margaret's laptop** — Ubuntu, IP `<MARGARET-IP>` (fill in below). Role:
  the **attacker** in Smer A, the **defender/target** in Smer B.

Everything is authorized: both machines are ours, on our own Wi-Fi, with the owner
present. Outside that, the same commands are a crime — say this first, and often.

---

## 0 · The picture — what we are demonstrating
1. **Lab lessons 1–3** (recon · password · sniff) against a safe Docker "practice
   box" running locally. This teaches the tools and the **kernel wall** (an
   out-of-scope target is refused — **HELD**).
2. **Smer A — Margaret → your machine (undefended).** She logs in over SSH and
   drops `margaret was here` on the Desktop. Proves she can get in when the host is
   open **and** she is in scope.
3. **Smer B — you → Margaret's machine (defended).** The kernel *allows* it (her IP
   is in scope, you are authorized), but her **hardened host refuses you**. This is
   the second, different wall: even an authorized action is stopped by good defense.

Two walls, taught separately: **the kernel** (scope) and **the host** (hardening).

---

## 1 · Confirm the installs (recap)
**Your machine** — should already be done. Verify:
```sh
for t in nmap hashcat john docker sshd ssh tcpdump curl python3; do \
  command -v $t >/dev/null && echo "OK $t" || echo "MISSING $t"; done
python3 -c "import PySide6" && echo "OK PySide6"
systemctl is-active ssh              # -> active
id margaret                          # -> exists
sudo test -d /home/margaret/Desktop && echo "OK margaret Desktop"
```
**Margaret's laptop** — she runs `margaret-demo/INSTALL-MARGARET-EN.txt` and Step 6
in it must show all **OK**. Get her to send you that screen.

---

## 2 · Get both IPs
- **Your machine:** `10.0.0.109` (confirm: `hostname -I`).
- **Margaret's laptop:** `hostname -I` on her laptop → write it here: `<MARGARET-IP>`.

Both are on the same Wi-Fi, so both look like `10.0.0.x`.

---

## 3 · Rules of engagement — `config.yaml` (do on BOTH machines)
This file **is** the authorized scope. It must list the lab **and both machines**,
so that each real attack is *allowed by the kernel* — that way the only thing that
stops Smer B is Margaret's defense, not the wall.
```sh
cd ~/Desktop/pse-kali3
cp margaret-demo/config.demo.yaml config.yaml
```
Then edit `config.yaml` so it reads (put in the REAL IPs):
```yaml
scope:
  - 10.10.10.0/24          # the Docker lab (lessons 1-3)
  - 10.0.0.109/32          # your machine
  - <MARGARET-IP>/32       # Margaret's laptop
authorizations:
  - target_scope: [10.10.10.0/24, 10.0.0.109/32, <MARGARET-IP>/32]
    tools: [nmap, hashcat, john, tcpdump, tshark, ssh]
```
Do the **same edit on Margaret's laptop** (her copy of the repo).

> If a target is NOT in scope, the kernel HOLDs it (the wall) and you never reach
> the host defense. For the Smer B lesson, her IP **must** be in scope.

---

## 4 · Point the GUI at the other machine (`LAB` + `PEER`)
The native console's Attack/Defend menus use two variables at the top of
`monitor/pse_monitor_qt.py`:
```python
LAB  = "10.10.10.5"     # the docker lab target — leave as is
PEER = "PEER-IP"        # the OTHER machine's IP for the ssh lesson
```
- **On your machine:** set `PEER = "<MARGARET-IP>"` (you reach her — Smer B).
- **On Margaret's laptop:** set `PEER = "10.0.0.109"` (she reaches you — Smer A).

---

## 5 · Wire Smer A — Margaret into your machine
Your machine is already the target (sshd on, `margaret` user, Desktop folder). She
just needs a key that your machine trusts.

**On Margaret's laptop:**
```sh
ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519      # a key, no passphrase
ssh-copy-id margaret@10.0.0.109                        # type the margaret password ONCE
ssh margaret@10.0.0.109 'echo it-works'                # should print it-works
```
(If the Desktop folder is missing, on **your** machine:
`sudo mkdir -p /home/margaret/Desktop && sudo chown margaret:margaret /home/margaret/Desktop`.)

---

## 6 · Wire Smer B — defend Margaret's machine
Pick one or more of the four. Recommended: **key-only + fail2ban.** All commands run
**on Margaret's laptop.**

**a) SSH key-only (turn passwords off)** — your password attempt just bounces.
```sh
sudo sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo systemctl restart ssh
# you will see:  Permission denied (publickey)
```
**b) fail2ban (ban repeat attempts)** — after a few tries your IP is blocked.
```sh
sudo apt install -y fail2ban
sudo systemctl enable --now fail2ban
sudo fail2ban-client status sshd
# you will see: first tries denied, then Connection timed out (banned)
```
**c) UFW firewall (close/limit the port)** — you can't even reach the login.
```sh
sudo ufw enable
sudo ufw deny 22          # or: sudo ufw limit 22   (rate-limit instead of block)
# you will see: Connection refused / timed out
```
**d) Strong password (no config change)** — give her account a long password you
don't know; wordlist/guessing fails with `Permission denied`.

> These are also exactly the **Defend ▾** buttons in the GUI — you can apply them
> live in front of her (each asks for the Ubuntu password).

---

## 7 · The lab target (lessons 1–3) — on each machine that runs those lessons
```sh
cd ~/Desktop/pse-kali3
cp margaret-demo/words.txt .          # wordlist that contains the lab password
make lab-up                           # brings up 10.10.10.5 (ssh + http hash)
docker ps                             # confirm pse-lab-target is running
curl -s http://10.10.10.5:8000/hashes.txt   # should print a $1$... hash
```

---

## 8 · Clean slate for the report
So the final `report.html` shows only what Margaret did:
```sh
make clean            # wipes audit/*.jsonl and the old monitor snapshot
```

---

## 9 · Dry run — prove it BEFORE she arrives
**Lab verdicts (no --execute needed, no tools run):** each should print the verdict.
```sh
python3 run_action.py recon nmap 10.10.10.5 --args="-sV" --rationale test --config config.yaml   # ALLOWED
python3 run_action.py recon nmap 8.8.8.8    --args="-sV" --rationale test --config config.yaml   # HELD (wall)
```
**Smer A live (from Margaret's laptop):**
```sh
python3 run_action.py access ssh 10.0.0.109 --user margaret \
  --command 'echo "margaret was here" > ~/Desktop/margaret_was_here.txt' \
  --rationale "authorized marker" --config config.yaml --execute
```
Then on **your** machine: `cat /home/margaret/Desktop/margaret_was_here.txt` → the marker.

**Smer B live (from your machine):** target her IP — the kernel allows, her defense
refuses:
```sh
python3 run_action.py recon nmap <MARGARET-IP> --args="-sV" \
  --rationale "authorized scan" --config config.yaml --execute      # ALLOWED by kernel, ufw hides ports
python3 run_action.py access ssh <MARGARET-IP> --user margaret \
  --command 'echo hi' --rationale "authorized" --config config.yaml --execute  # ALLOWED by kernel, host refuses
```

---

## 10 · Running the session — the visual console
```sh
cd ~/Desktop/pse-kali3
python3 monitor/pse_monitor_qt.py --backend mock       # to show the UI safely
python3 monitor/pse_monitor_qt.py --execute            # REAL tools (uses config.yaml scope)
```
- **Left column — Attack / Defend** (per unit). Click **Attack ▾** or **Defend ▾**
  to open the list of concrete commands; the list pops up at the left/centre edge.
- **A click runs nothing.** It opens a terminal, shows the exact command, and runs
  it only after you press **ENTER and type your Ubuntu password** — every command.
- Green dots on the simplex = allowed; ringed dots = HELD. The **Command log**
  (right) narrates each action; **θ per unit** shows posture.

---

## 11 · The deliverable — the report
```sh
make report          # builds report.html from the audit log
```
Open `report.html`: summary tiles, the simplex with every action (green=passed,
red/amber=held), θ per unit, and the full audit table. This is her proof of what the
governed session did.

---

## 12 · Cleanup afterwards
```sh
make lab-down                                     # both machines
# on YOUR machine, if you don't want to keep them:
sudo deluser --remove-home margaret
sudo systemctl disable --now ssh
# on MARGARET's laptop, revert any defense you toggled (e.g. ufw disable,
# PasswordAuthentication yes, systemctl disable --now fail2ban) if you want.
```

---

### One-line summary to leave her with
*"Anyone can run nmap. The point is that a machine sat between me and the tools and
refused everything I wasn't allowed to do — and that a well-defended host refuses me
even when I am allowed."*
