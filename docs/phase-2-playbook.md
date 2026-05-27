# Phase 2 — Execution Playbook

Пошаговая инструкция для AI-агента. Код не дан — агент выбирает реализацию самостоятельно. Контракты, связи и проверки заданы жёстко.

**Предусловие:** Phase 1 полностью завершена. Все проверки из `phase-1-playbook.md` проходят.**

**Перед началом прочитай `docs/00-overview-and-architecture.md` и `docs/phase-2-expansion.md`.**

---

## Принцип целостности

Phase 2 **расширяет** фундамент Phase 1, не переписывает его.

Конкретно:
- `ProtocolAdapter` из Phase 1 — неизменный интерфейс, все новые протоколы реализуют его
- `AppConfig` — добавляет новые поля, не меняет существующие
- `schema.py` — добавляет новые таблицы/миграции, не трогает существующие DDL
- Telegram middleware — добавляется новый слой (RateLimitMiddleware), AuthMiddleware не трогается
- Reply keyboard из Phase 1 дополняется inline keyboard, не заменяется
- `VlessAdapter` из Phase 1 не переписывается

**Если шаг требует выбора — выбирай вариант, который не ломает Phase 1 и проще расширить в Phase 3.**

---

## Step 1: Зависимости

### Цель
Добавить httpx и PyYAML.

### Действие
В `pyproject.toml` добавить в dependencies:
- `httpx>=0.25.0`
- `pyyaml>=6.0`

### Связи
- httpx используется в `Hysteria2Adapter` для Traffic Stats API
- PyYAML используется в `Hysteria2Adapter` для config writer

### Проверка
```bash
pip install -e ".[dev]"
python -c "import httpx; import yaml"
```

---

## Step 2: Capability Model

### Цель
Декларативная модель возможностей каждого протокола. UI показывает только доступные действия.

### Файлы
- `src/domain/capability.py`

### Контракт

`ProtocolCapabilities` — frozen dataclass:
- `supports_individual_clients: bool`
- `supports_client_link_generation: bool`
- `supports_per_client_traffic: bool`
- `supports_aggregate_traffic: bool`
- `supports_hot_reload: bool`
- `supports_backup_restore: bool`
- `supports_port_change: bool`

`CAPABILITY_MATRIX: dict[ProtocolType, ProtocolCapabilities]` — фиксированная таблица:
- VLESS: все True
- Hysteria2: `supports_individual_clients = True`, `supports_per_client_traffic = True`
- MTProto: `supports_individual_clients = False`, `supports_per_client_traffic = False`, `supports_aggregate_traffic = True`

`get_capabilities(protocol: ProtocolType) -> ProtocolCapabilities`

### Связи
- используется в Telegram UI для скрытия недоступных кнопок
- используется в `ProtocolRegistry`
- Phase 3 не меняет этот файл

### Проверка
```bash
python -c "
from src.domain.capability import get_capabilities
from src.domain.enums import ProtocolType
caps = get_capabilities(ProtocolType.MTPROTO)
assert caps.supports_individual_clients is False
assert caps.supports_per_client_traffic is False
assert caps.supports_aggregate_traffic is True
caps = get_capabilities(ProtocolType.VLESS)
assert caps.supports_individual_clients is True
print('OK')
"
```

---

## Step 3: HTTP Client

### Цель
Единый async HTTP клиент для внешних API.

### Файлы
- `src/infrastructure/http_client.py`

### Контракт

- `http_get_json(url, *, params=None, headers=None, timeout=10.0) -> dict | None`
- Возвращает `None` при любой ошибке (не бросает исключения)
- Логирует ошибки через `logger`

### Связи
- используется в `Hysteria2Adapter.collect_traffic()`
- может использоваться в будущем для других внешних API

### Проверка
```bash
python -c "
from src.infrastructure.http_client import http_get_json
import asyncio
# Не должно падать даже при недоступном URL
result = asyncio.run(http_get_json('http://localhost:1/nonexistent'))
assert result is None
print('OK')
"
```

---

## Step 4: Hysteria2 — config writer

### Цель
Чтение/запись YAML конфига Hysteria2.

### Файлы
- `src/infrastructure/protocols/hysteria2/__init__.py`
- `src/infrastructure/protocols/hysteria2/config_writer.py`

### Контракт

- `create_server_config(config_path, listen_port, cert_path, key_path, auth_password, stats_listen, stats_secret) -> None`
- `load_config(config_path) -> dict`
- `save_config(config_path, config) -> None`
- `get_listen_port(config) -> int`
- `get_auth_password(config) -> str`
- `update_auth_password(config, new_password) -> dict`
- `get_stats_endpoint(config) -> str | None`
- `get_stats_secret(config) -> str`

Паттерн аналогичен VLESS `config_writer.py`: load → mutate in-memory → save.

### Связи
- используется `Hysteria2Adapter`
- паттерн идентичен `src/infrastructure/protocols/vless/config_writer.py`

### Проверка
```bash
python -c "
from src.infrastructure.protocols.hysteria2.config_writer import get_listen_port
config = {'listen': ':8443', 'auth': {'type': 'password', 'password': 'test'}}
assert get_listen_port(config) == 8443
print('OK')
"
```

---

## Step 5: Hysteria2 — link generator

### Цель
Генерация клиентских URI и YAML конфигов.

### Файлы
- `src/infrastructure/protocols/hysteria2/link_generator.py`

### Контракт

- `generate_hysteria2_uri(host, port, password, *, remark, insecure) -> str`
  - Формат: `hysteria2://{password}@{host}:{port}?{params}#{remark}`
- `generate_hysteria2_client_config_text(host, port, password, *, insecure) -> str`
  - Возвращает YAML текст клиентского конфига

### Связи
- используется в `Hysteria2Adapter.generate_link()`
- паттерн аналогичен `vless/link_generator.py`

### Проверка
```bash
python -c "
from src.infrastructure.protocols.hysteria2.link_generator import generate_hysteria2_uri
uri = generate_hysteria2_uri('1.2.3.4', 443, 'pass123', remark='Test')
assert uri.startswith('hysteria2://')
assert '1.2.3.4:443' in uri
print('OK')
"
```

---

## Step 6: Hysteria2 — adapter

### Цель
Полная реализация управления Hysteria2, реализующая `ProtocolAdapter`.

### Файлы
- `src/infrastructure/protocols/hysteria2/adapter.py`

### Контракт

`Hysteria2Adapter(ProtocolAdapter)`:
- конструктор: `config_path`, `backups_dir`, `public_host`
- `detect()` — проверяет конфиг + `systemctl is-active hysteria`
- `install()` — устанавливает Hysteria2 если нет, создаёт конфиг с auth_password, stats endpoint, запускает сервис
- `create_client()` — возвращает (password, label). Если per-user auth не поддерживается выбранной версией — работает в shared mode
- `delete_client()` — no-op в shared mode
- `health()` — systemctl check
- `backup_config()` — копия YAML в backups_dir
- `generate_link()` — отдельный public метод через link_generator
- `collect_traffic()` — опрашивает Traffic Stats API через http_client, возвращает dict[user, {rx, tx}]

### Связи
- реализует `ProtocolAdapter` из Phase 1
- использует `shell_runner` из Phase 1
- использует `http_client` из Step 3
- регистрируется в `ProtocolRegistry` из Step 9

### Проверка
```bash
python -c "
from src.infrastructure.protocols.hysteria2.adapter import Hysteria2Adapter
from src.infrastructure.protocols.base import ProtocolAdapter
import inspect
assert issubclass(Hysteria2Adapter, ProtocolAdapter)
print('OK')
"
```

---

## Step 7: MTProto — link generator

### Цель
Генерация Telegram share proxy links.

### Файлы
- `src/infrastructure/protocols/mtproto/__init__.py`
- `src/infrastructure/protocols/mtproto/link_generator.py`

### Контракт

- `generate_mtproto_link(host, port, secret) -> str`
  - Формат: `https://t.me/proxy?server={host}&port={port}&secret={secret}`
- `generate_mtproto_tg_link(host, port, secret) -> str`
  - Формат: `tg://proxy?server={host}&port={port}&secret={secret}`

### Связи
- используется в `MtprotoAdapter.generate_link()`

### Проверка
```bash
python -c "
from src.infrastructure.protocols.mtproto.link_generator import generate_mtproto_link
link = generate_mtproto_link('proxy.com', 443, 'abc123')
assert 't.me/proxy?' in link
assert 'server=proxy.com' in link
assert 'port=443' in link
print('OK')
"
```

---

## Step 8: MTProto — adapter

### Цель
Реализация управления MTProto Proxy. Особенность: endpoint-oriented, не client-oriented.

### Файлы
- `src/infrastructure/protocols/mtproto/adapter.py`

### Контракт

`MtprotoAdapter(ProtocolAdapter)`:
- конструктор: `config_dir`, `backups_dir`, `public_host`
- `detect()` — systemctl check
- `install()` — запускает official installer script с параметрами port/secret/tag
- `create_client()` — **не создаёт отдельного клиента** (capability: `supports_individual_clients = False`), возвращает (secret, label) для share link
- `delete_client()` — no-op
- `health()` — systemctl check
- `backup_config()` — копия config dir в backups_dir
- `generate_link()` — отдельный public метод через link_generator

### Связи
- реализует `ProtocolAdapter` из Phase 1
- использует `shell_runner` из Phase 1
- UI **не показывает** "Clients" кнопку для MTProto (capability check)
- Phase 3 может добавить `rotate_secret()` как отдельный метод

### Проверка
```bash
python -c "
from src.infrastructure.protocols.mtproto.adapter import MtprotoAdapter
from src.infrastructure.protocols.base import ProtocolAdapter
assert issubclass(MtprotoAdapter, ProtocolAdapter)
print('OK')
"
```

---

## Step 9: Protocol Registry

### Цель
Единая точка доступа ко всем протоколам.

### Файлы
- `src/services/__init__.py`
- `src/services/protocol_registry.py`

### Контракт

`ProtocolRegistry`:
- `register(protocol: ProtocolType, adapter: ProtocolAdapter)`
- `get(protocol: ProtocolType) -> ProtocolAdapter`
- `list_registered() -> list[ProtocolType]`
- `get_capabilities(protocol: ProtocolType) -> ProtocolCapabilities`
- `is_registered(protocol: ProtocolType) -> bool`

### Связи
- используется в Telegram handlers для получения нужного adapter
- используется в `TrafficCollector`, `BackupService`
- Phase 3 использует тот же registry

### Проверка
```bash
python -c "
from src.services.protocol_registry import ProtocolRegistry
from src.domain.enums import ProtocolType
r = ProtocolRegistry()
assert not r.is_registered(ProtocolType.VLESS)
print('OK')
"
```

---

## Step 10: Traffic Collector

### Цель
Периодический сбор статистики трафика.

### Файлы
- `src/services/traffic_collector.py`

### Контракт

`TrafficCollector(registry, traffic_repo)`:
- `collect_all() -> None` — опрашивает все зарегистрированные протоколы
- `collect_protocol(protocol) -> None` — опрашивает один протокол

Логика:
- VLESS: через Xray Stats API (реализовать позже или через shell xray api statsquery)
- Hysteria2: через `Hysteria2Adapter.collect_traffic()` → http GET /traffic
- MTProto: aggregate only, через process-level counters (или заглушка)

Сохраняет результат в `TrafficRepository`.

### Связи
- использует `ProtocolRegistry`
- Phase 3 добавляет scheduler для автоматического вызова

### Проверка
```bash
python -c "
from src.services.traffic_collector import TrafficCollector
print('OK')
"
```

---

## Step 11: Traffic Repository

### Цель
Хранение снимков трафика в SQLite.

### Действие
В `src/database/repositories.py` добавить `TrafficRepository`:
- `save_snapshot(protocol, client_name, rx_bytes, tx_bytes) -> None`
- `get_latest_snapshots(protocol, limit=50) -> list[dict]`

### Связи
- используется `TrafficCollector`
- таблица `traffic_snapshots` уже создана в Phase 1

### Проверка
```bash
python -c "
from src.database.repositories import TrafficRepository
print('OK')
"
```

---

## Step 12: Backup Service

### Цель
Бэкап всех конфигов и БД.

### Файлы
- `src/services/backup_service.py`

### Контракт

`BackupService(registry, backups_dir, db_path)`:
- `backup_all() -> list[str]` — возвращает список путей к артефактам

Действия:
1. копирует SQLite DB
2. вызывает `adapter.backup_config()` для каждого протокола

### Связи
- использует `ProtocolRegistry`
- Phase 3 добавляет scheduler и алертинг на failure

### Проверка
```bash
python -c "
from src.services.backup_service import BackupService
print('OK')
"
```

---

## Step 13: Telegram — inline keyboard и callback routing

### Цель
Заменить текстовое меню на inline keyboard с capability-based навигацией.

### Файлы
- `src/interface/telegram/callback_router.py` (новый)
- `src/interface/telegram/screens/__init__.py` (новый)
- `src/interface/telegram/screens/main_menu.py` (новый)
- `src/interface/telegram/screens/protocol_screen.py` (новый)
- `src/interface/telegram/screens/clients_screen.py` (новый)
- `src/interface/telegram/screens/traffic_screen.py` (новый)
- `src/interface/telegram/keyboards.py` (расширяется)

### Контракты

**`callback_router.py`** — router с handlers:
- `menu:main` → show main menu
- `protocol:{name}` → show protocol screen (с capability check)
- `clients:{name}` → show clients screen (только если `supports_individual_clients`)
- `traffic:{name}` → show traffic screen
- `getlink:{name}` → generate and send link
- `confirm:{action}:{target}` → confirm destructive action

**`screens/main_menu.py`**:
- `show_main_menu(message)` — inline keyboard с тремя протоколами + Status + Backup

**`screens/protocol_screen.py`**:
- `show_protocol_screen(message, protocol, registry)` — показывает кнопки только для доступных capabilities

**`keyboards.py`** — добавить:
- `clients_inline_keyboard(clients)` — inline keyboard со списком клиентов
- `confirm_keyboard(action, target)` — inline keyboard подтверждения

### Связи
- `AuthMiddleware` из Phase 1 работает и для CallbackQuery
- capability model из Step 2 определяет какие кнопки показывать
- reply keyboard из Phase 1 может быть убрана или оставлена как fallback

### Проверка
```bash
python -c "
from src.interface.telegram.callback_router import router
from src.interface.telegram.screens.main_menu import show_main_menu
from src.interface.telegram.screens.protocol_screen import show_protocol_screen
print('OK')
"
```

---

## Step 14: Обновление bot.py

### Цель
Интегрировать все новые компоненты в бота.

### Действие
В `src/interface/telegram/bot.py`:
- импортировать и зарегистрировать `callback_router`
- инициализировать `ProtocolRegistry` и зарегистрировать adapters
- передать `registry` через dispatcher data (`dp["registry"]`)
- инициализировать `TrafficCollector` и `BackupService`

### Связи
- Phase 3 добавит scheduler, alerting и auto-update через тот же bot.py

### Проверка
```bash
python -m py_compile src/interface/telegram/bot.py
```

---

## Step 15: Tests

### Цель
Покрыть новые компоненты.

### Файлы
- `tests/test_hysteria2_config_writer.py`
- `tests/test_hysteria2_link_generator.py`
- `tests/test_mtproto_link_generator.py`
- `tests/test_capability.py`

### Контракты тестов

**`test_hysteria2_config_writer.py`**:
- создание и загрузка конфига
- получение порта
- получение auth password
- получение stats endpoint

**`test_hysteria2_link_generator.py`**:
- формат URI
- наличие host, port, password
- insecure flag

**`test_mtproto_link_generator.py`**:
- формат `https://t.me/proxy?...`
- наличие server, port, secret

**`test_capability.py`**:
- VLESS capabilities all True
- MTProto individual_clients = False
- Hysteria2 all True

### Проверка
```bash
python -m pytest tests/ -v
```
Все тесты должны быть зелёные. Включая тесты из Phase 1.

---

## Глобальная проверка Phase 2

```bash
# 1. Зависимости
pip install -e ".[dev]"

# 2. Все новые модули импортируются
python -c "from src.domain.capability import get_capabilities, CAPABILITY_MATRIX"
python -c "from src.infrastructure.http_client import http_get_json"
python -c "from src.infrastructure.protocols.hysteria2.adapter import Hysteria2Adapter"
python -c "from src.infrastructure.protocols.mtproto.adapter import MtprotoAdapter"
python -c "from src.services.protocol_registry import ProtocolRegistry"
python -c "from src.services.traffic_collector import TrafficCollector"
python -c "from src.services.backup_service import BackupService"
python -c "from src.interface.telegram.callback_router import router"

# 3. Все тесты (Phase 1 + Phase 2) зелёные
python -m pytest tests/ -v

# 4. Phase 1 модули всё ещё работают
python -c "from src.infrastructure.protocols.vless.adapter import VlessAdapter"
python -c "from src.database.schema import SCHEMA_SQL"
python -c "from src.interface.telegram.middleware import AuthMiddleware"
```

---

## Что Phase 2 НЕ делает (но подготавливает)

- не добавляет rate limiting — но capability model и callback routing готовы
- не добавляет structured logging — но traffic collector логирует через stdlib logger
- не добавляет auto-update — но registry и services layer готовы
- не добавляет CI/CD — но тесты покрывают все adapters
- не добавляет alerting — но health check infrastructure есть

---

## Связи между фазами — проверка

Убедись, что:
1. Phase 1 тесты всё ещё зелёные
2. `ProtocolAdapter` интерфейс не изменился
3. `schema.py` DDL не переписан (только дополнен)
4. `AuthMiddleware` не переписан
5. `AppConfig` только добавил поля
6. `VlessAdapter` не переписан
