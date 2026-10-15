#!/usr/bin/env bash
# Render the UI with headless Chrome on big-machine and pull the captures into .impeccable/review/.
# Usage: ./shot.sh [path-with-query]   e.g. ./shot.sh "/?shot=1&state=result"
set -euo pipefail
cd "$(dirname "$0")"
P=${1:-/?shot=1}
PFX=${2:-}
mkdir -p .impeccable/review
~/.terdiff-remote/bssh "cd research/embedgemma && for s in desktop:1440,900 mobile:390,844 user:1280,760; do n=\${s%%:*}; wh=\${s#*:}; google-chrome --headless=new --no-sandbox --disable-gpu --hide-scrollbars --use-fake-ui-for-media-stream --use-fake-device-for-media-stream --autoplay-policy=no-user-gesture-required --virtual-time-budget=6000 --window-size=\$wh --screenshot=/tmp/shot-\$n.png 'http://127.0.0.1:8787$P' >/dev/null 2>&1; done; ls -la /tmp/shot-*.png"
for n in desktop mobile user; do ./bscp -q "bm:/tmp/shot-$n.png" ".impeccable/review/${PFX}$n.png"; done
ls -la .impeccable/review/
