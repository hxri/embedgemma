#!/usr/bin/env bash
# Full loop: record (or take a clip) -> push to big-machine -> match on GPU 0 -> pull result -> play.
# Usage: ./demo.sh                                   record 10 s, then match
#        ./demo.sh clips/x.mp4 [match.py args]       e.g. --query video --mode audio --alpha 0.7 --mix
set -euo pipefail
cd "$(dirname "$0")"
BSSH=~/.terdiff-remote/bssh
REMOTE=research/embedgemma   # relative to the remote home (do not use ~ here: it expands on the Mac)
source ~/.terdiff-remote/connect.sh >/dev/null 2>&1 || true

if [[ $# -gt 0 && -f "$1" ]]; then CLIP=$1; shift; else CLIP=clips/clip_$(date +%Y%m%d_%H%M%S).mp4; ./record.sh "$CLIP" 10; fi
NAME=$(basename "$CLIP"); STEM=${NAME%.*}

echo "-> uploading $NAME"
$BSSH "mkdir -p $REMOTE/in" && ./bscp -q "$CLIP" "bm:$REMOTE/in/$NAME"
echo "-> matching on big-machine (GPU 0)"
$BSSH "cd $REMOTE && source ~/miniconda3/etc/profile.d/conda.sh && conda activate embedgemma && CUDA_VISIBLE_DEVICES=0 python match.py in/$NAME $*" 2>&1 | grep -v -E "^(Warning: Permanently|Loading weights)"
echo "-> downloading result"
mkdir -p out && ./bscp -q "bm:$REMOTE/in/${STEM}_sfx.mp4" "out/${STEM}_sfx.mp4"
echo "-> playing out/${STEM}_sfx.mp4"
ffplay -autoexit -loglevel error "out/${STEM}_sfx.mp4"
