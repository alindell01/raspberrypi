#!/usr/bin/env bash
set -euo pipefail

REPO=$(cd "$(dirname "$0")/.." && pwd)
RUN_USER="${SUDO_USER:-$USER}"
cd "$REPO"

echo "==> Repo:  $REPO"
echo "==> User:  $RUN_USER"

# Pi OS may need python3-venv explicitly.
if ! python3 -m venv --help >/dev/null 2>&1; then
  echo "==> Installing python3-venv"
  sudo apt-get update
  sudo apt-get install -y python3-venv
fi

if ! command -v chromium-browser >/dev/null 2>&1; then
  echo "==> Installing chromium-browser"
  sudo apt-get install -y chromium-browser || sudo apt-get install -y chromium
fi

echo "==> Creating venv at $REPO/.venv"
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

echo "==> Rendering systemd units"
TMP=$(mktemp -d)
for unit in scoreboard-backend.service scoreboard-kiosk.service; do
  sed -e "s|__USER__|$RUN_USER|g" -e "s|__REPO__|$REPO|g" \
    "deploy/$unit" > "$TMP/$unit"
done

echo "==> Installing systemd units"
sudo cp "$TMP/scoreboard-backend.service" /etc/systemd/system/
sudo cp "$TMP/scoreboard-kiosk.service"   /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable scoreboard-backend.service scoreboard-kiosk.service
rm -rf "$TMP"

# Allow the backend (running as $RUN_USER) to start/stop the kiosk and
# MagicMirror via passwordless sudo so the /control page can swap which
# app owns the TV display. Service names default to scoreboard-kiosk
# and magicmirror; override with SCOREBOARD_KIOSK_SERVICE and
# MAGICMIRROR_SERVICE env vars in the backend unit if yours differ.
echo "==> Installing sudoers entry for display swap"
SUDOERS_FILE=/etc/sudoers.d/scoreboard-display
sudo tee "$SUDOERS_FILE" >/dev/null <<EOF
$RUN_USER ALL=(ALL) NOPASSWD: /bin/systemctl start scoreboard-kiosk, /bin/systemctl stop scoreboard-kiosk, /bin/systemctl restart scoreboard-kiosk, /bin/systemctl is-active scoreboard-kiosk, /bin/systemctl start magicmirror, /bin/systemctl stop magicmirror, /bin/systemctl restart magicmirror, /bin/systemctl is-active magicmirror
EOF
sudo chmod 0440 "$SUDOERS_FILE"

cat <<EOF

==> Done.

Start now:
  sudo systemctl start scoreboard-backend
  sudo systemctl start scoreboard-kiosk

Logs:
  journalctl -u scoreboard-backend -f
  journalctl -u scoreboard-kiosk -f

Or run the backend directly (no kiosk, no sudo):
  .venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000
  # then open http://localhost:8000 in any browser on your LAN.
EOF
