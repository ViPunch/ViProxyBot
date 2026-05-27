#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="/opt/vpnbot"
APP_DIR="${APP_ROOT}/app"
BACKUPS_DIR="${APP_ROOT}/backups"
VENV_DIR="${APP_ROOT}/venv"
SERVICE_NAME="vpnbot"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo bash update.sh"
  exit 1
fi

TIMESTAMP="$(date +%Y%m%d%H%M%S)"
BACKUP_PATH="${BACKUPS_DIR}/pre-update-${TIMESTAMP}"

echo "==> Creating backup..."
mkdir -p "${BACKUPS_DIR}"
cp -R "${APP_DIR}" "${BACKUP_PATH}"

echo "==> Pulling updates..."
cd "${APP_DIR}"
git pull || { echo "git pull failed"; exit 1; }

echo "==> Installing dependencies..."
"${VENV_DIR}/bin/pip" install -e "${APP_DIR}[dev]" -q

echo "==> Restarting service..."
systemctl restart "${SERVICE_NAME}"

echo "Update complete. Backup at: ${BACKUP_PATH}"
