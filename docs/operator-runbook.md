# VPNBot Operator Runbook

## Установка

```bash
sudo bash <(curl -fsSL <url>/scripts/install.sh) --repo <repo-url>
```

Или из локальной копии:

```bash
sudo bash scripts/install.sh
```

После установки:

```bash
sudo nano /opt/vpnbot/.env
vi-proxy restart
```

## Проверка статуса

```bash
vi-proxy status
vi-proxy enable
vi-proxy restart
vi-proxy logs -f
```

## Обновление

```bash
sudo bash /opt/vpnbot/app/scripts/update.sh
```

Или через launcher:

```bash
vi-proxy update
```

Скрипт автоматически:
1. Создаст backup
2. Скачает обновления
3. Переустановит зависимости
4. Перезапустит сервис

## Восстановление

```bash
sudo bash /opt/vpnbot/app/scripts/restore.sh /opt/vpnbot/backups/pre-update-YYYYMMDDHHMMSS
```

## Чистое удаление

```bash
sudo bash /opt/vpnbot/app/scripts/uninstall.sh
```

## Расположение файлов

| Путь | Назначение |
|---|---|
| `/opt/vpnbot/app` | Код приложения |
| `/opt/vpnbot/venv` | Python venv |
| `/opt/vpnbot/.env` | Конфигурация |
| `/opt/vpnbot/data/vpnbot.db` | SQLite база |
| `/opt/vpnbot/data/xray/` | Конфиги протоколов |
| `/opt/vpnbot/backups/` | Backup архивы |
| `/var/log/vpnbot/` | Логи |

## Firewall ports

| Протокол | Порт | Тип |
|---|---|---|
| VLESS | 443 | TCP |
| Hysteria2 | 443 | UDP |
| MTProto | 443 | TCP |

```bash
sudo ufw allow 443/tcp
sudo ufw allow 443/udp
```

## Emergency recovery

Если бот не запускается:

```bash
# Проверить логи
sudo journalctl -u vpnbot -n 50

# Проверить .env
sudo cat /opt/vpnbot/.env

# Ручной запуск для отладки
cd /opt/vpnbot/app
source /opt/vpnbot/venv/bin/activate
source /opt/vpnbot/.env
python -m src.main

# Откат к последнему backup
sudo bash /opt/vpnbot/app/scripts/restore.sh <backup-path>
```

## Backup вручную

```bash
sudo /opt/vpnbot/venv/bin/python -c "
import asyncio
from src.interface.telegram.bot import create_bot
from src.config import AppConfig
from src.services.backup_service import BackupService
# ... запустить backup через код
"
```

Или через бота: команда `/backup` (если реализована).
