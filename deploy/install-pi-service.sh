#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/web-spectrometer}"
CONFIG_DIR="${CONFIG_DIR:-/etc/web-spectrometer}"
LEGACY_CONFIG_DIR="${LEGACY_CONFIG_DIR:-/etc/bluetooth-spectrometer}"
SERVICE_USER="${SERVICE_USER:-pi}"
SERVICE_NAME="web-spectrometer.service"
LEGACY_SERVICE_NAME="bluetooth-spectrometer.service"
SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME"

boot_dir() {
  if [ -d /boot/firmware ]; then
    printf '%s\n' /boot/firmware
  else
    printf '%s\n' /boot
  fi
}

disable_camera_led() {
  [ "${DISABLE_CAMERA_LED:-1}" = "1" ] || return 0
  local config_txt
  config_txt="$(boot_dir)/config.txt"
  sudo touch "$config_txt"
  if ! sudo grep -Eq '^# Web Spectrometer camera LED setting v2$' "$config_txt"; then
    {
      printf '\n'
      printf '[all]\n'
      printf '# Web Spectrometer camera LED setting v2\n'
      printf 'disable_camera_led=1\n'
    } | sudo tee -a "$config_txt" >/dev/null
    echo "Configured camera LED off in $config_txt. Reboot the Pi for this to take effect."
  fi
}

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required" >&2
  exit 1
fi

sudo mkdir -p "$APP_DIR" "$CONFIG_DIR"
sudo rsync -a --delete --delete-excluded \
  --exclude ".venv" \
  --exclude "__pycache__" \
  --exclude ".pytest_cache" \
  --exclude "build" \
  --exclude "release" \
  --exclude "desktop" \
  --exclude "ui" \
  --exclude "web" \
  ./ "$APP_DIR/"

sudo python3 -m venv --system-site-packages "$APP_DIR/.venv"
sudo "$APP_DIR/.venv/bin/python" -m pip install --upgrade pip
sudo "$APP_DIR/.venv/bin/python" -m pip install -r "$APP_DIR/requirements-pi.txt"

if [ ! -f "$CONFIG_DIR/config.json" ] && [ -f "$LEGACY_CONFIG_DIR/config.json" ]; then
  sudo cp "$LEGACY_CONFIG_DIR/config.json" "$CONFIG_DIR/config.json"
  echo "Migrated $LEGACY_CONFIG_DIR/config.json to $CONFIG_DIR/config.json"
fi

if [ ! -f "$CONFIG_DIR/config.json" ]; then
  TOKEN="$("$APP_DIR/.venv/bin/python" -c 'import secrets; print(secrets.token_urlsafe(9))')"
  sudo "$APP_DIR/.venv/bin/python" "$APP_DIR/deploy/write_config.py" "$CONFIG_DIR/config.json" "$TOKEN"
  echo "Created $CONFIG_DIR/config.json"
  echo "Spectrometer access code: $TOKEN"
fi

sudo systemctl disable --now "$LEGACY_SERVICE_NAME" 2>/dev/null || true
sudo rm -f "/etc/systemd/system/$LEGACY_SERVICE_NAME"
disable_camera_led

sudo cp "$APP_DIR/deploy/web-spectrometer.service" "$SERVICE_FILE"
sudo sed -i "s/^User=.*/User=$SERVICE_USER/" "$SERVICE_FILE"
sudo systemctl daemon-reload
sudo systemctl enable --now "$SERVICE_NAME"
sudo systemctl --no-pager status "$SERVICE_NAME"
echo
HOSTNAME="$(hostname 2>/dev/null || printf 'raspberrypi')"
echo "Spectrometer API: http://${HOSTNAME}.local:8765/"
echo "API docs: http://${HOSTNAME}.local:8765/docs"
echo "If mDNS is not available on your network, use the Pi IP address with port 8765."
