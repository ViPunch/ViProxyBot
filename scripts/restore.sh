#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="/opt/vpnbot"
APP_DIR="${APP_ROOT}/app"
VENV_DIR="${APP_ROOT}/venv"
SERVICE_NAME="vpnbot"

has_systemd() {
  pidof systemd >/dev/null 2>&1 || [[ -d /run/systemd/system ]]
}

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo bash restore.sh <backup-path>"
  exit 1
fi

BACKUP_PATH="${1:-}"
if [[ -z "${BACKUP_PATH}" || ! -d "${BACKUP_PATH}" ]]; then
  echo "Usage: sudo bash restore.sh /opt/vpnbot/backups/pre-update-YYYYMMDDHHMMSS"
  exit 1
fi

if has_systemd; then
  echo "==> Stopping service..."
  systemctl stop "${SERVICE_NAME}" || true
fi

echo "==> Restoring from ${BACKUP_PATH}..."
rm -rf "${APP_DIR}"
cp -R "${BACKUP_PATH}" "${APP_DIR}"

echo "==> Installing dependencies..."
"${VENV_DIR}/bin/pip" install -e "${APP_DIR}" -q

if has_systemd; then
  echo "==> Starting service..."
  systemctl start "${SERVICE_NAME}"
  echo "Restore complete."
else
  echo "Restore complete."
  echo "Restart manually: ${APP_ROOT}/run.sh"
fi
