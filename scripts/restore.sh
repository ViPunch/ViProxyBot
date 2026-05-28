#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="/opt/vpnbot"
APP_DIR="${APP_ROOT}/app"
DATA_DIR="${APP_ROOT}/data"
VENV_DIR="${APP_ROOT}/venv"
BACKUPS_DIR="${APP_ROOT}/backups"
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
  echo ""
  echo "Available backups:"
  ls -d "${BACKUPS_DIR}"/pre-update-* 2>/dev/null || echo "  (none)"
  exit 1
fi

PRE_RESTORE_DIR="${BACKUPS_DIR}/pre-restore-$(date -u +%Y%m%d%H%M%S)"
echo "==> Creating pre-restore backup at ${PRE_RESTORE_DIR}..."
mkdir -p "${PRE_RESTORE_DIR}"
if [[ -d "${APP_DIR}" ]]; then
  cp -R "${APP_DIR}" "${PRE_RESTORE_DIR}/app"
fi
if [[ -f "${DATA_DIR}/vpnbot.db" ]]; then
  cp "${DATA_DIR}/vpnbot.db" "${PRE_RESTORE_DIR}/vpnbot.db"
fi

if has_systemd; then
  echo "==> Stopping service..."
  systemctl stop "${SERVICE_NAME}" || true
fi

echo "==> Restoring from ${BACKUP_PATH}..."
rm -rf "${APP_DIR}"
cp -R "${BACKUP_PATH}" "${APP_DIR}"

DB_BACKUP=$(find "${BACKUP_PATH}" -name "vpnbot-*.db" -type f 2>/dev/null | head -1)
if [[ -n "${DB_BACKUP}" ]]; then
  echo "==> Restoring database from ${DB_BACKUP}..."
  mkdir -p "${DATA_DIR}"
  cp "${DB_BACKUP}" "${DATA_DIR}/vpnbot.db"
  chown vpnbot:vpnbot "${DATA_DIR}/vpnbot.db"
fi

echo "==> Installing dependencies..."
"${VENV_DIR}/bin/pip" install -e "${APP_DIR}" -q

if has_systemd; then
  echo "==> Starting service..."
  systemctl start "${SERVICE_NAME}"
  sleep 3
  if systemctl is-active --quiet "${SERVICE_NAME}"; then
    echo "Restore complete. Service is active."
  else
    echo "WARNING: Service failed to start. Check: journalctl -u ${SERVICE_NAME} -n 20"
    echo "Pre-restore backup at: ${PRE_RESTORE_DIR}"
  fi
else
  echo "Restore complete."
  echo "Restart manually: ${APP_ROOT}/run.sh"
fi
