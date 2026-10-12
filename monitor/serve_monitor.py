#!/usr/bin/env python3
# =============================================================================
# PSE-KALI — LIVE CONSOLE SERVER
# Serves the governed-security console (pse_app.html) and:
#   GET  /events  -> the current audit log as monitor records (page polls this)
#   POST /run     -> start one governed engagement (Run button)
#   POST /stop    -> stop a running engagement (Stop button)
# The three points move as the engagement runs. On the boot image, autostart
# this and open a browser at http://localhost:8420.
#
#   python3 monitor/serve_monitor.py [--port 8420] [--run-cmd "python3 run_engagement.py --backend mock"]
# =============================================================================
import argparse
import http.server
import json
import os
import shlex
import subprocess

from audit_to_timeline import records_from_audit

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
APP = os.path.join(HERE, "pse_app.html")
AUDIT = os.path.join(REPO, "audit", "engagement.jsonl")


def make_handler(audit_path, run_cmd):
    state = {"proc": None}

    class Handler(http.server.BaseHTTPRequestHandler):
        def _send(self, body, ctype, code=200):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = self.path.rstrip("/")
            if path in ("", "/index.html"):
                with open(APP, "rb") as fh:
                    self._send(fh.read(), "text/html; charset=utf-8")
            elif path.endswith("events"):
                lines = open(audit_path).readlines() if os.path.exists(audit_path) else []
                self._send(json.dumps(records_from_audit(lines)).encode(),
                           "application/json")
            else:
                self.send_error(404)

        def do_POST(self):
            path = self.path.rstrip("/")
            if path.endswith("run"):
                if state["proc"] and state["proc"].poll() is None:
                    self._send(b'{"status":"already-running"}', "application/json")
                    return
                state["proc"] = subprocess.Popen(shlex.split(run_cmd), cwd=REPO)
                self._send(b'{"status":"started"}', "application/json")
            elif path.endswith("stop"):
                if state["proc"] and state["proc"].poll() is None:
                    state["proc"].terminate()
                self._send(b'{"status":"stopped"}', "application/json")
            else:
                self.send_error(404)

        def log_message(self, *a):   # quiet
            pass
    return Handler


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit", default=AUDIT)
    ap.add_argument("--port", type=int, default=8420)
    ap.add_argument("--run-cmd", default="python3 run_engagement.py --backend mock",
                    help="command the Run button starts (cwd = repo root)")
    args = ap.parse_args()
    srv = http.server.HTTPServer(("127.0.0.1", args.port),
                                 make_handler(args.audit, args.run_cmd))
    print(f"console: http://localhost:{args.port}   ·   Run -> {args.run_cmd!r}")
    srv.serve_forever()


if __name__ == "__main__":
    main()
