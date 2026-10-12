# PSE-Kali — Runbook za čas (dvosmerni napad ↔ odbrana sa Margaret)

Kompletna, redosledna lista za pripremu i vođenje časa uživo, gde se demonstriraju
**oba smera** na dve prave mašine, plus lab lekcije. Radi korake odozgo nadole.
Svaki korak kaže **na kojoj mašini** se pokreće.

- **Tvoja mašina** — Ubuntu 24.04, korisnik `a`, IP **`10.0.0.109`** (OptiPlex).
  Uloga: pokreće lab lekcije, **meta** je u Smeru A, i **napadač** u Smeru B.
- **Margaretin laptop** — Ubuntu, IP `<MARGARET-IP>` (upiši ispod). Uloga:
  **napadač** u Smeru A, **branilac/meta** u Smeru B.

Sve je autorizovano: obe mašine su naše, na našoj Wi-Fi mreži, uz prisustvo vlasnika.
Van toga, iste komande su krivično delo — reci to prvo, i često.

---

## 0 · Slika — šta demonstriramo
1. **Lab lekcije 1–3** (recon · password · sniff) protiv bezbedne Docker „vežbaonice"
   koja radi lokalno. Uči alate i **kernel zid** (meta van scope-a je odbijena —
   **HELD**).
2. **Smer A — Margaret → tvoja mašina (nebranjena).** Uđe preko SSH i ostavi
   `margaret was here` na Desktopu. Dokazuje da može da uđe kad je host otvoren **i**
   kad je u scope-u.
3. **Smer B — ti → Margaretina mašina (branjena).** Kernel *dozvoli* (njena IP je u
   scope-u, autorizovan si), ali je njen **utvrđeni host odbije**. To je drugi,
   drugačiji zid: čak i autorizovanu akciju zaustavlja dobra odbrana.

Dva zida, učena odvojeno: **kernel** (scope) i **host** (hardening).

---

## 1 · Potvrdi instalacije (rekapitulacija)
**Tvoja mašina** — trebalo bi već gotovo. Provera:
```sh
for t in nmap hashcat john docker sshd ssh tcpdump curl python3; do \
  command -v $t >/dev/null && echo "OK $t" || echo "FALI $t"; done
python3 -c "import PySide6" && echo "OK PySide6"
systemctl is-active ssh              # -> active
id margaret                          # -> postoji
sudo test -d /home/margaret/Desktop && echo "OK margaret Desktop"
```
**Margaretin laptop** — ona odradi `margaret-demo/INSTALL-MARGARET-EN.txt` i Step 6
u njemu mora pokazati sve **OK**. Nek ti pošalje taj ekran.

---

## 2 · Uzmi obe IP
- **Tvoja mašina:** `10.0.0.109` (potvrdi: `hostname -I`).
- **Margaretin laptop:** `hostname -I` na njenom laptopu → upiši ovde: `<MARGARET-IP>`.

Obe su na istoj Wi-Fi mreži, pa obe izgledaju kao `10.0.0.x`.

---

## 3 · Pravila angažmana — `config.yaml` (uradi na OBE mašine)
Ovaj fajl **JESTE** autorizovani scope. Mora da izlista lab **i obe mašine**, tako da
je svaki pravi napad *dozvoljen od kernela* — da bi Smer B zaustavila jedino
Margaretina odbrana, a ne zid.
```sh
cd ~/Desktop/pse-kali3
cp margaret-demo/config.demo.yaml config.yaml
```
Zatim izmeni `config.yaml` da glasi (stavi PRAVE IP):
```yaml
scope:
  - 10.10.10.0/24          # Docker lab (lekcije 1-3)
  - 10.0.0.109/32          # tvoja mašina
  - <MARGARET-IP>/32       # Margaretin laptop
authorizations:
  - target_scope: [10.10.10.0/24, 10.0.0.109/32, <MARGARET-IP>/32]
    tools: [nmap, hashcat, john, tcpdump, tshark, ssh]
```
Uradi **istu izmenu na Margaretinom laptopu** (njena kopija repoa).

> Ako meta NIJE u scope-u, kernel je HELD-uje (zid) i nikad ne stigneš do host
> odbrane. Za lekciju Smer B, njena IP **mora** biti u scope-u.

---

## 4 · Uperi GUI ka drugoj mašini (`LAB` + `PEER`)
Attack/Defend meniji native konzole koriste dve promenljive na vrhu
`monitor/pse_monitor_qt.py`:
```python
LAB  = "10.10.10.5"     # docker lab meta — ostavi ovako
PEER = "PEER-IP"        # IP DRUGE mašine za ssh lekciju
```
- **Na tvojoj mašini:** stavi `PEER = "<MARGARET-IP>"` (ti gađaš nju — Smer B).
- **Na Margaretinom laptopu:** stavi `PEER = "10.0.0.109"` (ona gađa tebe — Smer A).

---

## 5 · Poveži Smer A — Margaret u tvoju mašinu
Tvoja mašina je već meta (sshd radi, `margaret` korisnik, Desktop folder). Njoj treba
samo ključ kome tvoja mašina veruje.

**Na Margaretinom laptopu:**
```sh
ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519      # ključ, bez lozinke
ssh-copy-id margaret@10.0.0.109                        # ukucaj margaret lozinku JEDNOM
ssh margaret@10.0.0.109 'echo radi'                    # treba da ispiše: radi
```
(Ako Desktop folder fali, na **tvojoj** mašini:
`sudo mkdir -p /home/margaret/Desktop && sudo chown margaret:margaret /home/margaret/Desktop`.)

---

## 6 · Poveži Smer B — odbrani Margaretinu mašinu
Izaberi jedan ili više od četiri. Preporuka: **key-only + fail2ban.** Sve komande se
pokreću **na Margaretinom laptopu.**

**a) SSH samo-ključ (isključi lozinke)** — tvoj pokušaj lozinkom se odbije.
```sh
sudo sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo systemctl restart ssh
# vidiš:  Permission denied (publickey)
```
**b) fail2ban (ban za ponovljene pokušaje)** — posle par pokušaja tvoja IP je banovana.
```sh
sudo apt install -y fail2ban
sudo systemctl enable --now fail2ban
sudo fail2ban-client status sshd
# vidiš: prvi pokušaji odbijeni, pa Connection timed out (banovan)
```
**c) UFW firewall (zatvori/ograniči port)** — ni ne stigneš do login-a.
```sh
sudo ufw enable
sudo ufw deny 22          # ili: sudo ufw limit 22   (rate-limit umesto blokade)
# vidiš: Connection refused / timed out
```
**d) Jaka lozinka (bez izmene configa)** — daj njenom nalogu dugačku lozinku koju ne
znaš; wordlist/pogađanje pukne sa `Permission denied`.

> Ovo su tačno i **Defend ▾** dugmad u GUI-ju — možeš ih primeniti uživo pred njom
> (svako traži Ubuntu lozinku).

---

## 7 · Lab meta (lekcije 1–3) — na svakoj mašini koja te lekcije radi
```sh
cd ~/Desktop/pse-kali3
cp margaret-demo/words.txt .          # wordlista koja sadrži lab lozinku
make lab-up                           # podigne 10.10.10.5 (ssh + http hash)
docker ps                             # potvrdi da pse-lab-target radi
curl -s http://10.10.10.5:8000/hashes.txt   # treba da ispiše $1$... hash
```

---

## 8 · Čist start za izveštaj
Da finalni `report.html` pokaže samo ono što je Margaret uradila:
```sh
make clean            # briše audit/*.jsonl i stari monitor snapshot
```

---

## 9 · Probni prolaz — dokaži PRE nego što dođe
**Lab verdikti (ne treba --execute, ništa se ne pokreće):** svaki ispiše verdikt.
```sh
python3 run_action.py recon nmap 10.10.10.5 --args="-sV" --rationale test --config config.yaml   # ALLOWED
python3 run_action.py recon nmap 8.8.8.8    --args="-sV" --rationale test --config config.yaml   # HELD (zid)
```
**Smer A uživo (sa Margaretinog laptopa):**
```sh
python3 run_action.py access ssh 10.0.0.109 --user margaret \
  --command 'echo "margaret was here" > ~/Desktop/margaret_was_here.txt' \
  --rationale "authorized marker" --config config.yaml --execute
```
Pa na **tvojoj** mašini: `cat /home/margaret/Desktop/margaret_was_here.txt` → marker.

**Smer B uživo (sa tvoje mašine):** gađaj njenu IP — kernel dozvoli, njena odbrana
odbije:
```sh
python3 run_action.py recon nmap <MARGARET-IP> --args="-sV" \
  --rationale "authorized scan" --config config.yaml --execute      # ALLOWED od kernela, ufw sakrije portove
python3 run_action.py access ssh <MARGARET-IP> --user margaret \
  --command 'echo hi' --rationale "authorized" --config config.yaml --execute  # ALLOWED od kernela, host odbije
```

---

## 10 · Vođenje časa — vizuelna konzola
```sh
cd ~/Desktop/pse-kali3
python3 monitor/pse_monitor_qt.py --backend mock       # da bezbedno pokažeš UI
python3 monitor/pse_monitor_qt.py --execute            # PRAVI alati (koristi config.yaml scope)
```
- **Leva kolona — Attack / Defend** (po jedinici). Klik **Attack ▾** ili **Defend ▾**
  otvori listu konkretnih komandi; lista iskoči na granici levo/centar.
- **Klik ništa ne pokreće.** Otvori terminal, pokaže tačnu komandu, i pokrene je tek
  kad pritisneš **ENTER i uneseš svoju Ubuntu lozinku** — svaka komanda.
- Zelene tačke na simpleksu = dozvoljeno; tačke sa prstenom = HELD. **Command log**
  (desno) opisuje svaku akciju; **θ po jedinici** pokazuje posturu.

---

## 11 · Deliverable — izveštaj
```sh
make report          # gradi report.html iz audit loga
```
Otvori `report.html`: summary pločice, simpleks sa svakom akcijom (zeleno=prošlo,
crveno/amber=zadržano), θ po jedinici, i puna audit tabela. To je njen dokaz šta je
governisani čas uradio.

---

## 12 · Čišćenje posle
```sh
make lab-down                                     # obe mašine
# na TVOJOJ mašini, ako ih ne želiš zadržati:
sudo deluser --remove-home margaret
sudo systemctl disable --now ssh
# na MARGARETINOM laptopu, vrati svaku odbranu koju si menjao (npr. ufw disable,
# PasswordAuthentication yes, systemctl disable --now fail2ban) ako želiš.
```

---

### Rečenica za kraj
*„Svako može da pokrene nmap. Poenta je da je mašina stala između mene i alata i
odbila sve što mi nije dozvoljeno — i da me dobro branjen host odbije čak i kad
jesam dozvoljen."*
