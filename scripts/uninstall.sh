#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="/opt/vpnbot"
SERVICE_NAME="vpnbot"
SERVICE_USER="vpnbot"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo bash uninstall.sh"
  exit 1
fi

echo "=========================================="
echo "  ViProxyBot Uninstall"
echo "=========================================="
echo ""
echo "This will remove:"
echo "  - systemd service ${SERVICE_NAME}"
echo "  - ${APP_ROOT}"
echo "  - /var/log/${SERVICE_NAME}"
echo "  - /etc/${SERVICE_NAME}"
echo "  - /usr/local/bin/vi-proxy"
echo "  - /usr/local/bin/vpnbot-ctl"
echo "  - system user ${SERVICE_USER}"
echo ""
read -rp "Continue? [y/N]: " CONFIRM </dev/tty
if [[ ! "${CONFIRM}" =~ ^[Yy]$ ]]; then
  echo "Aborted."
  exit 0
fi

if command -v systemctl >/dev/null 2>&1; then
  systemctl stop "${SERVICE_NAME}" 2>/dev/null || true
  systemctl disable "${SERVICE_NAME}" 2>/dev/null || true
fi

rm -f "/etc/systemd/system/${SERVICE_NAME}.service"
rm -f "/etc/logrotate.d/${SERVICE_NAME}"
rm -f "/etc/sudoers.d/${SERVICE_USER}"
rm -f /usr/local/bin/vi-proxy
rm -f /usr/local/bin/vpnbot-ctl
rm -rf "${APP_ROOT}"
rm -rf "/var/log/${SERVICE_NAME}"
rm -rf "/etc/${SERVICE_NAME}"

if id -u "${SERVICE_USER}" >/dev/null 2>&1; then
  userdel "${SERVICE_USER}" 2>/dev/null || true
fi

if command -v systemctl >/dev/null 2>&1; then
  systemctl daemon-reload
  systemctl reset-failed 2>/dev/null || true
fi

echo ""
echo "ViProxyBot removed. VPS is ready for a clean install."
