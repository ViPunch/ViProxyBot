#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="/opt/vpnbot"
APP_DIR="${APP_ROOT}/app"
DATA_DIR="${APP_ROOT}/data"
BACKUPS_DIR="${APP_ROOT}/backups"
LOG_DIR="/var/log/vpnbot"
CERT_DIR="/etc/vpnbot/certs"
SERVICE_USER="vpnbot"
VENV_DIR="${APP_ROOT}/venv"
ENV_FILE="${APP_ROOT}/.env"
REPO_URL="https://github.com/ViPunch/ViProxyBot.git"
REPO_BRANCH="main"

has_systemd() {
  pidof systemd >/dev/null 2>&1 || [[ -d /run/systemd/system ]]
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo) REPO_URL="$2"; shift 2 ;;
    --branch) REPO_BRANCH="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: sudo bash install.sh [--repo <url>] [--branch <name>]"
      echo "   or: curl -fsSL https://raw.githubusercontent.com/ViPunch/ViProxyBot/main/scripts/install.sh | sudo bash"
      exit 0
      ;;
    *) echo "Unknown: $1"; exit 1 ;;
  esac
done

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo bash install.sh"
  echo "Remote install: curl -fsSL https://raw.githubusercontent.com/ViPunch/ViProxyBot/main/scripts/install.sh | sudo bash"
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive

echo ""
echo "=========================================="
echo "  ViProxyBot Installer"
echo "=========================================="
echo ""

echo "==> Installing system packages..."
apt-get update -qq
apt-get install -y -qq \
  git curl unzip python3 python3-venv python3-pip \
  ca-certificates openssl >/dev/null

echo "==> Creating directories..."
mkdir -p "${APP_ROOT}" "${DATA_DIR}" "${BACKUPS_DIR}" "${LOG_DIR}" "${CERT_DIR}"

if ! id -u "${SERVICE_USER}" >/dev/null 2>&1; then
  useradd --system --home "${APP_ROOT}" --shell /usr/sbin/nologin "${SERVICE_USER}"
fi

echo "==> Copying application..."
if [[ -n "${REPO_URL}" ]]; then
  TMP_DIR="$(mktemp -d)"
  git clone --depth 1 --branch "${REPO_BRANCH}" "${REPO_URL}" "${TMP_DIR}"
  rm -rf "${APP_DIR}"
  mkdir -p "${APP_DIR}"
  cp -R "${TMP_DIR}/." "${APP_DIR}"
  rm -rf "${TMP_DIR}"
else
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
  rm -rf "${APP_DIR}"
  mkdir -p "${APP_DIR}"
  cp -R "${PROJECT_DIR}/." "${APP_DIR}"
fi

echo "==> Installing vpnbot-ctl..."
install -m 0755 "${APP_DIR}/scripts/vpnbot-ctl" /usr/local/bin/vpnbot-ctl

echo "==> Creating venv and installing dependencies..."
python3 -m venv "${VENV_DIR}"
"${VENV_DIR}/bin/pip" install --upgrade pip -q
"${VENV_DIR}/bin/pip" install -e "${APP_DIR}" -q

echo "==> Installing vi-proxy launcher..."
cat > /usr/local/bin/vi-proxy <<EOF
#!/usr/bin/env bash
set -euo pipefail
exec "${VENV_DIR}/bin/vi-proxy" "$@"
EOF
chmod 0755 /usr/local/bin/vi-proxy

if [[ ! -f "${ENV_FILE}" ]]; then
  echo ""
  echo "=========================================="
  echo "  Configuration Wizard"
  echo "=========================================="
  echo ""

  while true; do
    read -rp "Telegram Bot Token: " BOT_TOKEN_INPUT </dev/tty
    [[ -n "${BOT_TOKEN_INPUT}" ]] && break
    echo "  Token cannot be empty."
  done

  while true; do
    read -rp "Telegram Admin User ID: " ADMIN_IDS_INPUT </dev/tty
    [[ "${ADMIN_IDS_INPUT}" =~ ^[0-9]+(,[0-9]+)*$ ]] && break
    echo "  Enter numeric ID (or comma-separated, no spaces)."
  done

  VPS_IP_INPUT="$(curl -sf --max-time 5 https://api.ipify.org 2>/dev/null \
    || curl -sf --max-time 5 https://ifconfig.me 2>/dev/null \
    || curl -sf --max-time 5 https://icanhazip.com 2>/dev/null \
    || true)"
  VPS_IP_INPUT="${VPS_IP_INPUT//[^0-9.]/}"

  if [[ -z "${VPS_IP_INPUT}" ]]; then
    echo "  Could not auto-detect IP. Enter manually:"
    read -rp "Public IP: " VPS_IP_INPUT </dev/tty
  fi
  echo "  Detected IP: ${VPS_IP_INPUT}"

  echo ""
  echo "--- Public Host ---"
  echo "  If you have a domain, enter it for SSL certificates."
  echo "  Leave blank to use IP (${VPS_IP_INPUT})."
  read -rp "Domain (optional): " DOMAIN_INPUT </dev/tty

  if [[ -n "${DOMAIN_INPUT}" ]]; then
    PUBLIC_HOST_INPUT="${DOMAIN_INPUT}"
  else
    PUBLIC_HOST_INPUT="${VPS_IP_INPUT}"
  fi

  echo ""
  echo "--- SSL Certificate ---"
  echo "  1) Domain (Let's Encrypt via acme.sh, requires domain with A record)"
  echo "  2) IP (Let's Encrypt for IP address, short-lived but real cert)"
  echo "  3) Self-signed (10 years, browser warning, works everywhere)"
  echo ""
  while true; do
    read -rp "SSL mode [1/2/3]: " SSL_CHOICE </dev/tty
    case "${SSL_CHOICE}" in
      1)
        if [[ -z "${DOMAIN_INPUT}" ]]; then
          echo "  Domain is required. Enter domain first."
          continue
        fi
        SSL_MODE_INPUT="domain"
        SSL_CERT_PATH_INPUT=""
        SSL_KEY_PATH_INPUT=""
        echo "  Will issue Let's Encrypt cert for ${DOMAIN_INPUT}"
        break
        ;;
      2)
        SSL_MODE_INPUT="ip"
        SSL_CERT_PATH_INPUT=""
        SSL_KEY_PATH_INPUT=""
        echo "  Will issue Let's Encrypt cert for IP ${VPS_IP_INPUT}"
        break
        ;;
      3)
        SSL_MODE_INPUT="selfsigned"
        SSL_CERT_PATH_INPUT=""
        SSL_KEY_PATH_INPUT=""
        echo "  Will generate self-signed cert (10 years)"
        break
        ;;
      *) echo "  Enter 1, 2, or 3." ;;
    esac
  done

  echo ""
  echo "--- Hysteria2 (optional, UDP/QUIC VPN) ---"
  VLESS_PORT_INPUT="443"
  read -rp "Install Hysteria2? [y/N]: " INSTALL_HYSTERIA </dev/tty
  HYSTERIA_PORT_INPUT=""
  if [[ "${INSTALL_HYSTERIA}" =~ ^[Yy] ]]; then
    if [[ "${VLESS_PORT_INPUT}" == "443" ]]; then
      HYSTERIA_PORT_INPUT="443"
      echo "  Hysteria2 will use UDP 443 (VLESS uses TCP 443, no conflict)."
    else
      read -rp "Hysteria2 UDP port [443]: " HYSTERIA_PORT_INPUT </dev/tty
      HYSTERIA_PORT_INPUT="${HYSTERIA_PORT_INPUT:-443}"
    fi
  fi

  ENCRYPTION_KEY_INPUT="$(python3 -c \
    "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).rstrip(b'=').decode())")"

  cat > "${ENV_FILE}" <<ENVEOF
BOT_TOKEN=${BOT_TOKEN_INPUT}
ADMIN_IDS=${ADMIN_IDS_INPUT}
ENCRYPTION_KEY=${ENCRYPTION_KEY_INPUT}
VPS_PUBLIC_IP=${VPS_IP_INPUT}
PUBLIC_HOST=${PUBLIC_HOST_INPUT}
SSL_MODE=${SSL_MODE_INPUT}
DOMAIN=${DOMAIN_INPUT}
SSL_CERT_PATH=${SSL_CERT_PATH_INPUT}
SSL_KEY_PATH=${SSL_KEY_PATH_INPUT}
HYSTERIA_PORT=${HYSTERIA_PORT_INPUT}
ENVEOF
  chmod 600 "${ENV_FILE}"
  chown "${SERVICE_USER}:${SERVICE_USER}" "${ENV_FILE}"

  echo ""
  echo "  Configuration saved to ${ENV_FILE}"
  echo "  ENCRYPTION_KEY backed up — store it safely for recovery."
  echo ""

  if [[ "${SSL_MODE_INPUT}" == "domain" ]]; then
    echo "==> Issuing Let's Encrypt certificate for ${DOMAIN_INPUT}..."
    "${VENV_DIR}/bin/python" -c "
import asyncio, sys
sys.path.insert(0, '${APP_DIR}')
from src.infrastructure.ssl_manager import issue_certificate
r = asyncio.run(issue_certificate('${DOMAIN_INPUT}'))
if r.success:
    print(f'  Certificate: {r.cert_path}')
    print(f'  Key: {r.key_path}')
else:
    print(f'  FAILED: {r.error}')
    sys.exit(1)
"
  elif [[ "${SSL_MODE_INPUT}" == "ip" ]]; then
    echo "==> Issuing Let's Encrypt certificate for IP ${VPS_IP_INPUT}..."
    "${VENV_DIR}/bin/python" -c "
import asyncio, sys
sys.path.insert(0, '${APP_DIR}')
from src.infrastructure.ssl_manager import issue_certificate
r = asyncio.run(issue_certificate('${VPS_IP_INPUT}', is_ip=True))
if r.success:
    print(f'  Certificate: {r.cert_path}')
    print(f'  Key: {r.key_path}')
else:
    print(f'  FAILED: {r.error}')
    sys.exit(1)
"
  elif [[ "${SSL_MODE_INPUT}" == "selfsigned" ]]; then
    echo "==> Generating self-signed certificate (10 years)..."
    "${VENV_DIR}/bin/python" -c "
import asyncio, sys
sys.path.insert(0, '${APP_DIR}')
from src.infrastructure.ssl_manager import generate_self_signed_cert
r = asyncio.run(generate_self_signed_cert('${PUBLIC_HOST_INPUT}'))
if r.success:
    print(f'  Certificate: {r.cert_path}')
    print(f'  Key: {r.key_path}')
else:
    print(f'  FAILED: {r.error}')
    sys.exit(1)
"
  fi
fi

chown -R "${SERVICE_USER}:${SERVICE_USER}" "${DATA_DIR}"
chown -R "${SERVICE_USER}:${SERVICE_USER}" "${BACKUPS_DIR}"
chown -R "${SERVICE_USER}:${SERVICE_USER}" "${LOG_DIR}"

if [[ -f "${ENV_FILE}" ]]; then
  chown "${SERVICE_USER}:${SERVICE_USER}" "${ENV_FILE}"
  ln -sf "${ENV_FILE}" "${APP_DIR}/.env"
  chown -h "${SERVICE_USER}:${SERVICE_USER}" "${APP_DIR}/.env"
fi

echo "==> Configuring sudoers for ${SERVICE_USER}..."
cat > "/etc/sudoers.d/${SERVICE_USER}" <<SUDOEOF
${SERVICE_USER} ALL=(ALL) NOPASSWD: /usr/local/bin/vpnbot-ctl
SUDOEOF
chmod 440 "/etc/sudoers.d/${SERVICE_USER}"

RUN_SCRIPT="${APP_ROOT}/run.sh"
cat > "${RUN_SCRIPT}" <<RUNEOF
#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR}"
source "${VENV_DIR}/bin/activate"
set -a
source "${ENV_FILE}"
set +a
exec python -m src.main
RUNEOF
chmod +x "${RUN_SCRIPT}"

echo "==> Configuring log rotation..."
cat > /etc/logrotate.d/vpnbot <<LOGEOF
/var/log/vpnbot/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 ${SERVICE_USER} ${SERVICE_USER}
}
LOGEOF

if has_systemd; then
  echo "==> Configuring systemd service..."
  cat > /etc/systemd/system/vpnbot.service <<EOF
[Unit]
Description=ViProxyBot Telegram service
After=network.target

[Service]
Type=simple
User=${SERVICE_USER}
WorkingDirectory=${APP_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=${VENV_DIR}/bin/python -m src.main
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
  systemctl daemon-reload
  systemctl enable vpnbot.service

  systemctl start vpnbot.service
  echo ""
  echo "=========================================="
  echo "  ViProxyBot installed and started!"
  echo "=========================================="
  echo ""
  echo "  Open your bot in Telegram and send /start"
  echo ""
  echo "  Management:"
  echo "    Status:  vi-proxy status"
  echo "    Logs:    vi-proxy logs -f"
  echo "    Enable:  vi-proxy enable"
  echo "    Stop:    vi-proxy stop"
  echo "    Start:   vi-proxy start"
  echo "    Restart: vi-proxy restart"
  echo "    Update:  vi-proxy update"
  echo "    Remove:  sudo bash ${APP_DIR}/scripts/uninstall.sh"
  echo ""
else
  echo ""
  echo "=========================================="
  echo "  ViProxyBot installed!"
  echo "=========================================="
  echo ""
  echo "  Start: vi-proxy run"
  echo "  Run script: ${RUN_SCRIPT}"
  echo "  Update: vi-proxy update"
  echo "  Remove: sudo bash ${APP_DIR}/scripts/uninstall.sh"
  echo "  systemd not detected, use the run script above."
  echo ""
fi
