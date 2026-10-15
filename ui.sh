#!/usr/bin/env bash
# Launch the demo UI on this Mac: Tailscale up -> SSH tunnel localhost:8787 -> model server on big-machine -> open browser.
# Usage: ./ui.sh            start everything and open http://localhost:8787
#        ./ui.sh stop       stop the tunnel (the server on the box keeps running in tmux "eg-server")
#        ./ui.sh restart    restart the model server on the box (after editing server.py / engine.py)
set -euo pipefail
cd "$(dirname "$0")"
PORT=8787
BSSH=~/.terdiff-remote/bssh
TUNNEL_PID=.tunnel.pid

tunnel_loop() {  # self-restarting port forward over the Tailscale SOCKS proxy (box WiFi drops sometimes)
  while true; do
    ssh -i ~/.terdiff-remote/id_terdiff -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        -o BatchMode=yes -o ConnectTimeout=20 -o ServerAliveInterval=15 -o ServerAliveCountMax=3 \
        -o ExitOnForwardFailure=yes -o "ProxyCommand=nc -X 5 -x 127.0.0.1:1055 %h %p" \
        -N -L $PORT:127.0.0.1:$PORT hari@100.103.33.60 >/dev/null 2>&1
    sleep 3
  done
}

case "${1:-start}" in
  stop)
    [[ -f $TUNNEL_PID ]] && pkill -P "$(cat $TUNNEL_PID)" 2>/dev/null; [[ -f $TUNNEL_PID ]] && kill "$(cat $TUNNEL_PID)" 2>/dev/null; rm -f $TUNNEL_PID
    echo "tunnel stopped"; exit 0;;
  restart)
    $BSSH "cd research/embedgemma && source ~/miniconda3/etc/profile.d/conda.sh && conda activate embedgemma && tmux kill-session -t eg-server 2>/dev/null; tmux new-session -d -s eg-server 'CUDA_VISIBLE_DEVICES=0 uvicorn server:app --host 127.0.0.1 --port $PORT > server.log 2>&1'"
    echo "server restarting on big-machine";;
esac

source ~/.terdiff-remote/connect.sh >/dev/null 2>&1 || true

# model server on the box (idempotent)
$BSSH "cd research/embedgemma && source ~/miniconda3/etc/profile.d/conda.sh && conda activate embedgemma && (curl -sf http://127.0.0.1:$PORT/api/health >/dev/null || (tmux kill-session -t eg-server 2>/dev/null; tmux new-session -d -s eg-server 'CUDA_VISIBLE_DEVICES=0 uvicorn server:app --host 127.0.0.1 --port $PORT > server.log 2>&1'))"

# decode service (DiffusionGemma, 52 GB on GPU 0; idempotent)
$BSSH "cd research/embedgemma && source ~/miniconda3/etc/profile.d/conda.sh && conda activate embedgemma && (curl -sf http://127.0.0.1:8788/health >/dev/null || (tmux kill-session -t eg-steer 2>/dev/null; tmux new-session -d -s eg-steer 'PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True CUDA_VISIBLE_DEVICES=0 uvicorn steer_server:app --host 127.0.0.1 --port 8788 > steer.log 2>&1'))"

# tunnel (idempotent)
if ! { [[ -f $TUNNEL_PID ]] && kill -0 "$(cat $TUNNEL_PID)" 2>/dev/null; }; then
  tunnel_loop & echo $! > $TUNNEL_PID; disown
fi

printf "waiting for model server"
for i in $(seq 1 60); do
  if curl -sf http://localhost:$PORT/api/health 2>/dev/null | grep -q '"ok":true'; then echo; echo "ready: http://localhost:$PORT"; break; fi
  printf "."; sleep 2
done
if [[ "${1:-start}" == "start" ]]; then open "http://localhost:$PORT"; fi
exit 0
