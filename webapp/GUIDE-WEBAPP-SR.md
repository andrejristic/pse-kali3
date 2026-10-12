# PSE-Kali Web Konzola — Uputstvo

Ista governed konzola kao native aplikacija, ali u **browseru** — pa je koristiš
sa bilo kog uređaja (laptop, telefon), i možeš je hostovati da i drugi mogu.
Mali Python server vozi živi swarm; stranica je front-end.

## Pokretanje lokalno
```sh
cd pse-kali
pip install pyyaml                       # kernel je stdlib; ovo je za config
python3 webapp/server.py --backend mock  # demo (ne pokreće alate) — bezbedno
# otvori http://localhost:8420 u browseru
```
Backend-i (isti svuda):
```sh
python3 webapp/server.py --backend gguf:models/qwen2.5-7b-instruct-q4.gguf
python3 webapp/server.py --backend claude:claude-opus-4-8      # treba ANTHROPIC_API_KEY
PSE_EXECUTE=1 python3 webapp/server.py --backend gguf:...      # PRAVI alati, SAMO LOKALNI LAB
```
> Ova mašina („Moj") nema instaliran browser. Ili instaliraj jedan
> (`sudo apt install firefox-esr`) pa otvori `localhost:8420`, ili koristi
> **native** aplikaciju (`monitor/pse_monitor_qt.py`), ili je **hostuj**
> (vidi hosting uputstvo) pa otvori javni URL sa telefona.

## Šta vidiš
- **Command** — pričaš s komandantom običnim jezikom:
  *„fokusiraj recon na 10.10.10.5, ugasi sniffer, krekuj samo md5."* On uživo
  re-taskuje jedinice. Sme samo da **suzi** unutar autorizovanog scope-a —
  nikad da ga proširi.
- **Approvals** — judgment hold (over-reach, borderline) čeka ovde za
  **Approve / Deny**. Van-scope akcija (floor) piše **denied** u audit-u i ne
  može se odobriti klikom.
- **Local model** — dropdown `.gguf` fajlova iz `./models`; izaberi i **Switch**
  da prebaciš model usred runa (ima smisla samo kad je backend lokalni model).
- **Simpleks + audit stream** — četiri jedinice uživo, i svaka skorovana akcija.

## Režimi
- **Demo režim** (podrazumevano, `--backend mock` ili API backend, bez
  `PSE_EXECUTE`): ništa se ne izvršava na mašini — prikazuje governance i UI.
  Ovo je režim za javni hosting.
- **Pravi režim** (`PSE_EXECUTE=1`, samo lokalno): pokreće prave alate protiv
  lab cilja na `10.10.10.0/24`. Nikad ovo na javnom serveru.

## API (ako hoćeš da skriptuješ)
`GET /events` · `GET /log?since=N` · `GET /escalations` · `GET /models` ·
`POST /command {text}` · `POST /escalation {id,decision}` · `POST /switch {path,fits}`.
