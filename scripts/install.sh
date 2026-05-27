#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="/opt/vpnbot"
APP_DIR="${APP_ROOT}/app"
DATA_DIR="${APP_ROOT}/data"
BACKUPS_DIR="${APP_ROOT}/backups"
LOG_DIR="/var/log/vpnbot"
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
      exit 0
      ;;
    *) echo "Unknown: $1"; exit 1 ;;
  esac
done

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo bash install.sh"
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive

echo "==> Installing system packages..."
apt-get update -qq
apt-get install -y -qq git curl unzip python3 python3-venv python3-pip ca-certificates >/dev/null

echo "==> Creating directories..."
mkdir -p "${APP_ROOT}" "${DATA_DIR}" "${BACKUPS_DIR}" "${LOG_DIR}"

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

echo "==> Creating venv and installing dependencies..."
python3 -m venv "${VENV_DIR}"
"${VENV_DIR}/bin/pip" install --upgrade pip -q
"${VENV_DIR}/bin/pip" install -e "${APP_DIR}" -q

if [[ ! -f "${ENV_FILE}" ]]; then
  echo
  echo "==> Настройка бота (Configuration wizard)"
  echo

  while true; do
    read -rp "Telegram Bot Token: " BOT_TOKEN_INPUT </dev/tty
    [[ -n "${BOT_TOKEN_INPUT}" ]] && break
    echo "  Токен не может быть пустым."
  done

  while true; do
    read -rp "Ваш Telegram User ID (Admin ID): " ADMIN_IDS_INPUT </dev/tty
    [[ "${ADMIN_IDS_INPUT}" =~ ^[0-9]+(,[0-9]+)*$ ]] && break
    echo "  Введите числовой ID (или несколько через запятую, без пробелов)."
  done

  VPS_IP_INPUT="$(curl -sf --max-time 5 https://api.ipify.org 2>/dev/null \
    || curl -sf --max-time 5 https://ifconfig.me 2>/dev/null \
    || curl -sf --max-time 5 https://icanhazip.com 2>/dev/null \
    || true)"
  VPS_IP_INPUT="${VPS_IP_INPUT//[^0-9.]/}"

  if [[ -z "${VPS_IP_INPUT}" ]]; then
    echo "  Не удалось определить IP. Введите вручную:"
    read -rp "Публичный IP: " VPS_IP_INPUT </dev/tty
  fi

  ENCRYPTION_KEY_INPUT="$(python3 -c \
    "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).rstrip(b'=').decode())")"

  cat > "${ENV_FILE}" <<ENVEOF
BOT_TOKEN=${BOT_TOKEN_INPUT}
ADMIN_IDS=${ADMIN_IDS_INPUT}
ENCRYPTION_KEY=${ENCRYPTION_KEY_INPUT}
VPS_PUBLIC_IP=${VPS_IP_INPUT}
ENVEOF
  chmod 600 "${ENV_FILE}"
  chown "${SERVICE_USER}:${SERVICE_USER}" "${ENV_FILE}"

  echo
  echo "  Сгенерированный ENCRYPTION_KEY (сохраните на случай восстановления):"
  echo "  ${ENCRYPTION_KEY_INPUT}"
  echo
fi

chown -R "${SERVICE_USER}:${SERVICE_USER}" "${DATA_DIR}"
chown -R "${SERVICE_USER}:${SERVICE_USER}" "${BACKUPS_DIR}"
chown -R "${SERVICE_USER}:${SERVICE_USER}" "${LOG_DIR}"

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
  echo
  echo "ViProxyBot установлен и запущен."
  echo "Откройте бота в Telegram и отправьте /start"
  echo
  echo "Управление:"
  echo "  Статус:  systemctl status vpnbot"
  echo "  Логи:    journalctl -u vpnbot -f"
  echo "  Стоп:    systemctl stop vpnbot"
else
  echo
  echo "ViProxyBot установлен."
  echo "Запуск: sudo ${RUN_SCRIPT}"
  echo
  echo "systemd не обнаружен, используйте run script выше."
fi
