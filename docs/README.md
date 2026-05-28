# VPNBot

Telegram-бот для управления VPN-сервером на VPS. Установка, управление клиентами, генерация ссылок, мониторинг трафика — всё через Telegram без CLI.

---

## Для AI-агента: инструкция по разработке

Ты в режиме build. Твоя задача — разработать продукт под ключ, следуя документации в `docs/`.

Текущая целевая концепция пересмотрена: проект больше не является просто ботом
с набором заглушек протоколов. Основа продукта — one-command VPS installer,
установка ядер/сервисов/SSL на сервер и Telegram-бот как замена web-панели.
Главный документ для новой разработки: `docs/01-product-rebuild-plan.md`.

### Правила

Перед началом работы прочитай:
- `AGENTS.md` в корне проекта — обязательные правила качества, безопасности, стиля
- `G:\Dev\AGENTS.md` — глобальные правила (если отличаются, проектные имеют приоритет)

### Как работать

1. **Читай документы по порядку.** Не пропускай.
2. **Следуй playbook шаг за шагом.** Не делай два шага одновременно.
3. **После каждого шага — проверяй.** Команды проверки даны в playbook.
4. **После завершения шага — отчитайся.** Формат: `✅ Step N завершён: [что сделано]`
5. **После завершения фазы — прогони глобальную проверку.** Она в конце каждого playbook.
6. **Если что-то не проходит проверку — исправляй, не переходи дальше.**
7. **Если шаг неоднозначен — задай вопрос, не гадай.**

### Порядок чтения документов

```
Rebuild baseline:
  1. docs/01-product-rebuild-plan.md          — новая целевая концепция, фазы, правила агентов
  2. docs/00-overview-and-architecture.md     — архитектура, домен, контракты

Phase 1:
  3. docs/phase-1-mvp.md                     — старое бизнес-описание Phase 1
  4. docs/phase-1-playbook.md                — старые шаги реализации Phase 1

Phase 2:
  5. docs/phase-2-expansion.md               — старое бизнес-описание Phase 2
  6. docs/phase-2-playbook.md                — старые шаги реализации Phase 2

Phase 3:
  7. docs/phase-3-production.md              — старое бизнес-описание Phase 3
  8. docs/phase-3-playbook.md                — старые шаги реализации Phase 3
```

Старые playbook использовать как справочник по текущему коду. Если они
противоречат `docs/01-product-rebuild-plan.md`, приоритет у rebuild plan.

### Формат отчётов

После каждого шага:
```
✅ Step [номер] завершён: [краткое описание]
  Файлы: [список созданных/изменённых файлов]
  Проверка: [результат команды проверки]
```

После завершения фазы:
```
🏁 Phase [номер] завершена: [название]
  Создано файлов: [N]
  Тесты: [все зелёные / есть ошибки]
  Глобальная проверка: [пройдена / не пройдена]
```

---

## Roadmap

### Phase 1 — MVP
**Цель:** рабочий бот с одним протоколом (VLESS).

| Step | Что делаем | Файлы | Проверка |
|------|-----------|-------|----------|
| 1 | Инициализация проекта | pyproject.toml, .gitignore, .env.example | pip install |
| 2 | Config | src/config.py | import |
| 3 | Domain | enums, models, exceptions | import + assertions |
| 4 | Database | connection, schema, repositories | import |
| 5 | Shell Runner | infrastructure/shell_runner.py | run_command test |
| 6 | Protocol Adapter (base) | infrastructure/protocols/base.py | inspect.isabstract |
| 7 | VLESS Adapter | adapter, config_writer, link_generator | unit tests |
| 8 | Secret Store | infrastructure/secret_store.py | get/set test |
| 9 | Telegram Interface | bot, middleware, commands, keyboards | import |
| 10 | Main Entry Point | src/main.py | py_compile |
| 11 | Tests | tests/ | pytest green |
| 12 | Install Script | scripts/install.sh | bash -n |

**DoD Phase 1:**
- [ ] `pip install -e ".[dev]"` проходит
- [ ] `python -m pytest tests/ -v` зелёный
- [ ] Все модули импортируются
- [ ] VLESS link generator работает
- [ ] Config writer работает
- [ ] Install script валиден

---

### Phase 2 — Expansion
**Цель:** три протокола, inline UI, трафик, backup.

| Step | Что делаем | Файлы | Проверка |
|------|-----------|-------|----------|
| 1 | Зависимости | pyproject.toml (httpx, pyyaml) | import |
| 2 | Capability Model | domain/capability.py | assertions |
| 3 | HTTP Client | infrastructure/http_client.py | null on error |
| 4 | Hysteria2 config_writer | protocols/hysteria2/config_writer.py | load/save test |
| 5 | Hysteria2 link_generator | protocols/hysteria2/link_generator.py | URI format |
| 6 | Hysteria2 adapter | protocols/hysteria2/adapter.py | issubclass |
| 7 | MTProto link_generator | protocols/mtproto/link_generator.py | t.me/proxy format |
| 8 | MTProto adapter | protocols/mtproto/adapter.py | issubclass |
| 9 | Protocol Registry | services/protocol_registry.py | register/get |
| 10 | Traffic Collector | services/traffic_collector.py | import |
| 11 | Traffic Repository | database/repositories.py (+) | import |
| 12 | Backup Service | services/backup_service.py | import |
| 13 | Telegram inline UI | callback_router, screens | import |
| 14 | bot.py update | bot.py (расширение) | py_compile |
| 15 | Tests | tests/ (+) | pytest green |

**DoD Phase 2:**
- [ ] Hysteria2 adapter реализует ProtocolAdapter
- [ ] MTProto adapter реализует ProtocolAdapter
- [ ] Capability model скрывает MTProto client management
- [ ] Inline keyboards работают
- [ ] Traffic collector опрашивает протоколы
- [ ] Backup service создаёт артефакты
- [ ] Все тесты (Phase 1 + Phase 2) зелёные
- [ ] Phase 1 модули не сломаны

---

### Phase 3 — Production
**Цель:** безопасность, наблюдаемость, CI/CD, документация.

| Step | Что делаем | Файлы | Проверка |
|------|-----------|-------|----------|
| 1 | Rate Limiter | infrastructure/rate_limiter.py | limit test |
| 2 | Structured Logging | main.py (обновление) | py_compile |
| 3 | Audit Logger | domain/audit.py | import |
| 4 | Alerting | infrastructure/alerting.py | send test |
| 5 | Middleware Extensions | middleware.py (+) | import |
| 6 | Health Checker | services/health_checker.py | import |
| 7 | Auto-Update | infrastructure/updater.py | import |
| 8 | Config Extensions | config.py (+) | import |
| 9 | Install Script Extensions | scripts/install.sh (+) | bash -n |
| 10 | Update/Restore Scripts | scripts/update.sh, restore.sh | bash -n |
| 11 | Documentation | docs/user-guide.md, operator-runbook.md | files exist |
| 12 | CI Pipeline | .github/workflows/ci.yml | yaml valid |
| 13 | Integration — bot.py | bot.py (расширение) | py_compile |
| 14 | Tests | tests/ (+) | pytest green |

**DoD Phase 3:**
- [ ] Rate limiting работает
- [ ] Structured logging не содержит секретов
- [ ] Audit trail логирует критичные действия
- [ ] Alert dispatcher работает
- [ ] Health checker обнаруживает failures
- [ ] Update/restore scripts работают
- [ ] User guide и operator runbook написаны
- [ ] CI pipeline зелёный
- [ ] ВСЕ тесты (Phase 1 + 2 + 3) зелёные
- [ ] Phase 1 и Phase 2 модули не сломаны

---

## Архитектура (кратко)

```
src/
├── config.py                    — единая точка конфигурации
├── main.py                      — точка входа
├── domain/                      — типы, enums, exceptions, capability
├── database/                    — SQLite schema, repositories
├── infrastructure/              — shell, http, secrets, protocol adapters
│   └── protocols/
│       ├── base.py              — ProtocolAdapter (интерфейс)
│       ├── vless/               — Xray-core adapter
│       ├── hysteria2/           — Hysteria2 adapter
│       └── mtproto/             — MTProto Proxy adapter
├── services/                    — registry, traffic, backup, health
└── interface/
    └── telegram/                — bot, middleware, commands, screens
```

### Ключевые контракты (не менять между фазами)

| Контракт | Файл | Почему не менять |
|----------|------|-----------------|
| `ProtocolAdapter` | infrastructure/protocols/base.py | Все протоколы реализуют его |
| `ProtocolType` | domain/enums.py | Используется везде |
| `AppConfig` | config.py | Только добавлять поля |
| `schema.py DDL` | database/schema.py | Только дополнять |
| `AuthMiddleware` | interface/telegram/middleware.py | Phase 3 добавляет слой, не переписывает |

---

## Стек

| Компонент | Технология |
|-----------|-----------|
| Язык | Python 3.11+ |
| Telegram | aiogram 3.x |
| БД | SQLite (aiosqlite) |
| Валидация | pydantic |
| Шифрование | cryptography |
| HTTP клиент | httpx |
| YAML | PyYAML |
| Тесты | pytest + pytest-asyncio |

---

## Структура docs/

| Файл | Назначение |
|------|-----------|
| `00-overview-and-architecture.md` | Архитектура, домен, контракты — читать первым |
| `phase-1-mvp.md` | Бизнес-описание Phase 1 |
| `phase-1-playbook.md` | Пошаговая инструкция Phase 1 |
| `phase-2-expansion.md` | Бизнес-описание Phase 2 |
| `phase-2-playbook.md` | Пошаговая инструкция Phase 2 |
| `phase-3-production.md` | Бизнес-описание Phase 3 |
| `phase-3-playbook.md` | Пошаговая инструкция Phase 3 |

---

## Быстрый старт (для разработчика-человека)

```bash
# 1. Клонировать репозиторий
git clone <repo-url>
cd VPNBot

# 2. Установить зависимости
pip install -e ".[dev]"

# 3. Создать .env из шаблона
cp .env.example .env
# Редактировать .env — указать BOT_TOKEN, ADMIN_IDS

# 4. Запустить тесты
python -m pytest tests/ -v

# 5. Запустить бота
python -m src.main
```

---

## Установка на VPS

```bash
# На VPS от root:
bash scripts/install.sh

# Настроить:
nano /opt/vpnbot/.env

# Запустить:
systemctl start vpnbot
```
