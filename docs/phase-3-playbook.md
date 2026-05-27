# Phase 3 — Execution Playbook

Пошаговая инструкция для AI-агента. Код не дан — агент выбирает реализацию самостоятельно. Контракты, связи и проверки заданы жёстко.

**Предусловие:** Phase 2 полностью завершена. Все проверки из `phase-1-playbook.md` и `phase-2-playbook.md` проходят.**

**Перед началом прочитай `docs/00-overview-and-architecture.md` и `docs/phase-3-production.md`.**

---

## Принцип целостности

Phase 3 **укрепляет** продукт, не переписывает его.

Конкретно:
- `ProtocolAdapter` не трогается
- `ProtocolRegistry` не трогается
- `schema.py` не трогается (если не нужны новые таблицы для алертинга)
- `AppConfig` добавляет поля для rate limiting, alerting, auto-update
- `AuthMiddleware` не переписывается — к нему добавляется `RateLimitMiddleware`
- Telegram handlers не переписываются — к ним добавляется аудит-логирование
- Все Phase 1 и Phase 2 тесты должны оставаться зелёными

**Если шаг требует выбора — выбирай вариант минимально инвазивный.**

---

## Step 1: Rate Limiter

### Цель
Ограничение частоты команд для защиты от abuse.

### Файлы
- `src/infrastructure/rate_limiter.py`

### Контракт

`RateLimiter`:
- `configure(action: str, max_requests: int, window_seconds: int = 60)`
- `check(user_id: int, action: str) -> bool` — True = разрешено
- `get_remaining(user_id: int, action: str) -> int`

Поведение:
- хранит timestamps в памяти (не в БД)
- автоматически очищает expired entries
- возвращает False при превышении лимита

### Связи
- используется в `RateLimitMiddleware` из Step 5
- не зависит от других компонентов

### Проверка
```bash
python -c "
from src.infrastructure.rate_limiter import RateLimiter
rl = RateLimiter()
rl.configure('test', max_requests=2, window_seconds=60)
assert rl.check(123, 'test') is True
assert rl.check(123, 'test') is True
assert rl.check(123, 'test') is False
assert rl.get_remaining(123, 'test') == 0
print('OK')
"
```

---

## Step 2: Structured Logging

### Цель
Заменить basicConfig на JSON structured logging.

### Действие
В `src/main.py`:
- заменить `logging.basicConfig` на custom `JSONFormatter`
- формат: `{"timestamp": ..., "level": ..., "logger": ..., "message": ...}`
- опциональные поля: `event`, `actor_id`, `protocol`
- exception добавляется если есть

### Связи
- `shell_runner.py` redaction работает как раньше
- `AuditLogger` из Step 3 пишет через тот же logger

### Проверка
```bash
python -c "
import logging, json, io, sys
# Проверяем что JSONFormatter существует
from src.main import JSONFormatter  # если вынесен в модуль
# Или проверяем что main.py компилируется
import py_compile
py_compile.compile('src/main.py', doraise=True)
print('OK')
"
```

---

## Step 3: Audit Logger

### Цель
Структурированный аудит всех критичных действий.

### Файлы
- `src/domain/audit.py`

### Контракт

`AuditAction` (StrEnum):
- `BOT_START`, `INSTALL_PROTOCOL`, `CREATE_CLIENT`, `DELETE_CLIENT`, `GET_LINK`, `BACKUP`, `UPDATE`, `ADMIN_DENIED`, `RATE_LIMIT_HIT`

`AuditLogger`:
- `log(actor_id, action, target_type, target_id, status, details) -> None`
- пишет через `logging.getLogger("audit")`
- **не логирует секреты** (details redacted)

### Связи
- используется в Telegram handlers (commands, callback_router)
- используется в middleware (admin denied, rate limit)
- Phase 1 `AuditRepository` в БД может быть дополнен или заменён на file-only

### Проверка
```bash
python -c "
from src.domain.audit import AuditAction, AuditLogger
assert AuditAction.CREATE_CLIENT == 'create_client'
print('OK')
"
```

---

## Step 4: Alerting

### Цель
Уведомление администраторов о критичных событиях.

### Файлы
- `src/infrastructure/alerting.py`

### Контракт

`AlertLevel` (StrEnum): `INFO`, `WARNING`, `CRITICAL`

`Alert` (dataclass): level, title, message, source

`AlertDispatcher`:
- `register_handler(handler)`
- `send(alert: Alert) -> None`
- логирует алерт через logger
- вызывает все зарегистрированные handlers

`TelegramAlertHandler`:
- конструктор: `bot`, `admin_chat_ids: list[int]`
- отправляет форматированное сообщение в Telegram каждому admin

### Связи
- используется в `HealthChecker` (Step 6) при обнаружении failures
- используется в `BackupService` при backup failure
- используется в `Updater` при update failure

### Проверка
```bash
python -c "
from src.infrastructure.alerting import Alert, AlertDispatcher, AlertLevel
d = AlertDispatcher()
a = Alert(level=AlertLevel.WARNING, title='Test', message='msg', source='test')
# Не должно падать без handlers
import asyncio
asyncio.run(d.send(a))
print('OK')
"
```

---

## Step 5: Middleware Extensions

### Цель
Добавить rate limiting и аудит в middleware pipeline.

### Действие
В `src/interface/telegram/middleware.py` добавить:

`RateLimitMiddleware(BaseMiddleware)`:
- конструктор: `rate_limiter: RateLimiter`
- проверяет `rate_limiter.check(user_id, action)`
- при превышении: отвечает пользователю + логирует в audit
- action определяется по типу события (command, callback, message)

Порядок middleware в bot.py:
1. AuthMiddleware (первый — блокирует неавторизованных)
2. RateLimitMiddleware (второй — ограничивает частоту)

### Связи
- `AuthMiddleware` из Phase 1 не трогается
- `RateLimiter` из Step 1

### Проверка
```bash
python -c "
from src.interface.telegram.middleware import AuthMiddleware, RateLimitMiddleware
print('OK')
"
```

---

## Step 6: Health Checker

### Цель
Регулярная проверка здоровья всех компонентов.

### Файлы
- `src/services/health_checker.py`

### Контракт

`HealthReport` (dataclass):
- `bot_alive: bool`
- `db_healthy: bool`
- `protocols: dict[ProtocolType, bool]`
- `overall_healthy: bool`

`HealthChecker(registry)`:
- `check_all() -> HealthReport`
- опрашивает каждый protocol adapter через `health()`
- при failure — отправляет alert через `AlertDispatcher`

### Связи
- использует `ProtocolRegistry` из Phase 2
- использует `AlertDispatcher` из Step 4
- используется в `/status` command handler

### Проверка
```bash
python -c "
from src.services.health_checker import HealthChecker, HealthReport
print('OK')
"
```

---

## Step 7: Auto-Update

### Цель
Обновление бота с backup и rollback.

### Файлы
- `src/infrastructure/updater.py`

### Контракт

`Updater(app_dir, backups_dir, service_name)`:
- `check_for_updates() -> bool`
- `backup_before_update() -> str` — путь к backup
- `apply_update() -> bool` — pull + restart, при failure rollback

Поведение:
1. backup текущего состояния
2. `git pull`
3. `pip install -e .`
4. `systemctl restart vpnbot`
5. если шаг 3 или 4 fail → rollback из backup

### Связи
- использует `shell_runner`
- может отправлять alerts через `AlertDispatcher`

### Проверка
```bash
python -c "
from src.infrastructure.updater import Updater
print('OK')
"
```

---

## Step 8: Config Extensions

### Цель
Добавить production-поля в конфиг.

### Действие
В `src/config.py` добавить поля:
- `rate_limit_commands: int = 30`
- `rate_limit_heavy_ops: int = 5`
- `rate_limit_window: int = 60`
- `alert_chat_ids: list[int] = []`
- `auto_update_enabled: bool = False`
- `auto_update_check_interval: int = 3600`

### Связи
- существующие поля не меняются
- новые поля используются в RateLimiter, AlertDispatcher, Updater

### Проверка
```bash
python -c "from src.config import AppConfig; print('OK')"
```

---

## Step 9: Install Script Extensions

### Цель
Добавить log rotation и .env из шаблона.

### Действие
В `scripts/install.sh` добавить:
- создание `/etc/logrotate.d/vpnbot`
- копирование `.env.example` → `.env` если .env не существует

### Проверка
```bash
bash -n scripts/install.sh
```

---

## Step 10: Update и Restore Scripts

### Цель
Скрипты для ручного update и restore.

### Файлы
- `scripts/update.sh`
- `scripts/restore.sh`

### Контракты

**`update.sh`**:
1. проверяет root
2. создаёт backup
3. git pull
4. pip install
5. systemctl restart

**`restore.sh`**:
1. принимает путь к backup как аргумент
2. останавливает сервис
3. восстанавливает файлы и БД
4. запускает сервис

### Проверка
```bash
bash -n scripts/update.sh
bash -n scripts/restore.sh
```

---

## Step 11: Documentation

### Цель
User guide и operator runbook.

### Файлы
- `docs/user-guide.md`
- `docs/operator-runbook.md`

### Контракты

**`user-guide.md`** — описывает:
- как начать работу с ботом
- как установить каждый протокол
- как создать клиента и получить ссылку
- как смотреть трафик
- ограничения MTProto (нет per-client, только share link)
- troubleshooting

**`operator-runbook.md`** — описывает:
- установка (install.sh)
- проверка статуса
- обновление (update.sh)
- восстановление (restore.sh)
- расположение логов
- firewall ports
- emergency recovery

### Проверка
- файлы существуют и не пустые

---

## Step 12: CI Pipeline

### Цель
Автоматические проверки на каждый push/PR.

### Файлы
- `.github/workflows/ci.yml`

### Контракт

Pipeline:
1. checkout
2. setup Python 3.11
3. `pip install -e ".[dev]"`
4. `python -m pytest tests/ -v`
5. `python -m py_compile src/main.py`

### Связи
- запускает все тесты из Phase 1 + Phase 2 + Phase 3

### Проверка
```bash
# Проверяем синтаксис YAML
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"
```

---

## Step 13: Integration — bot.py

### Цель
Собрать все компоненты вместе.

### Действие
В `src/interface/telegram/bot.py`:
- инициализировать `RateLimiter` с конфигом
- добавить `RateLimitMiddleware` после `AuthMiddleware`
- инициализировать `AlertDispatcher` + `TelegramAlertHandler`
- инициализировать `HealthChecker`
- передать все через dispatcher data

### Проверка
```bash
python -m py_compile src/interface/telegram/bot.py
```

---

## Step 14: Tests

### Цель
Покрыть новые компоненты.

### Файлы
- `tests/test_rate_limiter.py`
- `tests/test_audit.py`

### Контракты тестов

**`test_rate_limiter.py`**:
- check возвращает True до лимита
- check возвращает False после лимита
- get_remaining показывает правильный остаток
- window reset работает

**`test_audit.py`**:
- AuditAction значения корректны
- AuditLogger не падает

### Проверка
```bash
python -m pytest tests/ -v
```
Все тесты Phase 1 + Phase 2 + Phase 3 должны быть зелёные.

---

## Глобальная проверка Phase 3

```bash
# 1. Все зависимости
pip install -e ".[dev]"

# 2. Все модули импортируются
python -c "from src.infrastructure.rate_limiter import RateLimiter"
python -c "from src.infrastructure.alerting import AlertDispatcher"
python -c "from src.infrastructure.updater import Updater"
python -c "from src.domain.audit import AuditLogger, AuditAction"
python -c "from src.services.health_checker import HealthChecker"

# 3. Phase 1 модули не сломаны
python -c "from src.infrastructure.protocols.vless.adapter import VlessAdapter"
python -c "from src.database.schema import SCHEMA_SQL"
python -c "from src.interface.telegram.middleware import AuthMiddleware"

# 4. Phase 2 модули не сломаны
python -c "from src.domain.capability import get_capabilities"
python -c "from src.infrastructure.protocols.hysteria2.adapter import Hysteria2Adapter"
python -c "from src.infrastructure.protocols.mtproto.adapter import MtprotoAdapter"
python -c "from src.services.protocol_registry import ProtocolRegistry"

# 5. ВСЕ тесты зелёные
python -m pytest tests/ -v

# 6. Скрипты валидны
bash -n scripts/install.sh
bash -n scripts/update.sh
bash -n scripts/restore.sh
```

---

## Финальная проверка целостности

После Phase 3 убедись что:

1. **Phase 1 тесты** зелёные
2. **Phase 2 тесты** зелёные
3. **Phase 3 тесты** зелёные
4. `ProtocolAdapter` интерфейс не изменился с Phase 1
5. `schema.py` DDL не переписан
6. `AppConfig.from_env()` работает с новыми полями (дефолты)
7. Все protocol adapters реализуют `ProtocolAdapter`
8. Capability model корректно скрывает MTProto client management
9. Rate limiting работает на commands и callbacks
10. Structured logging не содержит секретов
11. Audit trail логирует все критичные действия
12. Backup/restore scripts работают
13. CI pipeline зелёный
14. User guide и operator runbook написаны
