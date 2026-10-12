#!/usr/bin/env bash
# =============================================================================
# PSE-KALI — APPROVE-THEN-RUN wrapper (opened by the native console)
# The console never runs anything itself. It opens a terminal here, shows the
# EXACT command it prepared, and waits. Nothing executes until the operator
# presses ENTER *and* types their Ubuntu password. `sudo -k` clears any cached
# credential first, so EVERY run is password-gated — no exceptions.
#   env in:  PSE_CMD  PSE_ASROOT(0|1)  PSE_REPO  PSE_USER
# =============================================================================
set -u
cmd="${PSE_CMD:-}"
asroot="${PSE_ASROOT:-0}"
repo="${PSE_REPO:-.}"
user="${PSE_USER:-$USER}"

echo
echo "  ┌─ PSE-Kali · approve to run ────────────────────────────────"
echo "  │ This command was prepared by the console (nothing has run):"
echo "  │"
echo "  │    $cmd"
echo "  │"
if [ "$asroot" = "1" ]; then
  echo "  │ It needs administrator rights (a defense/system change)."
else
  echo "  │ It runs a governed security tool against an authorized target."
fi
echo "  └─ Press ENTER to RUN, or close this window / Ctrl-C to CANCEL."
read -r _ || exit 0

echo
if [ "$asroot" = "1" ]; then
  sudo -k -p "  your Ubuntu password: " bash -lc "cd '$repo'; $cmd"
else
  # run as the normal user (not root), but still force a password prompt
  sudo -k -p "  your Ubuntu password: " -u "$user" bash -lc "cd '$repo'; $cmd"
fi
status=$?
echo
echo "  --- finished (exit $status). Press ENTER to close this window. ---"
read -r _ || true
