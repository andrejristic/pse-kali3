#!/usr/bin/env python3
# =============================================================================
# PSE-KALI — RUN A GOVERNED ENGAGEMENT
# Wires a local/cloud model (the operator) into the concurrent swarm. The model
# drives four security units; the kernel governs every proposed action.
#
#   python3 run_engagement.py --backend claude:claude-opus-4-8
#   python3 run_engagement.py --backend mistral:mistral-large-latest
#   python3 run_engagement.py --backend gguf:/models/qwen2.5-3b-instruct-q4.gguf
#   python3 run_engagement.py --backend mock      # offline demo, no deps/keys
#
# With no --backend, auto-selects a local GGUF sized to this machine's RAM from
# ./models (edit MODELS below). Tools run against the lab target only (simulated
# here; wire real CLI adapters at the marked points for a live lab).
# =============================================================================
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pse_kernel import (EngagementContext, AuditLog, Swarm, Unit, ModelOperator,
                        make_backend, select_gguf, detect_ram_gb, selftest_backend)
from pse_kernel.adapters import lab_adapters
from packs.recon import RECON_PACK
from packs.password import PASSWORD_PACK
from packs.sniff import SNIFF_PACK
from packs.access import ACCESS_PACK

HERE = os.path.dirname(os.path.abspath(__file__))
AUDIT_PATH = os.path.join(HERE, "audit", "engagement.jsonl")

# Local models to auto-select from, largest-first (paths are yours to provide).
MODELS = [
    {"path": os.path.join(HERE, "models", "qwen2.5-14b-instruct-q4.gguf"), "min_ram_gb": 12},
    {"path": os.path.join(HERE, "models", "qwen2.5-7b-instruct-q4.gguf"),  "min_ram_gb": 6},
    {"path": os.path.join(HERE, "models", "qwen2.5-3b-instruct-q4.gguf"),  "min_ram_gb": 3},
]

SCOPE = ["10.10.10.0/24"]
AUTHZ = [{"target_scope": ["10.10.10.0/24"],
          "tools": ["nmap", "masscan", "hashcat", "john", "tcpdump", "wireshark", "ssh"]}]

# ---- lab adapters (simulate tool execution). Replace with real CLI calls. ---
def recon_adapter(a, ctx):
    return [{"kind": "host", "target": "10.10.10.5", "service": "ssh"},
            {"kind": "hash", "target": "10.10.10.5", "artifact": "$1$xyz$deadbeef"}]
def cracker_adapter(a, ctx):
    return [{"kind": "cred", "target": a.get("target"), "user": "admin"}]
def sniff_adapter(a, ctx):
    return [{"kind": "pcap", "target": a.get("target"), "bytes": 4096}]
def access_adapter(a, ctx):
    return [{"kind": "access", "target": a.get("target"), "ok": True}]


def load_config(path):
    try:
        import yaml   # lazy; pyyaml only needed when --config is used
    except ImportError:
        sys.exit("--config needs pyyaml:  pip install pyyaml  (or drop --config "
                 "and use flags/defaults)")
    with open(path) as fh:
        return yaml.safe_load(fh) or {}


def build_backends(spec, scripts, gguf_opts=None):
    gguf_opts = gguf_opts or {}
    if spec == "mock":
        return {u: make_backend("mock", scripted=s) for u, s in scripts.items()}
    if spec:
        kw = gguf_opts if spec.startswith("gguf") else {}
        return {u: make_backend(spec, **kw) for u in scripts}   # same model, 4 units
    path = select_gguf(MODELS)
    print(f"[auto] RAM ~= {detect_ram_gb():.1f} GB -> local model {path}")
    return {u: make_backend(f"gguf:{path}", **gguf_opts) for u in scripts}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default=None,
                    help="claude:<model> | mistral:<model> | gguf:<path> | mock")
    ap.add_argument("--selftest", action="store_true",
                    help="check the backend emits valid actions, then exit")
    ap.add_argument("--execute", action="store_true",
                    help="run REAL tools against the lab (default: simulated)")
    ap.add_argument("--config", default=None,
                    help="YAML with scope/authorizations/backend (see config.yaml)")
    args = ap.parse_args()

    cfg = load_config(args.config) if args.config else {}
    scope = cfg.get("scope", SCOPE)
    authz = cfg.get("authorizations", AUTHZ)
    backend_spec = args.backend or cfg.get("backend")
    gguf_opts = cfg.get("gguf", {})     # n_gpu_layers / n_ctx / n_threads

    packs = {"recon": RECON_PACK, "password": PASSWORD_PACK,
             "sniff": SNIFF_PACK, "access": ACCESS_PACK}
    if args.selftest:
        be = build_backends(backend_spec or "", {u: [] for u in packs}, gguf_opts)
        bad = 0
        for u, pack in packs.items():
            ok, msg = selftest_backend(be[u], pack, scope=scope[0])
            print(f"  {'ok ' if ok else 'FAIL'} {u:9} {msg}")
            bad += 0 if ok else 1
        sys.exit(1 if bad else 0)

    os.makedirs(os.path.dirname(AUDIT_PATH), exist_ok=True)
    open(AUDIT_PATH, "w").close()
    audit = AuditLog(AUDIT_PATH)
    ctx = EngagementContext("ENG-LIVE", scope, authz)

    # offline demo script (only used with --backend mock)
    def a(tool, tgt, args_, why, art=None, done=False):
        return json.dumps({"action": "done" if done else "propose", "tool": tool,
                           "target": tgt, "args": args_, "rationale": why, "artifact": art})
    scripts = {
        "recon": [a("nmap", "10.10.10.0/24", ["-sV", "-T4"], "enumerate in scope"),
                  a("", "", [], "done", done=True)],
        "password": [a("hashcat", "10.10.10.5", ["-a", "0", "rockyou.txt"],
                       "credential audit in scope", art="$1$xyz$deadbeef"),
                     a("", "", [], "done", done=True)],
        "sniff": [a("tcpdump", "10.10.10.5", ["-i", "eth0"], "passive capture in scope"),
                  a("", "", [], "done", done=True)],
        "access": [json.dumps({"action": "propose", "tool": "ssh", "target": "10.10.10.5",
                               "args": [], "rationale": "authorized marker in scope",
                               "command": "echo \"pse was here\" > ~/pse.txt",
                               "user": "analyst", "artifact": None}),
                   a("", "", [], "done", done=True)],
    }
    backends = build_backends(backend_spec, scripts, gguf_opts)

    goals = {"recon": "map in-scope hosts and services",
             "password": "audit credentials recovered in scope",
             "sniff": "capture in-scope traffic for analysis",
             "access": "gain authorized access and leave an agreed marker"}
    if args.execute:
        # real tools against the lab; seed an in-scope hash (dumped in a prior
        # authorized step) so the cracker's action has valid provenance
        adapters = lab_adapters(execute=True)
        ctx.add_finding({"kind": "hash", "target": "10.10.10.5",
                         "artifact": "$1$xyz$deadbeef"})
    else:
        adapters = {"recon": recon_adapter, "password": cracker_adapter,
                    "sniff": sniff_adapter, "access": access_adapter}

    units = [Unit(packs[u],
                  ModelOperator(backends[u], packs[u], goals[u], scope),
                  adapters[u], ctx, audit)
             for u in ("recon", "password", "sniff", "access")]
    Swarm(units).run()

    allowed = sum(1 for u in units for d in u.decisions if d.allowed)
    held = sum(1 for u in units for d in u.decisions if not d.allowed)
    print(f"engagement complete: {allowed} actions ran, {held} held by the kernel")
    print(f"findings: {[f['kind'] for f in ctx.findings()]}")
    print(f"audit: {AUDIT_PATH}")


if __name__ == "__main__":
    main()
