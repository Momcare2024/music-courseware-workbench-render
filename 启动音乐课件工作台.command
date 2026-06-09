#!/bin/zsh
set -e

cd /Users/linda/Documents/ppt-master-web

if [ ! -d ".venv" ]; then
  /Users/linda/.local/bin/python3.11 -m venv .venv
fi

source .venv/bin/activate
python -m pip install -r requirements.txt

python -m uvicorn app.main:app --host 127.0.0.1 --port 8765 &
SERVER_PID=$!

sleep 2
open http://127.0.0.1:8765

echo ""
echo "音乐课件工作台正在运行： http://127.0.0.1:8765"
echo "关闭这个窗口会停止网页服务。"
echo ""

wait $SERVER_PID
