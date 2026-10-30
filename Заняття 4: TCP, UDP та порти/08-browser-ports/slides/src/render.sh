#!/usr/bin/env bash
# Usage: src/render.sh name W H
D="$(cd "$(dirname "$0")" && pwd)"
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu --hide-scrollbars \
  --user-data-dir="$D/.chrome-profile" --force-device-scale-factor=2 --window-size="$2,$3" \
  --screenshot="$D/../img/$1.png" "file://$D/$1.html" 2>/dev/null
