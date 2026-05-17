#!/usr/bin/env bash
set -euo pipefail

REPO=$(cd "$(dirname "$0")/.." && pwd)
cd "$REPO"

echo "==> Creating venv at $REPO/.venv"
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

echo "==> Installing systemd units"
sudo cp deploy/scoreboard-backend.service /etc/systemd/system/
sudo cp deploy/scoreboard-kiosk.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable scoreboard-backend.service scoreboard-kiosk.service

cat <<EOF

Done. To start now:
  sudo systemctl start scoreboard-backend
  sudo systemctl start scoreboard-kiosk

Or just run the backend manually:
  .venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000

Then open http://localhost:8000 (or http://raspberrypi.local:8000 from another device).
EOF
