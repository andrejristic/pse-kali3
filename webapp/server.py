#!/usr/bin/env python3
# =============================================================================
# PSE-KALI — WEB APP SERVER
# The full governed console in the browser: the same live steering + model swap
# as the native app, over HTTP. A ThreadingHTTPServer drives one LiveEngine and
# exposes it as a small JSON API the front-end polls.
#
#   Local:   python3 webapp/server.py --port 8420
#   Public:  runs in DEMO MODE by default (no real tools execute) — safe to host.
#
# Env:
#   PORT / --port      listen port (default 8420; hosts like Render/HF set PORT)
#   PSE_BACKEND        mock (default) | claude:<model> | mistral:<model> | gguf:<path>
#   PSE_EXECUTE=1      run REAL tools (LOCAL LAB ONLY — never on a public host)
# =============================================================================
import argparse
import json
import os
import sys
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "monitor"))

from audit_to_timeline import records_from_audit
from pse_kernel import make_backend, SwappableBackend, list_local_models
from pse_kernel.engine import assemble
from pse_kernel.adapters import lab_adapters
from packs.recon import RECON_PACK
from packs.password import PASSWORD_PACK
from packs.sniff import SNIFF_PACK
from packs.access import ACCESS_PACK

INDEX = os.path.join(HERE, "index.html")
AUDIT = os.path.join(REPO, "audit", "webapp.jsonl")
MODELS_DIR = os.path.join(REPO, "models")
PACKS = {"recon": RECON_PACK, "password": PASSWORD_PACK,
         "sniff": SNIFF_PACK, "access": ACCESS_PACK}


class App:
    """Owns the LiveEngine and mirrors its control queues into pollable state."""
    def __init__(self, backend_spec, execute):
        scope = ["10.10.10.0/24"]
        authz = [{"target_scope": ["10.10.10.0/24"],
                  "tools": ["nmap", "masscan", "hashcat", "john", "tcpdump", "tshark"]}]
        gguf_opts = {}
        try:
            import yaml
            cfg = yaml.safe_load(open(os.path.join(REPO, "config.yaml"))) or {}
            scope = cfg.get("scope", scope)
            authz = cfg.get("authorizations", authz)
            gguf_opts = cfg.get("gguf", {})
        except Exception:
            pass
        kw = gguf_opts if backend_spec.startswith("gguf") else {}
        raw = make_backend(backend_spec,
                           **({"scripted": []} if backend_spec == "mock" else kw))
        self.proxy = SwappableBackend(raw, name=backend_spec.split(":")[-1] or backend_spec)
        adapters = lab_adapters(execute=execute)     # execute=False => nothing runs
        goals = {"recon": "map in-scope hosts and services",
                 "password": "audit in-scope credentials",
                 "sniff": "capture in-scope traffic",
                 "access": "gain authorized access and leave an agreed marker"}
        os.makedirs(os.path.dirname(AUDIT), exist_ok=True)
        open(AUDIT, "w").close()
        self.engine, self.ctx, self.control, self.proxy = assemble(
            PACKS, adapters, self.proxy, scope, authz, goals, AUDIT)
        if execute:
            self.ctx.add_finding({"kind": "hash", "target": "10.10.10.5",
                                  "artifact": "$1$xyz$deadbeef"})
        self.log_lines = []
        self.escalations = {}          # id -> Escalation
        self.engine.start()
        threading.Thread(target=self._drain, daemon=True).start()

    def _drain(self):
        c = self.control
        while not c.stop.is_set():
            drained = False
            while not c.log.empty():
                self.log_lines.append(c.log.get()); drained = True
            while not c.escalations.empty():
                e = c.escalations.get(); self.escalations[e.id] = e; drained = True
            if not drained:
                threading.Event().wait(0.2)

    # ---- API operations ----------------------------------------------------
    def events(self):
        lines = open(AUDIT).readlines() if os.path.exists(AUDIT) else []
        return records_from_audit(lines)

    def log(self, since):
        return {"lines": self.log_lines[since:], "total": len(self.log_lines)}

    def pending(self):
        return [{"id": e.id, "unit": e.unit, "tool": e.action.get("tool"),
                 "target": e.action.get("target"), "kind": e.kind, "reason": e.reason}
                for e in self.escalations.values()]

    def resolve(self, eid, decision):
        e = self.escalations.pop(int(eid), None)
        if e:
            e.resolve("approve" if decision == "approve" else "deny")
            return True
        return False

    def command(self, text):
        self.control.say(f"you: {text}")
        self.control.command(text)

    def models(self):
        return {"active": self.proxy.name,
                "swapping": self.control.paused.is_set(),
                "available": list_local_models(MODELS_DIR)}

    def preset(self, name):
        return self.engine.apply_preset(name)

    def scope(self):
        return {"scope": self.ctx.scope}

    def authorize(self, target):
        if target:
            self.engine.authorize_scope(target)
            return True
        return False

    def switch(self, path, fits):
        threading.Thread(target=lambda: self.engine.switch_model(path, fits=fits),
                         daemon=True).start()


APP = None      # set in main()
TOKEN = None    # optional access token for public hosting (env PSE_TOKEN)


class Handler(BaseHTTPRequestHandler):
    def _authed(self):
        if not TOKEN:
            return True
        q = dict(p.split("=", 1) for p in self.path.split("?")[1].split("&")) \
            if "?" in self.path else {}
        return self.headers.get("X-PSE-Token") == TOKEN or q.get("t") == TOKEN

    def _send(self, body, ctype="application/json", code=200):
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n) or b"{}") if n else {}

    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/")
        qs = dict(p.split("=", 1) for p in self.path.split("?")[1].split("&")) \
            if "?" in self.path else {}
        if path in ("", "/index.html"):
            self._send(open(INDEX, "rb").read(), "text/html; charset=utf-8")
            return
        if not self._authed():
            self._send({"error": "unauthorized"}, code=401); return
        if path.endswith("/events"):
            self._send(APP.events())
        elif path.endswith("/log"):
            self._send(APP.log(int(qs.get("since", 0))))
        elif path.endswith("/escalations"):
            self._send(APP.pending())
        elif path.endswith("/models"):
            self._send(APP.models())
        elif path.endswith("/scope"):
            self._send(APP.scope())
        else:
            self._send({"error": "not found"}, code=404)

    def do_POST(self):
        if not self._authed():
            self._send({"error": "unauthorized"}, code=401); return
        path = self.path.split("?")[0].rstrip("/")
        data = self._body()
        if path.endswith("/command"):
            APP.command(data.get("text", "")); self._send({"ok": True})
        elif path.endswith("/escalation"):
            ok = APP.resolve(data.get("id"), data.get("decision"))
            self._send({"ok": ok})
        elif path.endswith("/switch"):
            APP.switch(data.get("path"), data.get("fits", True)); self._send({"ok": True})
        elif path.endswith("/scope"):
            self._send({"ok": APP.authorize(data.get("target"))})
        elif path.endswith("/preset"):
            self._send({"ok": APP.preset(data.get("name"))})
        else:
            self._send({"error": "not found"}, code=404)

    def log_message(self, *a):   # quiet
        pass


def main():
    global APP, TOKEN
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8420)))
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--backend", default=os.environ.get("PSE_BACKEND", "mock"))
    ap.add_argument("--token", default=os.environ.get("PSE_TOKEN"),
                    help="require ?t=TOKEN / X-PSE-Token on the API (for public hosting)")
    args = ap.parse_args()
    TOKEN = args.token
    execute = os.environ.get("PSE_EXECUTE") == "1"

    APP = App(args.backend, execute)
    mode = "REAL TOOLS" if execute else "demo (simulated — no tools run)"
    print(f"PSE-Kali web console on http://{args.host}:{args.port}  "
          f"[backend={args.backend}, {mode}]")
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
