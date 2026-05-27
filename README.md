# ViProxyBot

Telegram-бот для управления VPN-протоколами на одном VPS: VLESS, Hysteria2 и MTProto.

## Возможности

- Установка и управление VPN через Telegram без CLI
- VLESS (Xray-core), Hysteria2, MTProto Proxy
- Создание/удаление клиентов, генерация ссылок
- Inline UI с навигацией по протоколам
- Автоматический backup конфигов и БД
- RU / EN по языку Telegram

## Быстрый старт (VPS / WSL)

Одна команда — бот установится как сервис:

```bash
curl -fsSL https://raw.githubusercontent.com/ViPunch/ViProxyBot/main/scripts/install.sh | sudo bash
```

Или если код уже скачан:

```bash
sudo bash scripts/install.sh
```

После установки заполнить `.env` и запустить:

```bash
sudo nano /opt/vpnbot/.env
sudo systemctl restart vpnbot
```

На WSL (без systemd):

```bash
sudo nano /opt/vpnbot/.env
/opt/vpnbot/run.sh
```

## Заполнение .env

| Поле | Откуда |
|---|---|
| `BOT_TOKEN` | `@BotFather` → `/newbot` |
| `ADMIN_IDS` | `@userinfobot` → ваш числовой ID |
| `ENCRYPTION_KEY` | Любая строка ≥ 16 символов |
| `VPS_PUBLIC_IP` | IP вашего VPS |

```env
BOT_TOKEN=123456:ABC-DEF
ADMIN_IDS=123456789
ENCRYPTION_KEY=my-secret-key-at-least-16
VPS_PUBLIC_IP=1.2.3.4
```

## Быстрый старт (Windows локально)

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env
# заполнить .env
python -m src.main
```

## Структура на VPS

```
/opt/vpnbot/
├── app/          — код приложения
├── venv/         — Python venv
├── .env          — конфигурация
├── data/         — SQLite, конфиги протоколов
├── backups/      — backup архивы
└── run.sh        — скрипт запуска (для WSL)
```

## Команды

**systemd (VPS):**
```bash
sudo systemctl status vpnbot
sudo systemctl restart vpnbot
sudo journalctl -u vpnbot -f
```

**WSL / без systemd:**
```bash
/opt/vpnbot/run.sh
```

## Разработка

```bash
pip install -e ".[dev]"
ruff check .
mypy src
python -m pytest tests/ -v
bash -n scripts/install.sh
```

## Стек

- Python 3.11+
- aiogram 3.x (Telegram)
- SQLite (aiosqlite)
- pydantic, cryptography, httpx, PyYAML
