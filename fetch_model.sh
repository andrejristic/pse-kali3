#!/usr/bin/env bash
# =============================================================================
# PSE-KALI — fetch a local GGUF model sized to your machine.
#   ./fetch_model.sh [3b|7b|14b]     (default 7b — good on 16 GB)
# Saves to models/qwen2.5-<size>-instruct-q4.gguf so auto-select finds it.
# Prefers huggingface-cli (robust); falls back to curl. Qwen2.5-Instruct is a
# strong small model at JSON / instruction-following, which is what the operator
# needs. Verify the URL if a download 404s (repos occasionally rename files).
# =============================================================================
set -euo pipefail
SIZE="${1:-7b}"
mkdir -p models

case "$SIZE" in
  3b)  REPO="Qwen/Qwen2.5-3B-Instruct-GGUF";  FILE="qwen2.5-3b-instruct-q4_k_m.gguf";;
  7b)  REPO="Qwen/Qwen2.5-7B-Instruct-GGUF";  FILE="qwen2.5-7b-instruct-q4_k_m.gguf";;
  14b) REPO="Qwen/Qwen2.5-14B-Instruct-GGUF"; FILE="qwen2.5-14b-instruct-q4_k_m.gguf";;
  *) echo "usage: $0 [3b|7b|14b]" >&2; exit 2;;
esac
OUT="models/qwen2.5-${SIZE}-instruct-q4.gguf"

echo "[*] fetching $REPO / $FILE  ->  $OUT"
if command -v huggingface-cli >/dev/null; then
  huggingface-cli download "$REPO" "$FILE" --local-dir models >/dev/null
  # huggingface-cli keeps the original name; symlink/rename to the expected path
  [ -f "models/$FILE" ] && mv -f "models/$FILE" "$OUT"
else
  URL="https://huggingface.co/${REPO}/resolve/main/${FILE}?download=true"
  echo "[*] huggingface-cli not found; curl from $URL"
  curl -fL --retry 3 -o "$OUT" "$URL"
fi

echo "[✓] $OUT"
echo "    Point config.yaml at it:  backend: gguf:$OUT   (or leave auto-select)"
