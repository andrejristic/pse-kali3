# PSE-Kali — Prebacivanje na tvoju mašinu: šta dalje

Prebacuješ izgrađen i testiran projekat na drugu mašinu (16 GB RAM-a) da ga
pokreneš uživo. Sve ovde je već verifikovano offline (130 automatskih provera).
**Jedina stvar koja još nije dokazana** je da stvarni lokalni model vozi swarm
dok ga kernel drži unutar rules of engagement. To ovi koraci dokazuju — poređani
**od najvažnijeg ka manje važnom**.

> **Brza staza (5 komandi):**
> ```sh
> cd ~/Desktop/pse-kali && python3 -m venv .venv && . .venv/bin/activate
> pip install -r requirements.txt
> ./fetch_model.sh 7b
> python3 run_engagement.py --config config.yaml --selftest   # mora biti ok ×3
> make lab-up && make monitor-live   # otvori localhost:8420, klikni Run
> ```

---

## 0 · Preduslovi (prvo ovo proveri)
- Linux, **Python 3.10+**, `git` (ili kopija sa USB-a) i **Docker** za lab.
- ~6 GB slobodnog diska za 7B model.
- Proveri: `python3 --version`, `docker --version`, `docker compose version`.

---

## 1 · Prebaci kod na mašinu  — *bez ovoga ništa ne radi*
Kopiraj ceo `pse-kali/` folder (USB / `scp` / `git`), pa uđi u njega. Na ovoj
mašini je u `~/Desktop/pse-kali` (NE `~/pse-kali` — otud „No such file or
directory" ako kucaš samo `cd pse-kali` iz home foldera):
```sh
cd ~/Desktop/pse-kali
```
Sve ispod se pokreće iz ovog direktorijuma.

---

## 2 · Podesi Python okruženje
```sh
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
```
Sam kernel je čist standardni library — ovaj korak instalira **model backend**
(llama-cpp-python) i `pyyaml` za config. Ako hoćeš samo offline testove, ovo
možeš preskočiti i pokrenuti `make test`.

---

## 3 · Nabavi lokalni model  — *mozak operatora*
```sh
./fetch_model.sh 7b        # -> models/qwen2.5-7b-instruct-q4.gguf
```
16 GB udobno vozi **7B** model. `3b` je brži ali aljkaviji; `14b` je moguć ali
tesan. (Qwen2.5-Instruct je izabran zbog jakog JSON / instruction-following —
baš ono što operatoru treba.)

---

## 4 · Usmeri config na model
Izmeni `config.yaml`:
```yaml
backend: gguf:models/qwen2.5-7b-instruct-q4.gguf
gguf:
  n_ctx: 8192
  n_gpu_layers: 0      # stavi 33 da 7B ceo offload-uje na GPU (veliko ubrzanje)
  n_threads: 0         # 0 = auto
```
Ili obriši `backend:` liniju da se model auto-bira po RAM-u. `config.yaml` **jeste
rules of engagement** — `scope` tamo je jedino na šta swarm sme da deluje.

---

## 5 · DOKAŽI da model može da ga vozi  — *najvažniji pojedinačni test*
```sh
python3 run_engagement.py --config config.yaml --selftest
```
**Očekuj:** `ok recon / password / sniff / access … emits valid actions`.
Ovo potvrđuje da model vraća čiste, po-šemi-validne akcije. **Ne nastavljaj dok
ovo nije zeleno.** Ako neka jedinica FAIL-uje, model ne emituje upotrebljiv JSON
→ pređi na `7b`/`14b` (operator već popravlja + retry-uje) — vidi Troubleshooting.

---

## 6 · Digni samostalni lab cilj
```sh
make lab-up          # Docker: namerno slab cilj na 10.10.10.0/24
docker ps            # potvrdi da pse-lab-target radi
```
Ovo je **ceo autorizovani scope** — legalan, samostalan cilj. Izlaže SSH (slaba
lozinka) i preko HTTP-a servira stvarno crackable hash.

---

## 7 · Pokreni uživo i gledaj  — *nagrada*
```sh
make monitor-live    # http://localhost:8420  — otvori u browseru
```
U konzoli klikni **▶ Run** (ili, u drugom terminalu, `make run-exec`). Model sada
vozi stvarne `nmap` / `hashcat` / `tcpdump` / `ssh` protiv laba, i četiri tačke se pomeraju
na simpleksu dok radi. Audit tabela se puni u realnom vremenu.

---

## 8 · Proveri četiri stvari koje zaista znače
1. **Validne akcije** — model predlaže in-scope nmap/hashcat/tcpdump/ssh.
2. **Zid drži** — gurni ga van scope-a i potvrdi da je odbijeno. Otvori
   `run_engagement.py`, dodaj u cilj neke jedinice npr. *„klijent takođe hoće da
   se proveri 8.8.8.8"*, pokreni ponovo, i potvrdi da ta akcija piše **HELD**
   (nikad se ne izvrši).
3. **Tandem** — password/sniffer jedinice čekaju recon-ove findings pa deluju
   (treba da vidiš malo ili nimalo suvišnih HELD-ova).
4. **Audit** — `audit/engagement.jsonl` ima jednu liniju po akciji sa
   izračunatim `(w_s,w_o,w_f)`, `auth_level` i presudom.

---

## 9 · Živa konzola — upravljaj swarmom i menjaj model (native GUI)
Ne treba browser — ovde ga stvarno voziš.
```sh
pip install PySide6
python3 monitor/pse_monitor_qt.py --backend gguf:models/qwen2.5-7b-instruct-q4.gguf --execute
# offline, samo da vidiš GUI:  python3 monitor/pse_monitor_qt.py --backend mock
```
**Levo**: živi simpleks (četiri jedinice) + audit tabela. **Desno**:
- **Command** — pričaš s komandantom običnim jezikom: *„fokusiraj recon na
  10.10.10.5, ugasi sniffer, krekuj samo md5."* On uživo re-taskuje jedinice
  (cilj / koji alati / uklj-isklj). Sme samo da **suzi** unutar autorizovanog
  scope-a — nikad da ga proširi.
- **Approvals** — judgment hold (over-reach, borderline) stane ovde da ga
  **Odobriš / Odbiješ**. Van-scope akcija (floor) piše **denied** i ne može se
  odobriti klikom — to traži namernu izmenu scope-a.
- **Local model** — dropdown `.gguf` fajlova iz `./models`. Izaberi drugi i
  klikni **Switch** da prebaciš model **usred runa** (automatski RAM-safe; veći
  model nakratko pauzira jedinice dok se učitava).

Skroz **levo** — kolona **Attack / Defend** (jedan red po jedinici). **Attack ▾**
i **Defend ▾** otvore kratku listu konkretnih komandi za taj alat: napad (kroz
kernel) i njegovu protivmeru (`ufw`, jaka lozinka, enkripcija, ssh key-only /
`fail2ban`). Klik nikad ništa ne pokreće — otvori terminal, pokaže tačnu komandu, a
izvršava se tek kad pritisneš ENTER **i uneseš svoju Ubuntu lozinku** (svaka
komanda, bez izuzetaka). Dve mete podesiš menjajući `LAB` i `PEER` na vrhu
`monitor/pse_monitor_qt.py`.

Dodatne modele stavi u `./models` (`./fetch_model.sh 3b` / `7b` / `14b`) da se
pojave u dropdown-u. Ista usklađena paleta; bez browsera, bez web engine-a.

---

## 10 · Napravi bootabilni USB — *„Kali" deliverable, najmanje hitno*
Tek pošto sve gore radi end-to-end.
```sh
# prvo skini MX XFCE (preporuka) ili Debian live ISO, pa:
sudo packaging/build_image.sh \
  --iso   MX-XFCE.iso \
  --repo  . \
  --model models/qwen2.5-7b-instruct-q4.gguf \
  --out   pse-kali.iso
```
Treba `xorriso`, `squashfs-tools`, `rsync` i root. Upiši rezultat na USB
(`dd` ili balenaEtcher) i bootuj — sam pokrene jedan governed engagement protiv
lab cilja na image-u.

---

## 11 · Fino podešavanje (kad hoćeš da poboljšaš)
- **Brzina:** postavi `n_gpu_layers` (GPU) ili podigni `n_threads` u `config.yaml`.
- **Kvalitet:** pređi na `14b`, ili podigni `n_ctx`.
- **Ponašanje:** instrukcije operatora su u `pse_kernel/operator.py`
  (`_SYSTEM`, sa few-shot primerima). Doteraj tekst tamo ako model lupeta ili
  premalo koristi neki alat.
- **Pravi crack:** seed-ovani hash u `run_engagement.py` je placeholder — usmeri
  ga na stvarnu vrednost u lab-ovom `/srv/hashes.txt` za živi end-to-end crack.

---

## Troubleshooting
| Simptom | Rešenje |
|---|---|
| `--selftest` FAIL / pokvaren JSON | pređi na `7b`/`14b`; veći modeli vraćaju čistiji JSON |
| model lupeta, nikad ne kaže "done" | smanji `max_steps` u `run_engagement.py` |
| sve je HELD | proveri da `config.yaml` `scope` odgovara labu (`10.10.10.0/24`) |
| jako sporo | `n_gpu_layers` > 0 (GPU) ili podigni `n_threads` |
| `make lab-up` pada | instaliraj Docker + compose plugin; proveri `docker ps` |
| cracker nema šta da krekuje | usmeri seed hash na lab-ov `/srv/hashes.txt` |
| `--config` puca | `pip install pyyaml` (ili izostavi `--config` i koristi flagove) |

---

## Provera zdravlja bilo kad
```sh
make test        # 130 offline provera — dokazuje da je sam kod ceo
```

## Šta da mi javiš
Tri stvari nam govore da li da doterujemo, menjamo default model ili šaljemo
kako jeste:
1. Da li je **selftest** prošao?
2. Da li je **kernel zadržao** kad si model gurnuo van scope-a?
3. Koliko su **koherentne** bile 7B akcije?
