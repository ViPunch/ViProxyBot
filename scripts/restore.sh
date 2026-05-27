#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="/opt/vpnbot"
APP_DIR="${APP_ROOT}/app"
BACKUPS_DIR="${APP_ROOT}/backups"
VENV_DIR="${APP_ROOT}/venv"
SERVICE_NAME="vpnbot"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo bash restore.sh <backup-path>"
  exit 1
fi

BACKUP_PATH="${1:-}"
if [[ -z "${BACKUP_PATH}" || ! -d "${BACKUP_PATH}" ]]; then
  echo "Usage: bash restore.sh /opt/vpnbot/backups/pre-update-YYYYMMDDHHMMSS"
  exit 1
fi

echo "==> Stopping service..."
systemctl stop "${SERVICE_NAME}" || true

echo "==> Restoring from ${BACKUP_PATH}..."
rm -rf "${APP_DIR}"
cp -R "${BACKUP_PATH}" "${APP_DIR}"

echo "==> Installing dependencies..."
"${VENV_DIR}/bin/pip" install -e "${APP_DIR}[dev]" -q

echo "==> Starting service..."
systemctl start "${SERVICE_NAME}"

echo "Restore complete."
