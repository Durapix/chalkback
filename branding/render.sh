#!/usr/bin/env bash
# Render every icon size from the two SVGs in this folder (needs Docker; uses librsvg).
#   icon.svg       rounded square with transparent corners: browser tabs, in-app use
#   icon-full.svg  full-bleed square: Telegram (cropped to a circle), iPhone and Android
#                  home screens (they apply their own mask). The drawing stays inside the
#                  central 80% circle, so no crop cuts it.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
winpath() { if command -v cygpath >/dev/null; then cygpath -w "$1"; else echo "$1"; fi; }
export MSYS_NO_PATHCONV=1
docker run --rm -v "$(winpath "$here"):/w" -w /w alpine:3.22 sh -euc '
  apk add -q rsvg-convert imagemagick >/dev/null
  mkdir -p out
  r() { rsvg-convert -w "$2" -h "$2" "$1" -o "out/$3"; }
  r icon-full.svg 512 telegram-bot-512.png
  r icon-full.svg 180 apple-touch-icon.png
  r icon-full.svg 512 icon-maskable-512.png
  r icon.svg 192 icon-192.png
  r icon.svg 512 icon-512.png
  r icon.svg 16 favicon-16.png
  r icon.svg 32 favicon-32.png
  r icon.svg 48 favicon-48.png
  magick out/favicon-16.png out/favicon-32.png out/favicon-48.png out/favicon.ico
  rm out/favicon-16.png out/favicon-48.png
'
ls -l "$here/out"
