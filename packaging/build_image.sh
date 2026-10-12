#!/usr/bin/env bash
# =============================================================================
# PSE-KALI — BOOT IMAGE REMASTER
# Bake the governed-security swarm into an existing live ISO (MX XFCE or Debian
# live). Boot the result → it autostarts one governed engagement against the
# on-image lab target and the monitor reads the audit log. We remaster an ISO;
# we do NOT maintain a distribution.
#
# Run as root on your build machine (NOT in this repo's sandbox):
#   sudo packaging/build_image.sh \
#     --iso   MX-XFCE.iso \
#     --repo  /home/a/Desktop/pse-kali \
#     --model /models/qwen2.5-3b-instruct-q4.gguf \
#     --out   pse-kali.iso
#
# Needs: xorriso, squashfs-tools (unsquashfs/mksquashfs), rsync.
# =============================================================================
set -euo pipefail

ISO= REPO= MODEL= OUT=pse-kali.iso
while [ $# -gt 0 ]; do
  case "$1" in
    --iso) ISO=$2; shift 2;;
    --repo) REPO=$2; shift 2;;
    --model) MODEL=$2; shift 2;;
    --out) OUT=$2; shift 2;;
    *) echo "unknown arg: $1" >&2; exit 2;;
  esac
done
[ "$(id -u)" = 0 ] || { echo "run as root" >&2; exit 1; }
[ -f "$ISO" ] && [ -d "$REPO" ] || { echo "need --iso <file> and --repo <dir>" >&2; exit 1; }
for t in xorriso unsquashfs mksquashfs rsync; do
  command -v "$t" >/dev/null || { echo "missing tool: $t" >&2; exit 1; }
done

WORK=$(mktemp -d /tmp/pse-remaster.XXXXXX)
trap 'umount "$WORK/rootfs/proc" 2>/dev/null || true; rm -rf "$WORK"' EXIT
echo "[*] work dir: $WORK"

# --- 1. extract the ISO tree (osirrox) -------------------------------------
echo "[*] extracting ISO"
xorriso -osirrox on -indev "$ISO" -extract / "$WORK/iso" >/dev/null 2>&1
chmod -R u+w "$WORK/iso"

# --- 2. locate the squashfs (Debian live vs MX/antiX layout) ---------------
SQFS=$(find "$WORK/iso" -name filesystem.squashfs -o -name linuxfs 2>/dev/null | head -1)
[ -n "$SQFS" ] || { echo "could not find squashfs in ISO" >&2; exit 1; }
echo "[*] squashfs: ${SQFS#$WORK/iso}"

# --- 3. unpack root filesystem ---------------------------------------------
echo "[*] unsquashfs (this takes a while)"
unsquashfs -d "$WORK/rootfs" "$SQFS" >/dev/null

# --- 4. overlay PSE-Kali ----------------------------------------------------
echo "[*] copying repo -> /opt/pse-kali"
rsync -a --exclude audit/ --exclude '__pycache__' "$REPO"/ "$WORK/rootfs/opt/pse-kali/"
mkdir -p "$WORK/rootfs/opt/pse-kali/models" "$WORK/rootfs/opt/pse-kali/audit"
[ -n "$MODEL" ] && cp "$MODEL" "$WORK/rootfs/opt/pse-kali/models/"
install -m644 "$REPO/packaging/pse-kali.service" \
  "$WORK/rootfs/etc/systemd/system/pse-kali.service"

# --- 5. install deps inside the target rootfs (chroot) ---------------------
echo "[*] installing packages + python deps in chroot"
cp /etc/resolv.conf "$WORK/rootfs/etc/resolv.conf" 2>/dev/null || true
mount --bind /proc "$WORK/rootfs/proc" 2>/dev/null || true
chroot "$WORK/rootfs" /bin/bash -euo pipefail <<'CHROOT'
export DEBIAN_FRONTEND=noninteractive
apt-get update
# the three real tools + firmware-friendly extras + python + zram
apt-get install -y --no-install-recommends \
  python3 python3-pip nmap tcpdump hashcat john theharvester \
  docker.io zram-tools || true
pip3 install --break-system-packages -r /opt/pse-kali/requirements.txt || \
  pip3 install -r /opt/pse-kali/requirements.txt || true
systemctl enable pse-kali.service || true
systemctl enable docker || true
# zram on by default (4 GB target — from the Surface playbook)
printf 'ALGO=zstd\nPERCENT=50\nPRIORITY=100\n' > /etc/default/zramswap || true
apt-get clean; rm -rf /var/lib/apt/lists/*
CHROOT
umount "$WORK/rootfs/proc" 2>/dev/null || true

# --- 6. repack squashfs -----------------------------------------------------
echo "[*] mksquashfs"
rm -f "$SQFS"
mksquashfs "$WORK/rootfs" "$SQFS" -comp zstd -noappend >/dev/null

# --- 7. repack ISO, replaying the original boot setup ----------------------
echo "[*] repacking bootable ISO -> $OUT"
xorriso -indev "$ISO" -outdev "$OUT" \
  -boot_image any replay \
  -map "$WORK/iso" / -commit >/dev/null 2>&1 || {
    # fallback: rebuild from the extracted tree, cloning boot from the source
    xorriso -as mkisofs -o "$OUT" -R -J -V PSE-KALI \
      -boot_image any replay "$WORK/iso"
  }

echo "[✓] done: $OUT"
echo "    Write it to USB (e.g. dd/balenaEtcher), boot, and it will run one"
echo "    governed engagement against the on-image lab target on first boot."
