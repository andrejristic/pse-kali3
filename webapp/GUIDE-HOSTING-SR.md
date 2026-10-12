# PSE-Kali Web Konzola — Postavljanje na internet (besplatan hosting)

Hostuj governed konzolu da je svako otvori u browseru. Poređano **od najvažnijeg**.

## 0 · Prvo ovo — bezbednosno pravilo
Javni deployment ide u **DEMO REŽIM**: prikazuje governance i UI, **ne** pokreće
prave security alate.
- Priloženi `Dockerfile` **ne** instalira nikakve napadačke binarne (nema
  nmap/hashcat), koristi **mock** ili **API** backend, i nikad ne postavlja
  `PSE_EXECUTE`. Neka tako i ostane.
- Autorizovani scope ostaje lab (`10.10.10.0/24`). Nikad ga ne širi na hostu.
- Nikad API ključ u kodu — uvek kao host **secret** (dole).

Ovo je governance demo, ne napadačka platforma. To je i jedino što staje na
besplatan tier.

## 1 · Stavi kod u Git repo — *većina hostova povlači sa Git-a*
Napravi **GitHub** repo i push-uj `pse-kali/` folder (`Dockerfile` je u njegovom
korenu):
```sh
cd pse-kali
git init && git add . && git commit -m "PSE-Kali web console"
git branch -M main
git remote add origin https://github.com/<ti>/pse-kali.git
git push -u origin main
```

## 2 · Hugging Face Spaces — *preporuka (besplatno, 16 GB RAM, Docker)*
1. Registruj se na **huggingface.co** → **New Space**.
2. Owner + ime; **SDK = Docker** (prazan); Public. Create.
3. Push-uj fajlove u Space-ov git repo (prikaže URL), ili **Files → Upload**
   ceo folder uključujući `Dockerfile` u korenu.
4. HF build-uje `Dockerfile` i pokrene ga. App sluša na **7860** (naš default) —
   ništa da podešavaš.
5. Otvori Space URL: `https://<ti>-<space>.hf.space`. Gotovo — radi uživo.

Pošto HF besplatni CPU daje 16 GB RAM-a, možeš čak i mali lokalni model:
otkomentariši `pip install llama-cpp-python` u `Dockerfile`-u, dodaj `.gguf` u
`models/`, i postavi `PSE_BACKEND=gguf:models/<fajl>.gguf` (sporo na CPU ali radi).

## 3 · Oživi demo — API backend + secret
`mock` prikazuje UI ali jedinice ne rade mnogo. Za demo koji se stvarno pomera,
koristi cloud model (malo RAM-a, staje na svaki tier):
1. U `Dockerfile`-u otkomentariši `pip install anthropic` (ili `mistralai`).
2. U Space-u: **Settings → Variables and secrets**:
   - Variable `PSE_BACKEND` = `claude:claude-opus-4-8` (ili `mistral:mistral-large-latest`)
   - Secret `ANTHROPIC_API_KEY` = tvoj ključ (ili `MISTRAL_API_KEY`)
3. Restartuj Space. Sad komandant + jedinice voze preko API-ja.

## 4 · Render — *alternativa (besplatan web servis)*
1. Push na GitHub (korak 1). Registruj se na **render.com**, poveži GitHub.
2. **New → Web Service** → izaberi repo. Render prepozna `Dockerfile`.
3. Instance type: **Free**. Render daje `$PORT`; server ga čita.
4. **Environment** → dodaj `PSE_BACKEND` + tvoj ključ (kao secret env var).
5. Deploy → javni `…onrender.com` URL. Napomena: besplatni tier **spava** kad je
   neaktivan (~15 min) i budi se na sledeći zahtev (prvo učitavanje sporo).
   Render besplatni RAM (~512 MB) ne vozi lokalni model — koristi **API** backend.

## 5 · Ostali (kratko)
- **Fly.io** — `fly launch` nad Docker app-om; velikodušan besplatan tier.
- **Railway** — deploy sa GitHub-a (Docker); ograničeni besplatni sati.
Oba deploy-uju isti `Dockerfile`; postavi `PSE_BACKEND` + ključ kao env/secret.

## 6 · Ograničenja
- Besplatni tier-ovi spavaju i imaju malo RAM-a/CPU-a — ok za demo, ne za opterećenje.
- Secret-i samo preko host-ovog secret store-a; nikad ne commit-uj ključeve.
- Ostani u demo režimu: bez `PSE_EXECUTE`, bez pravih binarnih, scope = lab.

## Najbrža staza
GitHub push → Hugging Face **Docker** Space → (opciono) dodaj `PSE_BACKEND` +
API ključ secret → otvori `.hf.space` URL.
