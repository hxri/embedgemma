#!/usr/bin/env bash
# Record a short clip from the MacBook camera + microphone. Usage: ./record.sh [out.mp4] [seconds]
set -euo pipefail
OUT=${1:-clips/clip_$(date +%Y%m%d_%H%M%S).mp4}
SECS=${2:-10}
mkdir -p "$(dirname "$OUT")"
for n in 3 2 1; do echo "recording in $n..."; sleep 1; done
echo "GO (${SECS}s) - do something audible!"
ffmpeg -y -hide_banner -loglevel error \
  -f avfoundation -framerate 30 -video_size 1280x720 -pixel_format uyvy422 -i "0:0" \
  -t "$SECS" -c:v libx264 -preset veryfast -pix_fmt yuv420p -c:a aac -b:a 128k "$OUT"
echo "saved $OUT"
