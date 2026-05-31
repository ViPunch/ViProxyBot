# ViProxyBot

Telegram-бот для управления VPN-протоколами на одном VPS: VLESS, Hysteria2 и MTProto.

Текущая концепция проекта пересматривается в сторону модели 3x-ui без web-панели:
one-command VPS installer ставит ядра, сервисы и SSL, а администрирование
выполняется через Telegram-бота. Новое ТЗ и инструкции для агентов:
`docs/01-product-rebuild-plan.md`.

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

После установки заполнить `.env` и перезапустить:

```bash
sudo nano /opt/vpnbot/.env
vi-proxy restart
```

На WSL (без systemd):

```bash
sudo nano /opt/vpnbot/.env
vi-proxy run
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
vi-proxy status
vi-proxy restart
vi-proxy enable
vi-proxy update
vi-proxy logs -f
```

**WSL / без systemd:**
```bash
vi-proxy run
```

Удаление для чистой переустановки:

```bash
sudo bash /opt/vpnbot/app/scripts/uninstall.sh
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
