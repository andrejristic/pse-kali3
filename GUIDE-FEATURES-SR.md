# PSE-Kali — Vodič za nove features

Pet dodataka na governed konzolu. Sve ovde radi lokalno bez dodatnog hardvera
(offline / `--backend mock` takođe).

## 1 · Izveštaj o angažmanu — deljiv deliverable
Posle runa, pretvori audit log u jedan samostalan, štampiv HTML izveštaj:
```sh
python3 report.py                 # -> report.html   (ili: make report)
python3 report.py --audit audit/engagement.jsonl --out klijent_izvestaj.html
```
Sadrži: summary pločice (akcije / prošlo / zadržano / jedinice), Care-invariant
simpleks sa svakom akcijom, **posturu po jedinici sa θ**, listu zadržanih/eskaliranih,
i punu audit tabelu. Otvori `report.html` u browseru ili štampaj u PDF — čist pentest
deliverable, reproducibilan iz audit loga.

## 2 · θ uživo — teorija, vidljiva
Svaki monitor (native GUI, web konzola) sad pokazuje **θ po jedinici** ispod simpleksa.
- **θ = other/w_o udeo** poslednje prošle akcije jedinice (PSE θ, mapiran u naše
  3-way stanje).
- **Boja:** zelena (θ<15) zdravo · amber (15–30) pazi · crvena (>30) ide ka
  **Codependent**. U ovom security režimu *nizak* θ (malo kapitulacije) je zdrav —
  suprotno kliničkom režimu, gde je ~30% optimalno.
- Osvežava se uživo dok jedinice deluju; izveštaj (feature 1) pokazuje srednji θ runa.

## 3 · Panel autorizovanog scope-a + web token
**Proširenje scope-a** je jedina stvar koju komandant ne sme — samo ti, namerno,
i uvek se loguje.
- **Native GUI / web konzola:** panel *Authorized scope* pokazuje trenutni scope;
  ukucaš metu (npr. `10.10.10.9/32`) i klikneš **Authorize** → kernelov floor je sad
  dozvoljava, a `scope_change` linija ide u audit.
- **Nikad** ne širi scope na nešto što nisi autorizovan da testiraš.

**Web token (za javni hosting):** zaštiti hostovan server da nije otvoren svima:
```sh
PSE_TOKEN=tvoja-tajna python3 webapp/server.py     # ili postavi PSE_TOKEN u host secrets
# pa otvori:  http://<host>/?t=tvoja-tajna
```
Bez tokena stranica se učita ali API vraća 401 — niko ne može da ga vozi.
(Na Hugging Face: Space Settings → dodaj `PSE_TOKEN` kao secret.)

## 4 · Mission presets + živa aktivnost
- **Preset dugmad** (native GUI + web konzola): **Full · Recon · Passive · Stop all**
  — jedan klik trenutno re-taskuje jedinice (bez modela). *Passive* = samo recon +
  sniffer (bez krekovanja, bez pristupa); *Stop all* uspava sve.
- **Živa aktivnost:** svaka akcija jedinice sad ide u **Command log**
  (`recon ✓ nmap 10.10.10.5`, `⛔ … DENIED`, eskalacije) pa gledaš engagement kako
  se pomera rečima, ne samo na simpleksu.

## 5 · Attack / Defend panel — praktično, po alatu (native GUI)
Leva kolona dodaje **Attack** i **Defend** meni za svaku jedinicu
(recon · password · sniff · access) — nastavna površina za čas uživo.
- **Attack ▾** izlistava konkretne governed komande (npr. `nmap -sV → lab`, i isto
  na `8.8.8.8` da gledaš kako ga kernel **HELD**-uje van scope-a).
- **Defend ▾** izlistava odgovarajuću protivmeru: recon→`ufw` (sakrij portove),
  password→jaka lozinka, sniff→enkripcija (napomena), access→ssh key-only / `fail2ban`.
- **Konzola sama ništa ne pokreće.** Klik otvori terminal, pokaže tačnu komandu,
  a izvršava se tek kad pritisneš **ENTER i uneseš svoju Ubuntu lozinku** — svaka
  komanda, bez izuzetaka (`sudo -k` briše svaki keširan kredencijal).
- Lista iskoči na granici levo↔centar; rezultat i dalje ide u audit log / simpleks
  kao svaka druga akcija.
- **Mete:** izmeni `LAB` i `PEER` na vrhu `monitor/pse_monitor_qt.py` — `PEER` je IP
  *druge* mašine za ssh lekciju (tvoja za Smer A, Margaretina za Smer B). Treba
  terminal emulator (`gnome-terminal`, podrazumevano prisutan).

---

### Brzi pregled
| Feature | Gde | Kako |
|---|---|---|
| Izveštaj | CLI | `make report` → `report.html` |
| θ readout | GUI + web | ispod simpleksa, uživo |
| Proširenje scope-a | GUI + web | *Authorized scope* → Authorize (logovano) |
| Web token | hosting | `PSE_TOKEN=…` + `?t=…` |
| Presets | GUI + web | Full / Recon / Passive / Stop all |
| Activity log | GUI + web | Command log |
| Attack / Defend | GUI (native) | leva kolona → Attack ▾ / Defend ▾ (kroz lozinku) |
