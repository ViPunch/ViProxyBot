# Phase 2 — Expansion

## 1. Цель фазы

Расширить MVP до полноценной single-server панели управления несколькими VPN-протоколами, добавить мониторинг трафика, улучшить Telegram UX и закрыть основные пробелы по тестированию и backup.

Phase 2 должна превратить MVP из proof-of-concept в практичный эксплуатационный инструмент.

## 2. Scope

## Входит в Phase 2
- добавление `Hysteria2`;
- добавление `MTProto Proxy`;
- capability-based UI для разных протоколов;
- inline-кнопки и вложенное меню;
- per-client traffic monitoring для протоколов, где это доступно;
- aggregate traffic monitoring для MTProto;
- периодический сбор traffic snapshots;
- backup конфигов и SQLite по расписанию и по требованию;
- расширенные integration и system tests;
- улучшенные health checks;
- более чистые контракты protocol adapters.

## Не входит в Phase 2
- production-grade rate limiting и hardening как обязательное условие релиза;
- auto-update бота;
- CI/CD pipeline;
- пользовательская внешняя документация;
- multi-node управление несколькими VPS;
- web UI.

## 3. Ключевые продуктовые результаты

После Phase 2 администратор должен уметь:
- устанавливать любой из трёх протоколов через Telegram;
- управлять доступными клиентами без CLI;
- получать ссылки/конфиги подключения;
- смотреть трафик по клиентам там, где это поддерживается;
- запускать backup конфигов и состояния;
- пользоваться более удобным menu-driven интерфейсом.

## 4. Архитектурные изменения

## 4.1 Capability-based управление

Так как протоколы поддерживают разные модели управления, интерфейс и service layer должны опираться на capability flags.

### Обязательное поведение
- действия показываются только если capability доступна;
- MTProto не маскируется под per-client protocol;
- traffic screen показывает тип статистики: `per-client` или `aggregate`.

## 4.2 Единый каталог протоколов

Нужен реестр protocol adapters:
- `vless`
- `hysteria2`
- `mtproto`

Реестр отвечает за:
- обнаружение установки;
- вызов нужного адаптера;
- отдачу capabilities;
- унифицированные статусы и ошибки.

## 4.3 Фоновые задачи

Появляется scheduler для периодических jobs:
- сбор статистики трафика;
- scheduled backups;
- health polling;
- cleanup старых backup metadata.

Для single-node режима отдельный внешний broker не нужен.

## 5. Hysteria2 — требования фазы

## 5.1 Цель
Добавить управляемую установку Hysteria2 и клиентский access flow.

## 5.2 Scope реализации
- установка Hysteria2 через бота;
- выбор порта: вручную или рекомендованный `443/UDP`;
- настройка TLS mode;
- создание клиентских доступов в поддерживаемой модели;
- генерация client URI и/или YAML config;
- подключение Traffic Stats API;
- health/status экран.

## 5.3 Техническая стратегия

### Управление
- systemd service;
- YAML config под root-owned path;
- install через pinned binary/install script;
- firewall rule для UDP порта;
- локальный traffic stats endpoint.

### Конфиги
Хранить:
- listen port;
- TLS mode;
- auth mode;
- traffic stats endpoint settings;
- client metadata в SQLite;
- резервную копию server YAML перед изменениями.

### Клиентские материалы
Минимум один из форматов должен поддерживаться:
- `hysteria2://...` URI;
- YAML client config file.

Если URI недостаточен для всех параметров, бот отправляет YAML как документ.

## 5.4 Архитектурное условие

Перед полноценной реализацией per-user management для Hysteria2 требуется technical spike:
- проверить выбранный auth mode;
- подтвердить, что есть управляемая и обратимая модель create/delete users;
- подтвердить, что traffic stats соотносятся с user identities.

Если это не подтверждается, Phase 2 должна явно ограничить Hysteria2 support до server-level install + shared access mode, без ложного UI про отдельных клиентов.

## 6. MTProto Proxy — требования фазы

## 6.1 Цель
Добавить Telegram-native proxy endpoint как отдельный управляемый режим доступа.

## 6.2 Scope реализации
- установка MTProto Proxy;
- выбор порта: вручную или рекомендованный `443`;
- генерация share links;
- health/status;
- включение/выключение proxy;
- ротация secret;
- aggregate traffic display.

## 6.3 Ограничение предметной области

MTProto не должен насильно вписываться в модель `client CRUD`, если выбранная реализация не поддерживает этого нативно.

Следовательно:
- `create client` для MTProto отсутствует;
- `delete client` для MTProto отсутствует;
- вместо этого есть `rotate access secret` и `get proxy link`.

## 6.4 Техническая стратегия
- systemd unit;
- installer/config based deployment;
- link generation на стороне бота по параметрам `host + port + secret + mode`;
- aggregate monitoring через доступные process/network counters.

## 7. Трафик и мониторинг

## 7.1 Цель
Дать администратору понятный экран использования.

## 7.2 Модель данных
Добавляется периодический сбор `TrafficSnapshot`.

### Для VLESS
Источник: Xray Stats API/CLI.
Метрика: per-client `rx/tx`.

### Для Hysteria2
Источник: Hysteria Traffic Stats API (`/traffic`).
Метрика: per-user `rx/tx`, если user model подтверждена.

### Для MTProto
Источник: aggregate counters на уровне процесса/сервиса/интерфейса.
Метрика: total rx/tx, без user breakdown.

## 7.3 Экран трафика
UI должен показывать:
- протокол;
- тип статистики;
- временную отметку последнего сбора;
- список клиентов и объёмы трафика, если доступно;
- aggregate totals, если только они доступны.

## 8. Telegram UX Phase 2

## 8.1 Inline navigation
Добавить:
- inline keyboard;
- callback-based navigation;
- вложенные экраны: `Протоколы → Конкретный протокол → Действия`.

Согласно Bot API:
- после каждого нажатия на inline button обязателен `answerCallbackQuery`;
- состояние экрана должно редактироваться через `editMessageReplyMarkup`/message edit, где уместно.

## 8.2 Рекомендуемая структура меню
- `Протоколы`
- `VLESS`
- `Hysteria2`
- `MTProto`
- `Клиенты`
- `Трафик`
- `Backup`
- `Статус`

## 8.3 UX-требования
- меню не должно разрастаться в длинный текстовый список;
- контекст должен быть виден в заголовке экрана;
- destructive actions требуют подтверждения;
- бот должен уметь вернуться на предыдущий экран.

## 9. Backup требования

## 9.1 Scope
- manual backup по кнопке/команде;
- scheduled backup;
- backup SQLite;
- backup protocol configs;
- backup metadata по сервисам.

## 9.2 Формат backup
Архив с:
- `db.sqlite3`
- `xray-config.json`
- `hysteria-config.yaml`
- `mtproto-config.*`
- manifest c timestamp, checksum, versions

## 9.3 Ограничения
- restore может остаться semi-manual;
- отправка full backup в Telegram не обязательна из соображений размера и безопасности;
- можно ограничиться локальным сохранением и статусом в боте.

## 10. Шаги реализации

1. Вынести protocol registry и capability model в отдельные доменные контракты.
2. Реализовать inline-menu router и callback handlers.
3. Доработать SQLite schema под capabilities, traffic snapshots, scheduled jobs.
4. Добавить VLESS traffic collector.
5. Реализовать Hysteria2 adapter и technical spike по user model.
6. Реализовать Hysteria2 client material generation.
7. Реализовать Hysteria2 traffic collector.
8. Реализовать MTProto adapter.
9. Реализовать MTProto share link generation.
10. Реализовать aggregate stats collection для MTProto.
11. Реализовать backup orchestrator.
12. Добавить scheduled jobs и retention policy.
13. Написать integration tests для всех adapter contracts.
14. Написать system smoke сценарии по каждому протоколу.

## 11. Риски и митигация

### Риск: Hysteria2 не даёт удобную CRUD-модель пользователей
Митигация:
- провести spike до полной реализации;
- использовать capability flag `supports_individual_clients = false/conditional`;
- fallback на shared access mode.

### Риск: MTProto UX будет путать пользователей с обычными VPN-протоколами
Митигация:
- раздельные экраны;
- явные подписи `Proxy endpoint`, `Rotate secret`, `Get link`;
- не показывать действия CRUD клиентов.

### Риск: stats collectors начинают ломать сервис или давать inconsistent data
Митигация:
- collectors read-only;
- timeouts и retry policy;
- запись отметки `collection_failed` без падения бота.

### Риск: inline navigation усложнит логику состояний
Митигация:
- state machine для UI;
- ограничить глубину меню;
- хранить минимальный ephemeral context.

### Риск: backup архивы содержат чувствительные данные
Митигация:
- root-only permissions;
- checksum + metadata без secrets в логах;
- опциональное шифрование archive на Phase 3.

## 12. Тестирование фазы

### Unit
- capability resolver;
- callback router;
- link generators;
- traffic parsers;
- backup manifest builder.

### Integration
- VLESS adapter + stats;
- Hysteria2 adapter + traffic API parser;
- MTProto adapter + share links;
- repositories + scheduler.

### System
- install each protocol;
- generate access material;
- collect traffic;
- create manual backup;
- navigation through inline menu.

## 13. Definition of Done

Phase 2 считается завершённой, если:
- через Telegram можно установить VLESS, Hysteria2 и MTProto независимо друг от друга;
- UI корректно скрывает недоступные действия по capability model;
- VLESS выдаёт per-client traffic;
- Hysteria2 выдаёт per-client traffic или явно работает в documented limited mode;
- MTProto выдаёт share links и aggregate traffic/status;
- бот использует inline-кнопки и callback navigation без зависающих действий;
- backup можно запустить вручную и по расписанию;
- есть integration tests по всем protocol adapters;
- есть system smoke tests по ключевым сценариям.

## 14. Артефакты фазы

На выходе Phase 2 должны существовать:
- Hysteria2 adapter;
- MTProto adapter;
- protocol registry + capability model;
- traffic collectors;
- backup orchestrator;
- inline-menu UI layer;
- обновлённая schema/migrations;
- integration/system test suite.
