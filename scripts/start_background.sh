#!/usr/bin/env bash
set -euo pipefail

cd /Users/linda/Documents/ppt-master-web
source .venv/bin/activate

mkdir -p logs
nohup python -m uvicorn app.main:app --host 127.0.0.1 --port 8765 \
  > logs/server.log 2>&1 &

echo $! > logs/server.pid
echo "音乐课件工作台已启动: http://127.0.0.1:8765"
