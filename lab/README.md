# PSE-Kali Lab Target

A self-contained, intentionally-weak target for exercising the governed swarm.
It lives on the **exact subnet the engagement authorizes** — `10.10.10.0/24`,
target at `10.10.10.5` — so the kernel's scope is the whole world here. Nothing
reaches a real network.

## Bring it up / down
```sh
docker compose -f lab/docker-compose.yml up -d --build
docker compose -f lab/docker-compose.yml down
```

## What it exposes
| Port | Service | For |
|------|---------|-----|
| 22   | SSH (user `analyst`, password `hunter2`) | recon service enum, sniffer capture |
| 8000 | HTTP serving `/srv/hashes.txt` | recon HTTP enum; the hash the cracker audits |

`hashes.txt` is a **real md5crypt hash** of the weak password (`openssl passwd
-1 -salt xyz hunter2`), so `hashcat -m 500` / `john` genuinely crack it against a
wordlist that contains `hunter2`.

## Running the engagement against it
The operator (the swarm) runs on `labnet` and reaches the target directly:
```sh
python3 run_engagement.py --backend gguf:/models/<model>.gguf --execute
```
`--execute` seeds the recovered hash as an in-scope finding (representing a prior
authorized dump) so the cracker's action has valid provenance. Point the seeded
`artifact` in `run_engagement.py` at the value in `/srv/hashes.txt` for a live
end-to-end crack.

## Scope discipline
This target **is** the authorized scope. Do not add real hosts to
`SCOPE`/`AUTHZ` in `run_engagement.py`. The kernel will refuse out-of-scope
targets, and the adapters re-check scope in code — but the whole point is that
you never ask it to.
