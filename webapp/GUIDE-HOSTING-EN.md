# PSE-Kali Web Console — Putting it on the internet (free hosting)

Host the governed console so anyone can open it in a browser. Ordered **most
important first**.

## 0 · Read this first — the safety rule
A public deployment runs in **DEMO MODE**: it demonstrates the governance and the
UI, it does **not** run real security tools.
- The shipped `Dockerfile` installs **no** attack binaries (no nmap/hashcat), uses
  the **mock** or an **API** backend, and never sets `PSE_EXECUTE`. Keep it that way.
- The authorized scope stays the lab (`10.10.10.0/24`). Never widen it on a host.
- Never put an API key in the code — always a host **secret** (below).

This is a governance demo, not an attack platform. That is also the only thing
that fits a free tier.

## 1 · Put the code in a Git repo — *most hosts pull from Git*
Create a **GitHub** repo and push the `pse-kali/` folder (the `Dockerfile` is at
its root):
```sh
cd pse-kali
git init && git add . && git commit -m "PSE-Kali web console"
git branch -M main
git remote add origin https://github.com/<you>/pse-kali.git
git push -u origin main
```

## 2 · Hugging Face Spaces — *recommended (free, 16 GB RAM, Docker)*
1. Sign up at **huggingface.co** → **New Space**.
2. Owner + name; **SDK = Docker** (blank); Public. Create.
3. Push your files into the Space's git repo (it shows the URL), or **Files →
   Upload** the folder including the root `Dockerfile`.
4. HF builds the `Dockerfile` and runs it. The app listens on **7860** (our
   default) — nothing to configure.
5. Open your Space URL: `https://<you>-<space>.hf.space`. Done — it's live.

Because HF free CPU gives 16 GB RAM, you can even run a small local model:
uncomment `pip install llama-cpp-python` in the `Dockerfile`, add the `.gguf`
to `models/`, and set `PSE_BACKEND=gguf:models/<file>.gguf` (slow on CPU but works).

## 3 · Make the demo lively — an API backend + a secret
`mock` shows the UI but the units don't do much. For a demo that actually moves,
use a cloud model (low RAM, fits any tier):
1. In the `Dockerfile`, uncomment `pip install anthropic` (or `mistralai`).
2. In the Space: **Settings → Variables and secrets**:
   - Variable `PSE_BACKEND` = `claude:claude-opus-4-8` (or `mistral:mistral-large-latest`)
   - Secret `ANTHROPIC_API_KEY` = your key (or `MISTRAL_API_KEY`)
3. Restart the Space. Now the commander + units are driven by the API.

## 4 · Render — *alternative (free web service)*
1. Push to GitHub (step 1). Sign up at **render.com**, connect GitHub.
2. **New → Web Service** → pick the repo. Render detects the `Dockerfile`.
3. Instance type: **Free**. Render provides `$PORT`; the server reads it.
4. **Environment** → add `PSE_BACKEND` + your key (as a secret env var).
5. Deploy → public `…onrender.com` URL. Note: the free tier **sleeps** when idle
   (~15 min) and wakes on the next request (first load is slow).
   Render free RAM (~512 MB) won't run a local model — use an **API** backend.

## 5 · Others (brief)
- **Fly.io** — `fly launch` on the Docker app; generous free allowance.
- **Railway** — deploy from GitHub (Docker); limited free hours.
Both deploy the same `Dockerfile`; set `PSE_BACKEND` + key as env/secrets.

## 6 · Caveats
- Free tiers sleep/idle and have limited RAM/CPU — fine for a demo, not for load.
- Secrets only via the host's secret store; never commit keys.
- Keep it demo mode: no `PSE_EXECUTE`, no real binaries, scope = the lab.

## Quickest path
GitHub push → Hugging Face **Docker** Space → (optional) add `PSE_BACKEND` +
API key secret → open the `.hf.space` URL.
