# Phase 1 — Execution Playbook

Пошаговая инструкция для AI-агента. Код не дан — агент выбирает реализацию самостоятельно. Но контракты, связи и проверки заданы жёстко.

**Перед началом прочитай `docs/00-overview-and-architecture.md` и `docs/phase-1-mvp.md`.**

---

## Принцип целостности

Phase 1 закладывает **фундамент**, который Phase 2 и Phase 3 будут расширять, а не переписывать.

Конкретно:
- доменные типы (`ProtocolType`, `ClientAccount`, `ProtocolInstallation`) используются во всех фазах без изменений;
- интерфейс `ProtocolAdapter` расширяется (новые методы), но не переломается;
- схема БД только дополняется миграциями, не переписывается;
- Telegram handler layer расширяется (inline keyboard), но базовая архитектура остаётся;
- конфиг `AppConfig` добавляет поля, но не меняет существующие.

**Если шаг требует выбора — выбирай вариант, который проще расширить в Phase 2/3.**

---

## Стек (фиксирован на все фазы)

- Python 3.11+
- aiogram 3.x — Telegram framework
- aiosqlite — async SQLite
- pydantic — валидация данных
- cryptography — шифрование секретов
- asyncio.subprocess — shell commands

Phase 2 добавит: httpx, PyYAML. Phase 3 добавит: nothing new.

---

## Step 1: Инициализация проекта

### Цель
Создать структуру проекта, `pyproject.toml`, `.gitignore`, `.env.example`.

### Файлы
- `pyproject.toml`
- `.gitignore`
- `.env.example`
- `src/__init__.py`

### Контракты

**`pyproject.toml`** — фиксирует:
- `name = "vpnbot"`
- `requires-python = ">=3.11"`
- dependencies: aiogram, aiosqlite, pydantic, cryptography
- optional dev-dependencies: pytest, pytest-asyncio
- pytest config: `asyncio_mode = "auto"`, `testpaths = ["tests"]`

**`.env.example`** — содержит шаблон для:
- `BOT_TOKEN`
- `ADMIN_IDS` (comma-separated)
- `ENCRYPTION_KEY`
- `VPS_PUBLIC_IP`

**`.gitignore`** — обязательно игнорирует:
- `__pycache__/`, `*.pyc`
- `.env`
- `*.db`, `*.db-journal`
- `.venv/`, `venv/`

### Проверка
```bash
pip install -e ".[dev]"
python -c "import aiogram; import aiosqlite; import pydantic; import cryptography"
```
Все импорты должны пройти без ошибок.

---

## Step 2: Config

### Цель
Единая точка загрузки конфигурации из env.

### Файлы
- `src/config.py`

### Контракт

`AppConfig` — pydantic BaseModel:
- `bot_token: str`
- `admin_ids: list[int]`
- `encryption_key: str`
- `vps_public_ip: str`
- `db_path: Path`
- `backups_dir: Path`
- `xray_config_dir: Path`

Фабричный метод `from_env()` загружает из `os.environ`.

### Связи
- используется в `main.py`, `bot.py`, всех сервисах
- Phase 2/3 добавляют поля, но не меняют существующие

### Проверка
```bash
python -c "from src.config import AppConfig; print('OK')"
```

---

## Step 3: Domain — enums, models, exceptions

### Цель
Доменные типы, используемые во всех слоях.

### Файлы
- `src/domain/__init__.py`
- `src/domain/enums.py`
- `src/domain/models.py`
- `src/domain/exceptions.py`

### Контракты

**`enums.py`** — три StrEnum:
- `ProtocolType`: `vless`, `hysteria2`, `mtproto`
- `ProtocolStatus`: `not_installed`, `installing`, `active`, `degraded`, `failed`, `disabled`
- `ClientStatus`: `active`, `revoked`

**`models.py`** — pydantic BaseModel:
- `ProtocolInstallation`: protocol, status, listen_port, service_name, config_path, installed_at, updated_at
- `ClientAccount`: id, protocol, external_name, status, created_at
- `ClientCredential`: id, client_id, protocol, uuid, created_at
- `TrafficSnapshot`: id, protocol, client_id, rx_bytes, tx_bytes, collected_at
- `AuditEvent`: id, actor_telegram_user_id, action, target_type, target_id, status, details_redacted, created_at

**`exceptions.py`** — иерархия:
- `VPNBotError` (base)
- `ProtocolNotInstalledError`
- `PortInUseError`
- `ClientNotFoundError`
- `ClientAlreadyExistsError`
- `ConfigValidationError`
- `ServiceReloadError`
- `UnauthorizedError`

### Связи
- импортируются везде: database, infrastructure, services, interface
- Phase 2 не меняет эти типы, Phase 3 не меняет эти типы
- `ProtocolType.HYSTERIA2` и `ProtocolType.MTPROTO` определены здесь, хотя Phase 1 реализует только VLESS

### Проверка
```bash
python -c "
from src.domain.enums import ProtocolType, ProtocolStatus, ClientStatus
from src.domain.models import ProtocolInstallation, ClientAccount
from src.domain.exceptions import VPNBotError, PortInUseError
assert ProtocolType.HYSTERIA2 == 'hysteria2'
assert ProtocolType.MTPROTO == 'mtproto'
print('OK')
"
```

---

## Step 4: Database — connection, schema, repositories

### Цель
SQLite — единственный source of truth для состояния бота.

### Файлы
- `src/database/__init__.py`
- `src/database/connection.py`
- `src/database/schema.py`
- `src/database/repositories.py`

### Контракты

**`connection.py`**:
- `set_db_path(path: Path)` — глобальная настройка
- `get_connection() -> aiosqlite.Connection` — возвращает connection с WAL mode и foreign keys

**`schema.py`** — DDL для таблиц:
- `admins` (telegram_user_id PK, is_active, created_at, last_seen_at)
- `protocol_installations` (protocol PK, status, listen_port, service_name, config_path, installed_at, updated_at)
- `clients` (id PK autoincrement, protocol, external_name, status, created_at, revoked_at, UNIQUE(protocol, external_name))
- `client_credentials` (id PK, client_id FK→clients, protocol, uuid, created_at)
- `traffic_snapshots` (id PK, protocol, client_id FK nullable, rx_bytes, tx_bytes, collected_at)
- `audit_events` (id PK, actor_telegram_user_id, action, target_type, target_id, status, details_redacted, created_at)

Индексы: `clients(protocol, status)`, `traffic_snapshots(client_id, collected_at)`, `audit_events(actor_telegram_user_id, created_at)`

- `apply_schema(conn)` — создаёт таблицы если не существуют

**`repositories.py`** — классы:
- `AdminRepository`: upsert_admin, is_admin, list_admins
- `ProtocolRepository`: upsert_installation, get_installation
- `ClientRepository`: create_client, get_client, get_credential, list_clients, revoke_client, get_client_by_name
- `AuditRepository`: log

Все методы принимают `aiosqlite.Connection` через `__init__`.

### Связи
- `schema.py` — Phase 2 добавляет миграции (ALTER TABLE или новые таблицы), но не переписывает DDL
- `repositories.py` — Phase 2 добавляет `TrafficRepository`, Phase 3 не меняет
- `AdminRepository.is_admin()` используется в Telegram middleware

### Проверка
```bash
python -c "
import asyncio
from src.database.schema import SCHEMA_SQL
assert 'CREATE TABLE IF NOT EXISTS admins' in SCHEMA_SQL
assert 'CREATE TABLE IF NOT EXISTS clients' in SCHEMA_SQL
assert 'CREATE TABLE IF NOT EXISTS traffic_snapshots' in SCHEMA_SQL
print('OK')
"
```

---

## Step 5: Shell Runner

### Цель
Единый безопасный адаптер для shell-команд.

### Файлы
- `src/infrastructure/__init__.py`
- `src/infrastructure/shell_runner.py`

### Контракт

- `run_command(cmd: list[str], *, timeout: float = 30.0, check: bool = False, cwd: str | None = None) -> ShellResult`
- `ShellResult`: returncode, stdout, stderr, success
- Secrets redaction: строки содержащие `token`, `secret`, `password`, `key`, `uuid` заменяются на `[REDACTED]` в логах
- Timeout: обязательный, по умолчанию 30s
- Никогда не использовать `shell=True`

### Связи
- используется всеми protocol adapters
- Phase 2/3 не меняют этот файл

### Проверка
```bash
python -c "
import asyncio
from src.infrastructure.shell_runner import run_command
result = asyncio.run(run_command(['echo', 'hello']))
assert result.success
assert result.stdout == 'hello'
print('OK')
"
```

---

## Step 6: Protocol Adapter — базовый интерфейс

### Цель
Абстрактный интерфейс, который реализует каждый протокол.

### Файлы
- `src/infrastructure/protocols/__init__.py`
- `src/infrastructure/protocols/base.py`

### Контракт

Абстрактный класс `ProtocolAdapter`:
- `detect() -> ProtocolStatus`
- `install(listen_port: int, public_host: str) -> InstallResult`
- `create_client(external_name: str) -> tuple[str, str]` — возвращает (credential, label)
- `delete_client(identifier: str) -> None`
- `reload_service() -> bool`
- `health() -> HealthResult`
- `backup_config() -> str | None`

Dataclasses:
- `InstallResult`: success, service_name, listen_port, config_path, error
- `HealthResult`: healthy, status, message

### Связи
- `VlessAdapter`, `Hysteria2Adapter`, `MtprotoAdapter` реализуют этот интерфейс
- Phase 2/3 могут добавить методы, но не сломать существующие
- `ProtocolRegistry` работает только через этот интерфейс

### Проверка
```bash
python -c "
from src.infrastructure.protocols.base import ProtocolAdapter, InstallResult, HealthResult
import inspect
assert inspect.isabstract(ProtocolAdapter)
print('OK')
"
```

---

## Step 7: VLESS Adapter

### Цель
Полная реализация управления VLESS/Xray-core.

### Файлы
- `src/infrastructure/protocols/vless/__init__.py`
- `src/infrastructure/protocols/vless/adapter.py`
- `src/infrastructure/protocols/vless/config_writer.py`
- `src/infrastructure/protocols/vless/link_generator.py`

### Контракты

**`config_writer.py`**:
- `create_initial_config(config_path: Path, listen_port: int) -> None`
- `load_config(config_path: Path) -> dict`
- `save_config(config_path: Path, config: dict) -> None`
- `add_client_to_config(config: dict, uuid: str, email: str) -> dict`
- `remove_client_from_config(config: dict, email: str) -> dict`
- `get_clients_from_config(config: dict) -> list[dict]`
- `get_listen_port_from_config(config: dict) -> int`

Все мутации конфига in-memory → потом save.

**`link_generator.py`**:
- `generate_vless_link(uuid: str, host: str, port: int, *, remark: str, network: str, security: str) -> str`
- Формат: `vless://{uuid}@{host}:{port}?{query}#{remark}`

**`adapter.py`** — `VlessAdapter(ProtocolAdapter)`:
- конструктор принимает: `config_path`, `backups_dir`, `public_host`
- `detect()` — проверяет наличие конфига и `systemctl is-active xray`
- `install()` — проверяет порт, устанавливает Xray если нет, создаёт конфиг, запускает сервис
- `create_client()` — генерирует UUID, добавляет в конфиг, reload
- `delete_client()` — удаляет из конфига по email, reload
- `health()` — `systemctl is-active xray`
- `backup_config()` — копирует конфиг в backups_dir с timestamp
- `generate_link()` — отдельный public метод (не часть ProtocolAdapter), использует link_generator

### Связи
- `config_writer` работает с JSON Xray конфигом — Phase 2 использует тот же паттерн для YAML
- `link_generator` — чистая функция, легко тестируется
- `adapter` использует `shell_runner`
- Phase 2 добавляет аналогичные adapters для Hysteria2 и MTProto

### Проверка
```bash
python -c "
from src.infrastructure.protocols.vless.config_writer import (
    add_client_to_config, remove_client_from_config,
    get_clients_from_config, get_listen_port_from_config
)
config = {'inbounds': [{'port': 443, 'settings': {'clients': []}}]}
config = add_client_to_config(config, 'test-uuid', 'user1')
assert len(get_clients_from_config(config)) == 1
config = remove_client_from_config(config, 'user1')
assert len(get_clients_from_config(config)) == 0
print('OK')
"
```

```bash
python -c "
from src.infrastructure.protocols.vless.link_generator import generate_vless_link
link = generate_vless_link('uuid-123', '1.2.3.4', 443, remark='Test')
assert link.startswith('vless://uuid-123@1.2.3.4:443')
print('OK')
"
```

---

## Step 8: Secret Store

### Цель
Хранение секретов с optional шифрованием.

### Файлы
- `src/infrastructure/secret_store.py`

### Контракт

- `SecretStore(store_path: Path, encryption_key: str)`
- `get(key: str) -> str | None`
- `set(key: str, value: str) -> None`
- `delete(key: str) -> None`
- При пустом `encryption_key` — работает без шифрования (dev mode)
- При наличии `encryption_key` — Fernet encryption

### Связи
- используется для хранения credential material
- Phase 2 использует тот же store для Hysteria2/MTProto secrets

### Проверка
```bash
python -c "
from src.infrastructure.secret_store import SecretStore
from pathlib import Path
import tempfile, os
with tempfile.TemporaryDirectory() as d:
    s = SecretStore(Path(d) / 'secrets.json', '')
    s.set('test', 'value123')
    assert s.get('test') == 'value123'
print('OK')
"
```

---

## Step 9: Telegram Interface

### Цель
Базовый бот с admin-only доступом и текстовым меню.

### Файлы
- `src/interface/__init__.py`
- `src/interface/telegram/__init__.py`
- `src/interface/telegram/bot.py`
- `src/interface/telegram/middleware.py`
- `src/interface/telegram/commands.py`
- `src/interface/telegram/keyboards.py`

### Контракты

**`middleware.py`** — `AuthMiddleware`:
- проверяет `telegram_user_id` через `AdminRepository.is_admin()`
- блокирует неавторизованных без деталей
- работает и для Message, и для CallbackQuery

**`commands.py`** — router с обработчиками:
- `/start` — upsert admin + show menu
- `/menu` — show menu
- `/status` — placeholder (Phase 2 расширит)
- `/help` — help text

**`keyboards.py`**:
- `main_menu_keyboard()` → ReplyKeyboardMarkup с кнопками: Status, Install VLESS, Clients, Add Client, Help

**`bot.py`** — `create_bot(config: AppConfig)`:
- инициализирует DB connection + schema
- создаёт Bot + Dispatcher
- регистрирует middleware
- регистрирует routers
- запускает polling

### Связи
- `middleware.py` — Phase 2 добавляет `RateLimitMiddleware`, Phase 3 расширяет
- `commands.py` — Phase 2 добавляет callback handlers
- `keyboards.py` — Phase 2 добавляет inline keyboards
- `bot.py` — Phase 2/3 добавляют routers и services

### Проверка
```bash
python -c "
from src.interface.telegram.middleware import AuthMiddleware
from src.interface.telegram.commands import router
from src.interface.telegram.keyboards import main_menu_keyboard
kb = main_menu_keyboard()
assert kb is not None
print('OK')
"
```

---

## Step 10: Main Entry Point

### Цель
Точка входа `python -m src.main`.

### Файлы
- `src/main.py`

### Контракт
- настраивает logging (basicConfig)
- загружает `AppConfig.from_env()`
- вызывает `run_bot(config)`

### Связи
- Phase 3 заменяет basicConfig на structured JSON logging

### Проверка
```bash
python -m py_compile src/main.py
```

---

## Step 11: Tests

### Цель
Покрыть чистые функции и доменные типы.

### Файлы
- `tests/__init__.py`
- `tests/conftest.py`
- `tests/test_domain.py`
- `tests/test_vless_link_generator.py`
- `tests/test_config_writer.py`

### Контракты тестов

**`test_domain.py`** — проверяет:
- все ProtocolType значения
- все ProtocolStatus значения

**`test_vless_link_generator.py`** — проверяет:
- формат ссылки
- наличие host, port, uuid в ссылке
- remark в fragment

**`test_config_writer.py`** — проверяет:
- создание/загрузка конфига
- добавление клиента
- удаление клиента
- получение списка клиентов
- получение порта

### Проверка
```bash
python -m pytest tests/ -v
```
Все тесты должны быть зелёные.

---

## Step 12: Install Script

### Цель
Одна команда для развёртывания бота на VPS.

### Файлы
- `scripts/install.sh`

### Контракт скрипта
1. Проверяет root
2. Создаёт директории: `/opt/vpnbot/data`, `/opt/vpnbot/backups`, `/var/log/vpnbot`
3. Создаёт системного пользователя `vpnbot`
4. Устанавливает Python 3
5. Копирует приложение в `/opt/vpnbot/app`
6. Создаёт venv и устанавливает зависимости
7. Создаёт systemd unit `vpnbot.service`
8. Включает автозапуск
9. НЕ создаёт `.env` автоматически (только копирует `.env.example`)

### Связи
- Phase 3 расширяет этот скрипт (log rotation, firewall)

### Проверка
```bash
bash -n scripts/install.sh
```

---

## Глобальная проверка Phase 1

После выполнения всех шагов:

```bash
# 1. Зависимости установлены
pip install -e ".[dev]"

# 2. Все модули импортируются
python -c "from src.config import AppConfig"
python -c "from src.domain.enums import ProtocolType"
python -c "from src.domain.models import ProtocolInstallation"
python -c "from src.database.schema import SCHEMA_SQL"
python -c "from src.infrastructure.shell_runner import run_command"
python -c "from src.infrastructure.protocols.base import ProtocolAdapter"
python -c "from src.infrastructure.protocols.vless.adapter import VlessAdapter"
python -c "from src.infrastructure.secret_store import SecretStore"
python -c "from src.interface.telegram.bot import create_bot"

# 3. Тесты зелёные
python -m pytest tests/ -v

# 4. Скрипт валиден
bash -n scripts/install.sh
```

---

## Что Phase 1 НЕ делает (но подготавливает)

- не добавляет Hysteria2/MTProto — но `ProtocolType` уже содержит их значения
- не добавляет inline keyboard — но `AuthMiddleware` готов к CallbackQuery
- не добавляет traffic collection — но таблица `traffic_snapshots` уже есть
- не добавляет backup scheduler — но `VlessAdapter.backup_config()` работает
- не добавляет rate limiting — но middleware layer готов к расширению
