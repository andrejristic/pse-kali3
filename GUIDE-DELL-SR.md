# PSE-Kali na Dell-u (16 GB) — hardverske operacije

Sve što traži pravu mašinu: lab cilj, pokretanje pravih alata, pravljenje
bootabilnog USB-a, i postavljanje web app-a online. Ovo radiš na Dell-u (offline
testovi + native GUI rade bilo gde; ovaj vodič je hardverska polovina).

Podrazumeva da je repo u `~/Desktop/pse-kali` i da si uradio osnovni setup
(`python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt`
i `./fetch_model.sh 7b`). Za to vidi RUNBOOK-16GB.md / GUIDE-SR.md.

---

## 1 · Docker lab (bezbedan cilj za gađanje)
Samostalan, namerno slab cilj na `10.10.10.0/24` (host `10.10.10.5`). To je ceo
autorizovani scope — legalan, offline, potrošan.

**Instaliraj Docker (jednom):**
```sh
sudo apt install -y docker.io docker-compose-plugin
sudo usermod -aG docker $USER      # pa se izloguj/uloguj da `docker` radi bez sudo
```
**Gore / dole:**
```sh
make lab-up          # build + start pse-lab-target (ssh:22, http:8000 sa crackable hash-om)
docker ps            # potvrdi da radi
make lab-down
```
**Zamke:** subnet `10.10.10.0/24` ne sme da se sudari sa tvojim pravim Wi-Fi/LAN-om
(ako se sudara, promeni ga u `lab/docker-compose.yml` **i** `config.yaml` zajedno).
Prvi build povlači `debian:stable-slim` (treba internet). Vreme: ~5 min prvi put.

## 2 · Pokreni swarm sa PRAVIM alatima
```sh
sudo apt install -y nmap tcpdump hashcat john openssh-client   # pravi binarni
make lab-up
python3 run_engagement.py --config config.yaml --execute       # model vozi prave alate na lab
make report                                                    # -> report.html deliverable
```
Ili vozi uživo iz native konzole i gledaj:
```sh
python3 monitor/pse_monitor_qt.py --backend gguf:models/qwen2.5-7b-instruct-q4.gguf --execute
```
**Napomena:** `--execute` pokreće prave binarne. Drži `config.yaml` scope na labu
(`10.10.10.0/24`) osim ako ga namerno, uz autorizaciju, ne proširiš.

## 3 · Napravi bootabilni USB („AI-Kali")
Pretvara postojeći live ISO u samostalan `pse-kali.iso` koji se boot-uje u governed
engagement.

**Treba:** root, `xorriso squashfs-tools rsync`, ~10–15 GB slobodnog diska, bazni
ISO (MX XFCE preporuka, ili Debian live), i fajl modela.
```sh
sudo apt install -y xorriso squashfs-tools rsync
# prvo skini MX-XFCE.iso, pa:
sudo packaging/build_image.sh \
  --iso MX-XFCE.iso --repo . \
  --model models/qwen2.5-7b-instruct-q4.gguf --out pse-kali.iso
# upiši na USB:
sudo dd if=pse-kali.iso of=/dev/sdX bs=4M status=progress oflag=sync   # ili balenaEtcher
```
**Zamke:** chroot `apt install` korak traži internet; model naduva ISO na ~5 GB+;
na cilju paziš na UEFI/Secure Boot; test-boot u VM-u (VirtualBox/GNOME Boxes) pre
nego što veruješ pravoj mašini. Vreme: ~30–60 min sa skidanjima.

## 4 · Postavi web app online (Hugging Face — besplatno)
Da otvoriš konzolu sa telefona ili bilo kog browsera (Dell hostuje ili samo push-uje;
build se dešava na HF-u).

```sh
# 1) push repo na GitHub
git init && git add . && git commit -m "pse-kali" && git branch -M main
git remote add origin https://github.com/<ti>/pse-kali.git && git push -u origin main
# 2) huggingface.co -> New Space -> SDK: Docker -> poveži/push ovaj repo
#    HF build-uje root Dockerfile i servira na portu 7860 -> javni URL
```
**Bezbedno + živo:**
- Ide u **demo režim** (bez pravih alata) — ispravno za javno.
- Postavi token da nije otvoren celom svetu: Space **Settings → Variables/secrets**
  → `PSE_TOKEN` = tajna; pa otvori `https://<space>.hf.space/?t=<tajna>`.
- Za živ demo dodaj `PSE_BACKEND=claude:claude-opus-4-8` + secret
  `ANTHROPIC_API_KEY` (otkomentariši `pip install anthropic` u Dockerfile-u).
Pun vodič: `webapp/GUIDE-HOSTING-SR.md`.

---

## Troubleshooting
| Simptom | Rešenje |
|---|---|
| `docker: permission denied` | `sudo usermod -aG docker $USER`, pa re-login |
| sudar lab subneta | promeni `10.10.10.0/24` u `lab/docker-compose.yml` **i** `config.yaml` |
| `--execute` ne nađe ništa | instaliraj prave binarne (`nmap tcpdump hashcat`) |
| ISO build: `missing tool` | `sudo apt install xorriso squashfs-tools rsync` |
| ISO neće da boot-uje | ugasi Secure Boot na cilju; ponovo upiši USB; testiraj u VM-u prvo |
| HF Space build pada | proveri da je root `Dockerfile` prisutan; čitaj build logove Space-a |

## Šta gde radi
| Zadatak | Treba Dell? |
|---|---|
| offline testovi (`make test`), native GUI, report | ne (bilo koja mašina) |
| Docker lab + pravi alati (`--execute`) | **da** (Docker) |
| pravljenje bootabilnog ISO-a | **da** (root + disk) |
| deploy web app na HF | tvoji nalozi (build ide na HF) |
