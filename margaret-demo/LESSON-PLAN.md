# Lesson Plan — Margaret's First Governed Pentest

A hands-on, terminal-only class. Margaret uses PSE-Kali to exercise **all four
tools** — recon, password cracking, sniffing, and access — each against an
**authorized** target, and each time she watches the tool **refuse** anything
outside the rules. Ends with her leaving a `margaret was here` file on your real
machine.

**Assumes:** she can use a terminal (copy-paste commands, read output). Nothing
more. No model needed — every lesson is one `run_action.py` command.

**Why this is legal:** the lab target runs on *her own laptop*, and the one real
machine she touches (Lesson 4) is *yours*, on *your* Wi-Fi, with *your* written
permission, *you present*. Outside that, the exact same commands are a crime —
say this first, and often.

**Time:** ~60 min. **Teacher:** you (Andrej).

---

## The one pattern she needs to learn
Every lesson is the same shape:
```sh
python3 run_action.py  <UNIT>  <TOOL>  <TARGET>  [options]  --config config.yaml --execute
```
- `<UNIT>` is one of **recon · password · sniff · access**
- The **kernel scores every command** and either runs it (`✅ ALLOWED`) or blocks
  it (`⛔ HELD`). She never has to judge safety — the tool does.
- Drop `--execute` to see the verdict *without* running anything (a dry run).

She'll type four of these. That's the whole class.

---

## Part 0 · Setup — you do this before she arrives
On **Margaret's laptop** (she'll operate from here):
```sh
# 1. the code + deps (no model needed)
cd ~/Desktop/pse-kali
python3 -m venv .venv && . .venv/bin/activate
pip install pyyaml
sudo apt install -y nmap tcpdump hashcat openssh-client curl docker.io docker-compose-plugin

# 2. the practice target (a safe, weak box on her own laptop)
sudo usermod -aG docker $USER      # then log out/in once
make lab-up                        # target at 10.10.10.5 (ssh + http with a crackable hash)
curl -s http://10.10.10.5:8000/hashes.txt    # should print a $1$... hash

# 3. let tcpdump capture without sudo (for Lesson 3)
sudo setcap cap_net_raw+ep $(which tcpdump)

# 4. copy the demo wordlist (contains the lab password) into place (for Lesson 2)
cp margaret-demo/words.txt .

# 5. key access to YOUR machine (for Lesson 4) — do this from her laptop
ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519      # a key, no passphrase
ssh-copy-id margaret@<YOUR-IP>                        # type your machine's margaret password ONCE
```
On **your machine** (the Lesson 4 target), beforehand:
```sh
sudo apt install -y openssh-server && sudo systemctl enable --now ssh
sudo adduser margaret            # give it a password (used once, by ssh-copy-id)
hostname -I                      # note YOUR-IP, e.g. 192.168.1.50
```
Finally, set the **rules of engagement** — copy the demo config and put your
machine's IP in it (the two authorized targets are the lab and your machine):
```sh
cp margaret-demo/config.demo.yaml config.yaml     # then edit YOUR-IP inside it
```

---

## Lesson 1 · RECON — "See what's running" (nmap) · ~12 min
**Goal:** discover which services are open on the target.
```sh
python3 run_action.py recon nmap 10.10.10.5 --args="-sV" \
    --rationale "enumerate services in scope" --config config.yaml --execute
```
**What she sees:** `✅ ALLOWED`, then findings listing **port 22 (ssh)** and
**port 8000 (http)** open, with version banners. (`-sV` = "tell me the versions".)

**Now hit the wall** — try to scan something you were NOT authorized to:
```sh
python3 run_action.py recon nmap 8.8.8.8 --args="-sV" \
    --rationale "just curious" --config config.yaml --execute
```
→ `⛔ HELD — unauthorized`. 8.8.8.8 (a Google server) isn't in scope, so the
kernel makes it **unreachable** — it never runs.

**What she learned:** recon = *discovery*; the tool only ever scans what you're
explicitly authorized to.

---

## Lesson 2 · PASSWORD — "Crack a weak password" (hashcat) · ~15 min
**Goal:** recover a password from the hash the target exposes.
```sh
# grab the hash the box is leaking over HTTP
HASH=$(curl -s http://10.10.10.5:8000/hashes.txt); echo "$HASH"

# crack it (mode 500 = md5crypt) using our wordlist
python3 run_action.py password hashcat 10.10.10.5 --artifact "$HASH" \
    --args="-m 500 words.txt" \
    --rationale "credential audit in scope" --config config.yaml --execute
```
**What she sees:** `✅ ALLOWED`, hashcat runs and cracks it — the password
**`hunter2`** appears in the output. *(If hashcat says "found in potfile", re-run
the same line with `--args="-m 500 words.txt --show"` to reveal it.)*

**Now hit the wall** — try to crack a hash for an out-of-scope target:
```sh
python3 run_action.py password hashcat 8.8.8.8 --artifact "$HASH" \
    --args="-m 500 words.txt" --rationale "x" --config config.yaml --execute
```
→ `⛔ HELD — unauthorized`.

**What she learned:** cracking recovers weak passwords fast — which is exactly why
weak passwords are dangerous — and the tool ties every crack to an authorized
target.

---

## Lesson 3 · SNIFF — "Watch the traffic" (tcpdump) · ~12 min
**Goal:** capture packets going to/from the target.

Open **two terminals**. In the **first**, start the capture:
```sh
python3 run_action.py sniff tcpdump 10.10.10.5 \
    --rationale "traffic analysis in scope" --config config.yaml --execute
```
It waits for up to 50 packets on the target. In the **second terminal**, make some
traffic so there's something to see:
```sh
ping -c 20 10.10.10.5
```
**What she sees:** back in the first terminal, `✅ ALLOWED` and a finding with the
number of **packets captured**. (`tcpdump` is a wiretap for network traffic; here
it only listens to the one authorized host.)

**Now hit the wall:**
```sh
python3 run_action.py sniff tcpdump 8.8.8.8 \
    --rationale "x" --config config.yaml --execute
```
→ `⛔ HELD — unauthorized`.

**What she learned:** sniffing reads traffic off the wire; the tool confines it to
the host you're authorized to watch.

---

## Lesson 4 · ACCESS — "Get in and leave your mark" (ssh) · ~15 min
**Goal:** log into *your real machine* (authorized) and drop a proof file.
```sh
python3 run_action.py access ssh <YOUR-IP> --user margaret \
    --command 'echo "margaret was here" > ~/margaret_was_here.txt' \
    --rationale "authorized marker" --config config.yaml --execute
```
**What she sees:** `✅ ALLOWED` — the tool SSHes in (using the key from setup) and
writes the file. **You verify** on your machine:
```sh
cat /home/margaret/margaret_was_here.txt        # -> margaret was here
```
🎉 She got in and left proof.

**Now hit the wall — twice:**
```sh
# a destructive command — over-reach
python3 run_action.py access ssh <YOUR-IP> --user margaret \
    --command 'rm -rf /' --rationale "authorized" --config config.yaml --execute
# an out-of-scope machine
python3 run_action.py access ssh 8.8.8.8 --user margaret \
    --command 'echo hi' --rationale "x" --config config.yaml --execute
```
→ both `⛔ HELD` (the first as **narcissistic** over-reach, the second on the
**floor**). Even with a real login on your box, it refuses to do damage or to
wander off-target.

**What she learned:** access = doing the smallest authorized thing that proves the
point — never destruction, never a machine you weren't given.

---

## Part 5 · See everything she did (the report) · ~5 min
```sh
make report        # builds report.html from everything above
```
Open `report.html` in a browser. Show her:
- the **summary** (how many actions passed, how many the kernel held),
- the **simplex** — every command she ran is a dot; the green ones passed, the
  red/amber ones were held,
- **θ per unit** — how much each tool leaned toward "the other" vs staying on task.

One sentence to leave her with: *"The point isn't the tools — anyone can run nmap.
The point is that a machine sat between me and the tools and refused everything I
wasn't allowed to do."*

## Part 6 · Clean up
```sh
make lab-down                                   # on her laptop
# on YOUR machine:
sudo deluser --remove-home margaret
sudo systemctl disable --now ssh                # if you don't keep SSH on
```

---

## Cheat sheet (hand her this)
| Do | Command (…`--config config.yaml --execute`) |
|---|---|
| Discover services | `run_action.py recon nmap 10.10.10.5 --args="-sV"` |
| Crack a hash | `run_action.py password hashcat 10.10.10.5 --artifact "$HASH" --args="-m 500 words.txt"` |
| Sniff traffic | `run_action.py sniff tcpdump 10.10.10.5` (+ `ping 10.10.10.5` in another terminal) |
| Get in, leave a mark | `run_action.py access ssh <YOUR-IP> --user margaret --command '…'` |
| Test the wall | run any of them against `8.8.8.8` → HELD |

Every command starts with `python3 `. Green = it ran. Red = the kernel stopped it.
