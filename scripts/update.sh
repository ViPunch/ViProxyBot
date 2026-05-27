#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="/opt/vpnbot"
APP_DIR="${APP_ROOT}/app"
BACKUPS_DIR="${APP_ROOT}/backups"
VENV_DIR="${APP_ROOT}/venv"
SERVICE_NAME="vpnbot"

has_systemd() {
  pidof systemd >/dev/null 2>&1 || [[ -d /run/systemd/system ]]
}

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
if ! git pull; then
  echo "git pull failed. Restoring backup..."
  rm -rf "${APP_DIR}"
  cp -R "${BACKUP_PATH}" "${APP_DIR}"
  echo "Rolled back to backup."
  exit 1
fi

echo "==> Installing dependencies..."
if ! "${VENV_DIR}/bin/pip" install -e "${APP_DIR}" -q; then
  echo "pip install failed. Restoring backup..."
  rm -rf "${APP_DIR}"
  cp -R "${BACKUP_PATH}" "${APP_DIR}"
  "${VENV_DIR}/bin/pip" install -e "${APP_DIR}" -q
  echo "Rolled back to backup."
  exit 1
fi

if has_systemd; then
  echo "==> Restarting service..."
  systemctl restart "${SERVICE_NAME}"
  echo "Update complete. Backup at: ${BACKUP_PATH}"
else
  echo "Update complete. Backup at: ${BACKUP_PATH}"
  echo "Restart manually: ${APP_ROOT}/run.sh"
fi
