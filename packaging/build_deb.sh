#!/usr/bin/env bash
# Build pse-kali_<version>_all.deb — the Python app under /opt/pse-kali, run with
# the system python3. It DRIVES external tools (nmap, tcpdump, ssh, hashcat, ...)
# which are listed as Recommends; LLM backends install via pip when you pick one.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; REPO="$(dirname "$HERE")"
VERSION="${1:-0.1.0}"; ARCH="all"; PKG="pse-kali"
STAGE="$HERE/stage"; OUT="$REPO/dist"
rm -rf "$STAGE"; mkdir -p "$STAGE/opt/$PKG" "$STAGE/usr/bin" "$STAGE/usr/share/doc/$PKG" "$STAGE/DEBIAN"
# app payload (code + config + packs + labs), excluding VCS/build/docs cruft
for item in pse_kernel packs lab monitor webapp report.py run_action.py run_engagement.py config.yaml fetch_model.sh requirements.txt Makefile README.md; do
  [ -e "$REPO/$item" ] && cp -r "$REPO/$item" "$STAGE/opt/$PKG/"
done
find "$STAGE/opt/$PKG" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
cp "$REPO/LICENSE" "$STAGE/opt/$PKG/LICENSE"; cp "$REPO/NOTICE" "$STAGE/opt/$PKG/NOTICE"
cp "$REPO/LICENSE" "$STAGE/usr/share/doc/$PKG/LICENSE"; cp "$REPO/NOTICE" "$STAGE/usr/share/doc/$PKG/NOTICE"
cat > "$STAGE/usr/bin/$PKG" <<'SH'
#!/bin/sh
# PSE-Kali launcher: run the engagement orchestrator with the system python3.
cd /opt/pse-kali || exit 1
exec python3 run_engagement.py "$@"
SH
chmod 0755 "$STAGE/usr/bin/$PKG"
cat > "$STAGE/DEBIAN/control" <<CTL
Package: $PKG
Version: $VERSION
Section: admin
Priority: optional
Architecture: $ARCH
Maintainer: Andrej Ristic <andrej.s.ristic@gmail.com>
Depends: python3 (>= 3.10), python3-yaml
Recommends: nmap, tcpdump, openssh-client, hashcat, john, masscan
Homepage: https://github.com/andrejristic/pse-kali3
Description: PSE-Kali - a PSE-governed operator for authorized security assessment
 A PSE-governed operator that drives standard security tools (nmap, tcpdump,
 ssh, hashcat, ...) against an authorized lab target, with a Guardian over every
 action and a shared findings store. Defensive / authorized-assessment use only.
 Install the tools you need (Recommends) and pick an LLM backend; the mock
 backend runs fully offline. Run: pse-kali --backend mock
CTL
mkdir -p "$OUT"
DEB="$OUT/${PKG}_${VERSION}_${ARCH}.deb"
dpkg-deb --root-owner-group -Zxz --build "$STAGE" "$DEB"
echo "built $DEB"
