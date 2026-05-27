# Техническое задание: Telegram-бот для управления VPN-сервером

## 1. Цель документа

Этот документ задаёт архитектурную рамку, продуктовые ограничения, технические контракты и принципы реализации Telegram-бота, который устанавливается на VPS и становится единой оболочкой управления VPN-сервисами на этом же сервере.

Документ самодостаточен и должен быть понятен разработчику без дополнительного устного контекста.

## 2. Продуктовая цель

После первичной установки на VPS пользователь больше не работает с CLI. Все основные действия выполняются через Telegram-бота:
- установка VPN-протоколов на тот же VPS;
- создание и удаление клиентов;
- получение клиентских ссылок/конфигов;
- просмотр трафика по клиентам;
- базовое администрирование установленных протоколов.

## 3. Границы системы

### Бот является
- Telegram-интерфейсом управления VPS-установкой;
- оркестратором установки протоколов;
- панелью управления клиентами;
- генератором ссылок и клиентских конфигов;
- точкой просмотра статистики трафика.

### Бот не является
- VPN-клиентом;
- внешней SaaS-панелью;
- multi-tenant платформой;
- заменой systemd, firewall или пакетному менеджеру ОС;
- универсальным серверным хостинг-менеджером.

## 4. High-level требования

1. Один установочный сценарий разворачивает бота на VPS.
2. После установки бот доступен в Telegram и может управлять локальными сервисами на этом же хосте.
3. Каждый протокол устанавливается и управляется независимо.
4. Пользователь может вручную указать порт для каждого протокола или принять рекомендованный.
5. Все критичные операции должны быть идемпотентными или безопасно повторяемыми.
6. Все действия бота должны быть ограничены доверенными администраторами.
7. Секреты и клиентские ключи не должны попадать в логи.
8. Архитектура должна поддерживать MVP-first развитие: сначала один протокол, затем расширение.

## 5. Рекомендуемый стек MVP

Цель — минимум зависимостей и предсказуемое управление systemd/файлами на Linux VPS.

### Рекомендуемый стек
- Язык: Python 3.11+
- Telegram integration: прямой HTTP-клиент к Telegram Bot API или минимальная стабильная библиотека
- Хранилище состояния: SQLite
- Управление сервисами: systemd
- Конфиги протоколов: JSON/YAML/нативные конфиги на файловой системе
- Планировщик фоновых задач: встроенный asyncio scheduler / отдельный worker без внешнего брокера
- Логи: JSON lines или structured text в journald + локальный файл

### Почему так
- Python достаточно прост для автоматизации VPS и системных вызовов.
- SQLite подходит для single-node сценария.
- systemd — стандартный и надёжный способ управления сервисами на VPS.
- Отказ от веб-панели и внешней БД уменьшает операционную сложность.

## 6. Архитектурная модель

Рекомендуемая структура проекта:

- `domain/` — сущности и правила предметной области
- `services/` — use-cases и orchestration
- `infrastructure/` — Telegram API, systemd, файловая система, shell runner, firewall, backup
- `interface/telegram/` — handlers, меню, callback routing
- `storage/` — SQLite schema, repositories, migrations
- `scripts/` — bootstrap/install scripts
- `docs/` — ТЗ, runbooks, user docs

### Архитектурные принципы
- Бизнес-логика не зависит от Telegram SDK.
- Управление каждым протоколом идёт через отдельный adapter/service.
- Все shell-команды проходят через единый безопасный runner.
- Редактирование конфигов выполняется через in-memory model → атомарная запись → валидация → reload.
- Для каждого протокола есть единый контракт управления.

## 7. Основные сущности домена

### ServerNode
Представляет текущий VPS.
- `id`
- `hostname`
- `public_ip`
- `os_family`
- `created_at`

### AdminAccount
Разрешённый администратор бота.
- `telegram_user_id`
- `telegram_chat_id`
- `role`
- `is_active`
- `created_at`
- `last_seen_at`

### ProtocolInstallation
Факт установки и текущее состояние протокола.
- `protocol` ∈ `vless | hysteria2 | mtproto`
- `status` ∈ `not_installed | installing | active | degraded | failed | disabled`
- `listen_host`
- `listen_port`
- `service_name`
- `config_path`
- `version`
- `installed_at`
- `updated_at`

### ClientAccount
Клиент протокола.
- `id`
- `protocol`
- `external_name`
- `system_name`
- `credential_ref`
- `is_active`
- `created_at`
- `revoked_at`

### ClientCredential
Секреты/идентификаторы клиента.
- `id`
- `protocol`
- `secret_type`
- `secret_value_encrypted`
- `metadata_json`

### TrafficSnapshot
Агрегированная статистика трафика.
- `id`
- `protocol`
- `client_id`
- `rx_bytes`
- `tx_bytes`
- `collected_at`
- `source`

### AuditEvent
Аудит действий администратора.
- `id`
- `actor_telegram_user_id`
- `action`
- `target_type`
- `target_id`
- `status`
- `details_json_redacted`
- `created_at`

## 8. Контракты между слоями

## 8.1 Общий контракт ProtocolManager

Каждый протокол реализует единый интерфейс:

- `detect_installation() -> ProtocolInstallationStatus`
- `install(params) -> InstallResult`
- `uninstall(params) -> OperationResult`
- `create_client(params) -> ClientCreateResult`
- `delete_client(client_id) -> OperationResult`
- `list_clients() -> list[ClientSummary]`
- `get_client_access_material(client_id) -> AccessMaterial`
- `collect_traffic() -> list[TrafficSnapshot]`
- `validate_config() -> ValidationResult`
- `reload_service() -> OperationResult`
- `service_health() -> HealthResult`
- `backup_config() -> BackupArtifact`

### Обязательные свойства реализации
- Идемпотентность установки.
- Безопасный rollback при частичном сбое.
- Явная валидация порта, домена, UUID, секретов и имён клиентов.
- Атомарное изменение конфигов.

## 8.2 ShellRunner

Единый адаптер для shell/system операций.

### Обязанности
- запуск команд без shell injection;
- timeout;
- capture stdout/stderr;
- redaction секретов в логах;
- возврат exit code и structured result.

### Запрещено
- прямой `subprocess` из бизнес-логики;
- логирование секретов, токенов, полных ссылок доступа;
- выполнение произвольных команд из Telegram ввода.

## 8.3 ConfigRepository

Отвечает за файловые конфиги.

### Обязанности
- чтение текущего конфига;
- парсинг в typed model;
- изменение модели;
- запись во временный файл;
- backup предыдущей версии;
- atomic replace;
- запуск validate/reload.

## 9. Telegram UX и контракты интерфейса

## 9.1 Способ интеграции с Telegram

Для VPS-бота по умолчанию использовать long polling как более простой и автономный вариант для MVP.
Webhook допускается только в production-фазе при наличии стабильного HTTPS ingress.

Согласно Bot API, бот должен использовать:
- команды `BotCommand` для базовой навигации;
- `ReplyKeyboardMarkup` для MVP-меню;
- `InlineKeyboardMarkup` и `CallbackQuery` для расширенного меню со Phase 2;
- обязательный `answerCallbackQuery` после нажатия inline-кнопок.

## 9.2 Базовые команды
- `/start`
- `/menu`
- `/status`
- `/protocols`
- `/clients`
- `/traffic`
- `/backup`
- `/help`

## 9.3 Принципы UX
- Одна операция = один ясный сценарий с подтверждением результата.
- Ошибки формулируются кратко и прикладно.
- Разрушающие операции требуют подтверждения.
- Бот никогда не показывает секреты повторно без явного запроса.
- Для длинных операций бот отправляет промежуточный статус: `started / in progress / completed / failed`.

## 9.4 Admin-only доступ

Бот должен работать только в white-list режиме.

Обязательные проверки:
- разрешён ли `telegram_user_id`;
- совпадает ли разрешённый режим чата (`private` на MVP);
- не заблокирован ли администратор;
- не превышен ли rate limit.

По умолчанию все команды вне whitelist получают одинаковый отказ без лишних деталей.

## 10. Хранилище данных

Использовать SQLite как source of truth для состояния бота.

### Что хранить в SQLite
- список администраторов;
- установленные протоколы;
- метаданные клиентов;
- путь к конфигам и сервисам;
- снимки трафика;
- журнал аудита;
- задания backup/update.

### Что не хранить в SQLite в открытом виде
- bot token;
- приватные ключи TLS;
- UUID/пароли/секреты без шифрования;
- полные клиентские ссылки в логах.

### Хранение секретов
- env для bootstrap secrets;
- локальный encrypted-at-rest storage для клиентских секретов;
- ключ шифрования либо из env, либо из root-only файла на VPS.

## 11. Протоколы: техническая стратегия

## 11.1 VLESS (Xray-core)

### Рекомендуемый способ установки
- устанавливать Xray-core как отдельный systemd service;
- конфиг хранить в JSON-файле под root-owned директорией;
- управлять через редактирование inbound clients и systemd reload/restart;
- использовать официальный install path/пакет или pinned binary release.

### Рекомендуемая серверная модель
Для MVP использовать один inbound VLESS на одном порту с TLS.
Варианты transport/obfuscation не смешивать в MVP без необходимости.

### Формат конфигурации
Нативный JSON Xray.
Критичные поля:
- `inbounds[].port`
- `inbounds[].protocol = vless`
- `settings.clients[]`
- `clients[].id`
- `clients[].email`
- `decryption = none`
- `streamSettings`
- TLS settings

### Управление клиентами
Каждый клиент добавляется в `settings.clients[]`.
Идентификатор клиента:
- `id` = UUID
- `email` = внутренний label для идентификации и статистики

### Генерация ссылок
Бот генерирует VLESS URL из server endpoint + UUID + transport/tls params.
Формат ссылки должен определяться строго из фактического server config, а не из захардкоженных шаблонов.

### Сбор трафика
Предпочтительный способ — Xray Stats API.
Документация Xray показывает возможность запрашивать user stats через API/CLI (`xray api statsquery`).

Решение:
- включить stats policy и локальный API endpoint только на loopback;
- собирать per-user rx/tx по `email`/user key;
- сохранять снапшоты в SQLite.

### Как бот управляет протоколом
- systemd для lifecycle;
- JSON config files для state;
- Xray CLI/API для validate/stats;
- firewall adapter для открытия порта.

### Рекомендуемый порт
- рекомендованный: `443`
- вручную: любой свободный TCP-порт из разрешённого диапазона

### Основные риски
- некорректный TLS setup;
- несовместимость generated link и server config;
- сложность stats API;
- частичное повреждение JSON при редактировании.

### Митигация
- typed config model;
- pre-flight port check;
- validate before reload;
- backup previous config;
- smoke-check после установки.

## 11.2 Hysteria2

### Рекомендуемый способ установки
- установка через официальный install script или pinned binary;
- запуск как отдельный systemd service;
- YAML config в root-owned директории;
- для production использовать pinned version, а не latest без контроля.

### Формат конфигурации
Нативный YAML Hysteria 2.
Ключевые поля:
- `listen`
- `tls.cert` / `tls.key` или `acme`
- `auth`
- `trafficStats.listen`
- `trafficStats.secret`

### Модель аутентификации
Для MVP допустима password auth, но для полноценного multi-client учёта рекомендуется модель с отдельными учётными данными на пользователя, если целевая версия и выбранный режим это поддерживают.

Если выбранный режим Hysteria2 в конкретной реализации не поддерживает удобное удалённое управление individual users через API, бот должен использовать один из двух режимов:
1. phase-limited support: установка + ротация общего доступа как ограниченный режим;
2. расширенный режим на отдельном user map / auth backend, если подтверждено документацией и протестировано.

Для данного ТЗ в Phase 2 целевым считается per-user управление, но с техническим spike перед реализацией.

### Генерация клиентских конфигов
Бот должен уметь выдавать:
- URI формата `hysteria2://...`, если он однозначно применим;
- и/или YAML client config как файл/текст.

Фактический формат должен зависеть от выбранного auth mode и TLS mode.

### Сбор трафика
Предпочтительный способ — встроенный Traffic Stats API Hysteria 2.
Документация указывает `GET /traffic`, возвращающий JSON map по пользователям, а также настройку `trafficStats.listen` и `trafficStats.secret`.

Решение:
- включать stats API только на loopback или unix-socket-эквивалент, если доступно;
- использовать отдельный секрет;
- бот периодически опрашивает `/traffic` и сохраняет данные в SQLite.

### Как бот управляет протоколом
- systemd для lifecycle;
- YAML config files для state;
- локальный HTTP stats endpoint для статистики;
- shell adapter для install/upgrade;
- firewall adapter для порта.

### Рекомендуемый порт
- рекомендованный: `443/UDP`
- вручную: любой свободный UDP-порт из разрешённого диапазона

### Основные риски
- TLS/ACME автоматизация;
- различия между auth modes и управляемостью клиентов;
- UDP firewall misconfiguration;
- неочевидный UX для client config.

### Митигация
- отдельный discovery spike перед реализацией per-user management;
- поддержка YAML client config как fallback;
- health-check после deploy;
- backup config до любой мутации.

## 11.3 MTProto Proxy

### Рекомендуемый способ установки
Использовать отдельный MTProto proxy service как systemd unit с pinned способом установки.
Предпочтительно брать реализацию, которая:
- стабильно запускается как сервис;
- поддерживает share URL generation;
- допускает конфигурацию порта, secret, tag и transport mode;
- не требует ручного вмешательства после deploy.

Практически приемлемый baseline для Phase 2/3 — `seriyps/mtproto_proxy`, т.к. документация описывает installer и генерацию share URLs.

### Формат конфигурации
Нативный конфиг выбранной реализации (обычно `.config`/erlang terms/env driven config).
В хранилище бота отдельно сохраняются:
- listen port;
- secret;
- tag/advertised dc tag;
- transport modes;
- public hostname/SNI при fake TLS.

### Управление клиентами
Важно: MTProto Proxy по своей природе обычно не предоставляет полноценную модель отдельных конечных клиентов на стороне сервера, как VLESS или Hysteria2.

Следовательно, в рамках ТЗ принимается ограничение:
- MTProto Proxy управляется как server-level access endpoint;
- бот может ротировать secret, включать/выключать endpoint, генерировать новые share links;
- полноценные create/delete/list individual clients для MTProto не являются нативной возможностью протокола и не должны имитироваться ложной моделью.

Это must-have архитектурное ограничение: UI и доменная модель должны допускать, что разные протоколы поддерживают разные capability sets.

### Генерация ссылок
Использовать share links формата `https://t.me/proxy?...` или `tg://proxy?...`, сформированные из host, port, secret и transport mode.
Документация реализации показывает функцию build/share URLs и derivation для fake-TLS вариантов.

### Сбор трафика
Per-user статистика, как у VLESS/Hysteria2, для MTProto чаще всего недоступна.
Поддерживаемый baseline:
- process/service-level health;
- aggregate traffic на уровне proxy/service/interface;
- возможно log-based or exporter-based total counters.

В UI бот должен явно показывать, что для MTProto доступна aggregate статистика, а не per-client.

### Как бот управляет протоколом
- systemd для lifecycle;
- конфиг/installer parameters для service config;
- генерация share links в application layer;
- firewall adapter для TCP-порта.

### Рекомендуемый порт
- рекомендованный: `443`
- вручную: любой свободный TCP-порт, совместимый с выбранным режимом

### Основные риски
- завышенные ожидания по модели клиентов;
- сложность fake-TLS/SNI режима;
- отсутствие per-user stats;
- нестабильность неофициальных реализаций.

### Митигация
- capability-based UI;
- не обещать individual client management для MTProto;
- выбирать реализацию с documented installer и share URL support;
- фиксировать ограничения в пользовательской документации.

## 12. Capability model по протоколам

Система обязана поддерживать разные возможности протоколов через capability matrix.

### Обязательные capability flags
- `supports_individual_clients`
- `supports_client_link_generation`
- `supports_per_client_traffic`
- `supports_aggregate_traffic`
- `supports_hot_reload`
- `supports_backup_restore`
- `supports_port_change`

### Матрица по умолчанию
- VLESS: все `true`, кроме спорных зависящих от реализации
- Hysteria2: `supports_individual_clients = conditional`
- MTProto: `supports_individual_clients = false`, `supports_per_client_traffic = false`, `supports_aggregate_traffic = true`

UI не должен показывать недоступные действия.

## 13. Установка на VPS

## 13.1 Bootstrap сценарий
Один install script должен:
1. Проверить ОС и зависимости.
2. Создать системного пользователя бота.
3. Создать каталоги данных, логов, backup.
4. Установить runtime.
5. Развернуть код бота.
6. Записать env-файл.
7. Инициализировать SQLite.
8. Создать systemd unit бота.
9. Запустить и включить автозапуск.
10. Выполнить post-install smoke-check.

## 13.2 Директории
Рекомендуемый layout:
- `/opt/vpnbot/app`
- `/opt/vpnbot/data`
- `/opt/vpnbot/backups`
- `/opt/vpnbot/runtime`
- `/etc/vpnbot/`
- `/var/log/vpnbot/`

### Правила доступа
- root владеет конфигами протоколов и секретами;
- bot user имеет только необходимый минимум;
- операции, требующие root, выполняются через строго ограниченный механизм (`sudo` allowlist / root-owned helper).

## 14. Безопасность

### Обязательные меры
- whitelist admin IDs;
- private chat only на MVP;
- rate limiting по user/chat/action;
- redact secrets в логах;
- input validation всех портов, UUID, имён, доменов;
- атомарные обновления конфигов;
- root operations только через allowlisted commands;
- локальные stats/API endpoints только на loopback;
- резервные копии конфигов перед мутациями;
- audit trail для административных действий.

### Недопустимо
- shell-команды из пользовательского текста;
- хранение bot token в репозитории;
- отправка полных секретов в системные логи;
- world-readable конфиги с credential material.

## 15. Наблюдаемость

### Логи
Уровни:
- `INFO` — жизненный цикл и бизнес-события без секретов;
- `WARNING` — recoverable issues;
- `ERROR` — ошибки операций;
- `AUDIT` — административные действия.

### Метрики
Минимум:
- bot uptime;
- last poll timestamp;
- protocol service health;
- install/reload success rate;
- backup success/failure;
- traffic collection success/failure.

### Алертинг
На production-фазе:
- бот недоступен;
- сервис протокола down;
- backup failed;
- traffic collector failed N раз подряд.

## 16. Backup/restore

Минимальный состав backup:
- SQLite DB;
- protocol configs;
- metadata/secrets storage;
- env-template без секретов и/или отдельно защищённый секретный архив.

### Требования
- backup создаётся до рискованных изменений и по расписанию;
- restore документирован, но автоматический restore не обязателен для MVP;
- артефакт должен иметь timestamp, protocol tag и checksum.

## 17. Тестовая стратегия

### Unit
- validators;
- link generators;
- config serializers/parsers;
- capability logic;
- menu state machine.

### Integration
- repositories + SQLite;
- protocol adapters на fixture configs;
- shell runner на mock/controlled commands;
- Telegram handler flow.

### System / smoke
- bot boot;
- protocol install;
- create/delete client;
- generate link;
- collect traffic;
- backup config.

## 18. Нефункциональные требования

- Single VPS, single primary admin в MVP, расширяемо до нескольких admin.
- Поддержка Ubuntu LTS как primary target.
- Операции должны завершаться с предсказуемыми timeout.
- Все сервисы поднимаются после reboot.
- Повторная установка не должна разрушать уже развёрнутую систему без подтверждения.

## 19. Технические решения, принятые в ТЗ

1. MVP строится вокруг одного протокола — VLESS.
2. Telegram long polling используется как базовый транспорт управления.
3. SQLite используется как единственный state store для single-node режима.
4. Управление протоколами идёт через protocol adapters + systemd + config files.
5. VLESS и Hysteria2 проектируются как client-oriented protocol managers.
6. MTProto проектируется как endpoint-oriented manager, а не как per-client manager.
7. Capability model обязательна, чтобы не ломать UX ложными обещаниями.

## 20. Связанные документы

- `docs/phase-1-mvp.md`
- `docs/phase-2-expansion.md`
- `docs/phase-3-production.md`
