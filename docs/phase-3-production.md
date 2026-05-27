# Phase 3 — Production

## 1. Цель фазы

Довести продукт до production-grade эксплуатации на одном VPS: усилить безопасность, наблюдаемость, обновляемость, качество документации и предсказуемость поставки изменений.

Phase 3 не должна ломать архитектуру MVP/Phase 2, а должна укрепить её.

## 2. Scope

## Входит в Phase 3
- admin-only hardening;
- rate limiting;
- расширенный аудит и структурированные логи;
- алертинг;
- auto-update strategy для бота;
- документация для конечного пользователя;
- CI/CD pipeline;
- release process;
- backup hardening;
- restore runbook;
- production smoke checks;
- upgrade/migration strategy.

## Не входит в Phase 3
- multi-server orchestration;
- SaaS-режим;
- billing;
- self-service end-user portal;
- web dashboard;
- горизонтальное масштабирование.

## 3. Production требования

Система должна:
- безопасно переживать reboot VPS;
- ограничивать доступ только доверенным администраторам;
- не раскрывать секреты в логах и сообщениях;
- позволять обновлять бота с rollback strategy;
- иметь понятную документацию установки, эксплуатации и восстановления;
- проходить автоматические проверки в CI/CD.

## 4. Безопасность

## 4.1 Admin-only доступ

Обязательные требования:
- whitelist по `telegram_user_id`;
- private chat only по умолчанию;
- блокировка любых групповых сценариев, если они явно не разрешены;
- поддержка deactivation admin account;
- аудит всех административных действий.

## 4.2 Rate limiting

Нужны лимиты минимум на:
- количество команд в минуту на user;
- количество попыток destructive actions;
- количество неуспешных auth/whitelist access attempts;
- частоту heavy operations: install, reload, backup, update.

### Цель
Не допускать случайного DoS от самого администратора и усложнить abuse при компрометации Telegram-аккаунта.

## 4.3 Управление привилегиями

Root-привилегии должны быть минимизированы.

### Подход
- бот запускается под отдельным системным пользователем;
- только ограниченный список операций выполняется через `sudo` allowlist или root-owned helper;
- helper принимает только строго валидированные параметры;
- прямой root shell из приложения запрещён.

## 4.4 Секреты

Обязательные меры:
- bot token только в env/protected secret file;
- encryption key для local secret store вне репозитория;
- protocol secrets не логируются;
- backup secrets по возможности шифруются перед архивированием.

## 5. Логирование и аудит

## 5.1 Структурированные логи
Все production-логи должны быть машинно-читаемыми.

### Минимальные поля
- `timestamp`
- `level`
- `event`
- `actor_id`
- `protocol`
- `operation`
- `status`
- `error_code`
- `trace_id`

### Redaction rules
- скрывать bot token;
- скрывать UUID/пароли/секреты полностью или частично;
- не логировать полные connection links.

## 5.2 Audit trail

Аудит обязателен для:
- install/uninstall протоколов;
- create/delete/rotate access material;
- backup actions;
- config reload;
- bot update;
- admin access denials.

## 6. Алертинг и health

## 6.1 Health checks
Нужны регулярные проверки:
- bot polling alive;
- DB доступна;
- protocol service active;
- traffic collector работает;
- backup scheduler работает.

## 6.2 Алерты
Минимальные production-алерты:
- бот не может общаться с Telegram API N минут;
- protocol service down;
- backup failed N раз подряд;
- disk space ниже порога;
- repeated config validation failures;
- update failed.

### Канал алертов
Минимально допустимо:
- отправка администратору в Telegram;
- запись в системные логи.

Опционально:
- email/webhook/syslog sink.

## 7. Auto-update стратегия

## 7.1 Цель
Обновлять бота без ручного SSH-редактирования и без разрушения состояния.

## 7.2 Требования
- pinned release source;
- pre-update backup;
- migration step для SQLite/schema;
- post-update smoke-check;
- rollback strategy при сбое.

## 7.3 Ограничения
- автообновление protocol binaries не обязано входить в первый production release;
- сначала достаточно auto-update самого бота;
- обновление Xray/Hysteria2/MTProto лучше оформлять как отдельные административные действия.

## 8. Документация для конечного пользователя

Должны появиться документы:
- как установить бота на VPS;
- как привязать admin Telegram ID;
- как установить каждый протокол;
- как создать доступ;
- как посмотреть трафик;
- как сделать backup;
- как восстановиться после сбоя;
- какие ограничения есть у MTProto относительно клиентов и статистики.

Документация должна быть короткой, пошаговой и не требовать знаний внутренней архитектуры.

## 9. CI/CD pipeline

## 9.1 CI
На каждый PR/merge должны запускаться:
- formatter/lint;
- type checks;
- unit tests;
- integration tests на поддерживаемом окружении;
- markdown/docs lint, если принят в проекте;
- security checks зависимостей, если доступны без лишней сложности.

## 9.2 CD
Минимальный production pipeline:
1. build release artifact;
2. прогон тестов;
3. публикация versioned artifact;
4. deploy на target VPS;
5. post-deploy smoke-check;
6. уведомление об успехе/ошибке.

## 9.3 Релизная стратегия
Рекомендуется:
- semantic versioning;
- changelog;
- tagged releases;
- отдельный rollback procedure.

## 10. Миграции и совместимость

### Требования
- все изменения схемы БД должны быть мигрируемыми;
- новые релизы не должны ломать существующий state без миграции;
- destructive migrations запрещены без отдельного окна/плана;
- пользовательские протокольные конфиги должны быть обратно совместимы или мигрироваться явно.

## 11. Backup/restore hardening

## 11.1 Backup
Production backup должен включать:
- SQLite;
- protocol configs;
- encrypted secrets store;
- release metadata;
- checksums.

## 11.2 Restore runbook
Должен быть документирован порядок:
1. остановить бота;
2. восстановить артефакты;
3. проверить права доступа;
4. восстановить БД;
5. восстановить конфиги протоколов;
6. поднять systemd services;
7. выполнить smoke-check.

## 12. Шаги реализации

1. Добавить middleware rate limiting и abuse protection.
2. Усилить whitelist/admin management.
3. Вынести privileged operations в безопасный helper/allowlist.
4. Перевести логи в structured format.
5. Завершить audit trail по всем критичным операциям.
6. Добавить health scheduler и alert dispatcher.
7. Реализовать release/update orchestrator.
8. Описать rollback flow.
9. Подготовить end-user docs и operator runbooks.
10. Настроить CI pipeline.
11. Настроить CD pipeline.
12. Прогнать production-like smoke test после deploy/update.

## 13. Риски и митигация

### Риск: автообновление ломает рабочий инстанс
Митигация:
- pre-update backup;
- staged update flow;
- schema migrations с backward planning;
- rollback procedure.

### Риск: excessive logging раскрывает секреты
Митигация:
- единый redaction layer;
- log review checklist;
- тесты на redaction.

### Риск: rate limiting мешает легитимной админ-работе
Митигация:
- разные лимиты для read/write/heavy actions;
- понятные сообщения о блокировке;
- метрики по rate limit hits.

### Риск: CI/CD станет слишком сложным для single-VPS проекта
Митигация:
- минималистичный pipeline;
- только реально полезные проверки;
- без лишней инфраструктуры.

### Риск: production docs устареют
Митигация:
- документы входят в DoD релиза;
- обновление docs обязательно при изменении install/update/restore flow.

## 14. Definition of Done

Phase 3 считается завершённой, если:
- доступ к боту ограничен admin whitelist и rate limiting работает;
- privileged operations минимизированы и контролируемы;
- логи структурированы и не содержат секретов;
- есть алерты на ключевые operational failures;
- бот можно обновить с backup и rollback strategy;
- подготовлена документация для конечного пользователя и оператора;
- CI запускает lint, typecheck и tests;
- CD может доставить релиз на VPS и прогнать smoke-check;
- процесс восстановления после сбоя документирован и проверен.

## 15. Артефакты фазы

На выходе Phase 3 должны существовать:
- security hardening middleware;
- privileged helper/allowlist design;
- structured logging + audit implementation;
- alerting module;
- update/rollback mechanism;
- end-user docs;
- operator runbooks;
- CI/CD configuration;
- tested restore procedure.
