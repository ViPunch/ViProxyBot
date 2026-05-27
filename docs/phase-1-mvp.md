# Phase 1 — MVP

## 1. Цель фазы

Собрать минимально рабочий, деплойабельный продукт, который:
- устанавливает Telegram-бота на VPS;
- позволяет через Telegram установить один VPN-протокол на этот же VPS;
- позволяет создать и удалить клиента;
- генерирует и отправляет ссылку для подключения;
- предоставляет простое текстовое меню.

Phase 1 должна доказать, что модель `bot as control plane` работает без CLI после первичной установки.

## 2. Scope

## Входит в Phase 1
- bootstrap/install script для VPS;
- запуск бота как systemd service;
- white-list из одного или нескольких admin пользователей;
- long polling Telegram Bot API;
- простое текстовое меню на основе команд и reply keyboard;
- поддержка одного протокола: `VLESS (Xray-core)`;
- установка VLESS через бота;
- создание клиента VLESS;
- удаление клиента VLESS;
- генерация VLESS connection link;
- хранение состояния в SQLite;
- базовый аудит действий;
- базовые health/status команды;
- backup конфига VLESS перед мутациями.

## Не входит в Phase 1
- Hysteria2;
- MTProto Proxy;
- inline-кнопки и вложенные меню;
- per-client мониторинг трафика;
- автообновления;
- CI/CD;
- алертинг;
- multi-admin granular roles;
- webhook mode;
- полноценный restore workflow;
- высокая доступность и multi-server поддержка.

## 3. Почему VLESS выбран для MVP

VLESS лучше всего подходит как первый протокол, потому что:
- имеет понятную модель individual clients через UUID;
- конфиг клиентов хранится явно в Xray JSON;
- возможно генерировать share link детерминированно;
- доступен путь к per-user traffic stats через Xray Stats API;
- lifecycle хорошо укладывается в pattern `config file + systemd service`.

## 4. Пользовательские сценарии

## 4.1 Первый запуск
1. Оператор запускает install script на VPS.
2. Скрипт разворачивает бота и запускает systemd unit.
3. Оператор открывает бота в Telegram и отправляет `/start`.
4. Бот проверяет admin whitelist и показывает текстовое меню.

## 4.2 Установка VLESS
1. Администратор выбирает `Установить VLESS`.
2. Бот предлагает:
   - указать порт вручную;
   - или использовать рекомендованный `443`.
3. Бот валидирует порт и проверяет его доступность.
4. Бот устанавливает Xray-core, пишет конфиг, открывает порт и запускает сервис.
5. Бот сообщает статус установки.

## 4.3 Создание клиента
1. Администратор выбирает `Создать клиента`.
2. Бот запрашивает имя клиента.
3. Бот генерирует UUID.
4. Бот добавляет клиента в Xray config.
5. Бот валидирует конфиг и reload/restart сервис.
6. Бот отправляет ссылку подключения.

## 4.4 Удаление клиента
1. Администратор выбирает `Удалить клиента`.
2. Бот показывает список клиентов в текстовом виде.
3. Администратор выбирает клиента по имени/ID.
4. Бот просит подтверждение.
5. Бот удаляет клиента из конфига и БД.
6. Бот перезагружает сервис и подтверждает результат.

## 5. Технический scope реализации

## 5.1 ОС и инфраструктура
- primary target: Ubuntu LTS;
- systemd обязателен;
- root доступ нужен только на этапе установки и для protocol-level операций;
- IPv4 обязателен, IPv6 опционален.

## 5.2 Бот
- транспорт: Telegram Bot API через long polling;
- режим работы: private chat only;
- одно активное меню в виде текстовых кнопок;
- обработка команд `/start`, `/menu`, `/status`, `/protocols`, `/clients`.

## 5.3 Хранилище
SQLite содержит:
- admin whitelist;
- состояние установки бота;
- состояние установки VLESS;
- список клиентов VLESS;
- audit events;
- backup metadata.

## 5.4 VLESS adapter
MVP-адаптер должен уметь:
- определить, установлен ли Xray;
- установить Xray;
- создать VLESS inbound config;
- добавить клиента;
- удалить клиента;
- сгенерировать VLESS URL;
- проверить здоровье сервиса;
- сделать backup конфига перед изменением.

## 6. Контракты и правила Phase 1

## 6.1 Контракт установки VLESS

### Вход
- `listen_port`
- `transport_profile` (в MVP один фиксированный профиль)
- `tls_mode`
- `public_host` или `server_ip`

### Выход
- `status`
- `service_name`
- `config_path`
- `listen_port`
- `generated_server_metadata`

### Preconditions
- бот авторизован как admin;
- порт свободен;
- runtime окружение готово;
- директории для конфига и backup существуют.

### Postconditions
- Xray установлен;
- systemd service создан и активен;
- конфиг валиден;
- порт открыт;
- бот сохранил installation state в SQLite.

## 6.2 Контракт создания клиента

### Вход
- `external_name`

### Выход
- `client_id`
- `uuid`
- `access_link`
- `created_at`

### Preconditions
- VLESS установлен и активен;
- имя клиента валидно и уникально в рамках протокола.

### Postconditions
- клиент записан в SQLite;
- клиент добавлен в Xray config;
- сервис успешно reloaded/restarted;
- ссылка отправлена администратору.

## 7. Выбранный профиль VLESS для MVP

Чтобы избежать лишней сложности, MVP использует один supported profile.

### Требования к профилю
- один inbound;
- TLS включён;
- один listen port;
- детерминированная генерация client link;
- возможность дальнейшего расширения до stats API.

### Ограничение
В MVP не поддерживаются множественные transport-профили, REALITY/fallback chains и сложные multi-inbound схемы.
Они переносятся в будущие фазы только при отдельной необходимости.

## 8. Меню MVP

## Главное меню
- `Статус`
- `Установить VLESS`
- `Клиенты VLESS`
- `Создать клиента`
- `Удалить клиента`
- `Получить ссылку`

## Принципы
- меню текстовое и простое;
- один сценарий — одна команда;
- после каждой операции бот возвращает пользователя в понятное состояние.

## 9. Шаги реализации

1. Спроектировать SQLite schema для admins, protocols, clients, audit, backups.
2. Реализовать bootstrap/install script.
3. Реализовать systemd unit для бота.
4. Реализовать Telegram polling loop и базовый command router.
5. Реализовать admin whitelist middleware.
6. Реализовать ShellRunner с timeout и redaction.
7. Реализовать VLESS/Xray adapter.
8. Реализовать safe config writer: parse → modify → backup → validate → replace.
9. Реализовать сценарий установки VLESS через Telegram.
10. Реализовать сценарии create/delete client.
11. Реализовать генератор VLESS link на основе фактического server config.
12. Реализовать `/status` и базовые health checks.
13. Реализовать базовый audit log.
14. Прогнать smoke tests на чистом VPS.

## 10. Безопасность Phase 1

### Обязательно
- private chat only;
- whitelist по `telegram_user_id`;
- команды только для авторизованных admin;
- никакого выполнения пользовательских shell-команд;
- все секреты только в env или protected files;
- backup до мутации config;
- валидация имён клиентов и портов;
- no secrets in logs.

### Достаточно для MVP
- без RBAC;
- без внешнего secret manager;
- без webhook hardening.

## 11. Риски и митигация

### Риск: Xray не стартует после мутации конфига
Митигация:
- backup предыдущего конфига;
- validate перед replace;
- rollback при failed reload.

### Риск: пользователь выбирает занятый порт
Митигация:
- pre-flight port check;
- рекомендация порта `443`;
- понятная ошибка с предложением повторить.

### Риск: ссылка не соответствует серверному профилю
Митигация:
- генерация из runtime config, а не из шаблона;
- integration test на link generation.

### Риск: администратор случайно удаляет клиента
Митигация:
- обязательное подтверждение удаления;
- audit trail;
- backup config.

### Риск: bootstrap повторно ломает установленный инстанс
Митигация:
- install script должен быть idempotent;
- destructive шаги требуют флага/подтверждения.

## 12. Definition of Done

Phase 1 считается завершённой, если:
- install script поднимает бота на чистом Ubuntu LTS VPS;
- бот отвечает в Telegram после установки;
- бот пускает только whitelist admin;
- VLESS можно установить через Telegram без ручного редактирования файлов;
- можно создать минимум одного клиента;
- можно удалить клиента;
- бот отправляет валидную ссылку подключения;
- после reboot бот и VLESS поднимаются автоматически;
- конфиг VLESS бэкапится перед изменением;
- есть базовый audit log;
- smoke test сценарий проходит от начала до конца.

## 13. Артефакты фазы

На выходе Phase 1 должны существовать:
- install script;
- systemd unit бота;
- SQLite schema + migrations;
- VLESS protocol adapter;
- Telegram bot handlers MVP;
- docs/runbook по установке и smoke-check;
- automated или semi-automated smoke test checklist.
