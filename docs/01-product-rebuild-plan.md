# ViProxyBot Rebuild Plan: bot-managed VPS core

## 1. Product Decision

ViProxyBot is being rebuilt around the 3x-ui operating model, but without a web
panel.

The target product is:

- one-command VPS installer;
- interactive bootstrap wizard during installation;
- automatic installation of VPN/proxy cores and local services;
- SSL certificate setup during installation;
- Telegram bot as the only admin panel;
- protocol lifecycle, client lifecycle, access links, traffic and health managed
  from the bot.

The bot must replace the 3x-ui web panel. Do not embed, expose, proxy, or depend
on the 3x-ui UI as the production control surface.

## 2. Reference Projects And Sources

Use these sources as implementation references, not as copy-paste targets.

### 3x-ui

Repository: `https://github.com/MHSanaei/3x-ui`

Relevant ideas to reuse:

- one-command root installer;
- OS and architecture detection;
- package bootstrap per distro;
- random secure defaults;
- interactive questions during first install;
- acme.sh based SSL setup;
- choices for certificate mode;
- systemd/openrc service setup;
- firewall guidance;
- release artifact download instead of building everything from source.

Relevant 3x-ui SSL choices to adapt:

- Let's Encrypt certificate for domain;
- Let's Encrypt certificate for IP address where supported;
- custom existing certificate paths;
- skip SSL only as advanced fallback behind reverse proxy or SSH tunnel.

For this project we should expose 3 primary choices in the first production
installer:

1. Let's Encrypt domain certificate via acme.sh standalone HTTP-01.
2. Existing/custom certificate path.
3. Skip SSL with explicit warning and local-only/reverse-proxy recommendation.

IP certificates can be a later enhancement because they are short-lived, more
fragile, and not universally expected by operators.

### Xray-core

Use Xray-core for VLESS/REALITY and future Xray-backed protocols.

Current project already installs Xray from:

`https://github.com/XTLS/Xray-install/raw/main/install-release.sh`

Keep the installer idempotent and pin/version-control this decision before prod.

### Hysteria2

Use official Hysteria2 release/install path. Before implementation, verify the
current official installation command and config format from upstream docs.

Do not invent config fields from memory.

### MTProto

Official repository:

`https://github.com/TelegramMessenger/MTProxy`

Official run model:

- install build dependencies;
- clone repository;
- build with `make`;
- download `proxy-secret` from `https://core.telegram.org/getProxySecret`;
- download `proxy-multi.conf` from `https://core.telegram.org/getProxyConfig`;
- generate one or more 16-byte hex secrets;
- run `mtproto-proxy -u nobody -p 8888 -H <public_port> -S <secret> --aes-pwd proxy-secret proxy-multi.conf -M <workers>`;
- collect stats from local stats port, for example `127.0.0.1:8888/stats`;
- update `proxy-multi.conf` daily.

MTProto recommendation for this product:

- install MTProxy during main bootstrap as an optional component;
- default to disabled until configured if port conflicts exist;
- manage secrets and service state from the bot;
- implement daily refresh of `proxy-multi.conf` through a systemd timer or bot
  background job;
- expose MTProto as server-level proxy access, not as rich per-user VPN accounts.

Reason: the official MTProxy model supports multiple secrets, but its management
and traffic attribution are weaker than Xray clients. Per-client UX can be built
by issuing one secret per user, but traffic accounting must be treated as
best-effort until verified against real stats output.

## 3. Target Architecture

Keep the existing layered architecture and make it stricter.

```text
domain/              business entities and protocol capability model
services/            orchestration use-cases used by Telegram handlers
infrastructure/      systemd, shell, firewall, acme, protocol adapters, files
interface/telegram/  bot commands, callback routing, screens, text
database/            SQLite schema, repositories, migrations
scripts/             VPS bootstrap/update/restore scripts
docs/                specs, playbooks, operator docs
```

Core rule: Telegram handlers must never edit config files or call shell commands
directly. They call services. Services call protocol adapters and infrastructure
adapters. All shell execution goes through `ShellRunner`.

## 4. Protocol Roles

Each protocol must have a clear product role. Do not present all protocols as the
same thing if their capabilities differ.

### VLESS/REALITY through Xray

Role: primary general-purpose VPN access.

Required capabilities:

- install Xray;
- generate REALITY keys;
- create/delete/disable clients;
- generate VLESS access URI;
- reload service safely;
- collect traffic per client from Xray stats API or logs;
- validate config before restart;
- backup config before every mutation.

### Hysteria2

Role: UDP/QUIC-oriented fallback for networks where VLESS is unstable or slow.

Required capabilities:

- install Hysteria2;
- bind UDP port;
- configure TLS certificate path from SSL manager;
- create/delete/disable users where supported by config;
- generate `hysteria2://` links;
- collect available traffic metrics or mark traffic as unsupported until real
  metrics are implemented;
- validate config before restart.

### MTProto

Role: Telegram-specific proxy, not a full VPN.

Required capabilities:

- install official Telegram MTProxy;
- download and refresh Telegram proxy data;
- generate and revoke secrets;
- generate `tg://proxy` and `https://t.me/proxy` links;
- optionally register tag from `@MTProxybot` as an admin-provided value;
- expose stats from local stats endpoint if available;
- clearly mark per-client traffic as `best_effort` until verified.

## 5. Bootstrap Installer Requirements

The installer must become the foundation of the product.

Command shape:

```bash
curl -fsSL https://raw.githubusercontent.com/ViPunch/ViProxyBot/main/scripts/install.sh | sudo bash
```

Required first-run questions:

- Telegram bot token;
- Telegram admin IDs;
- public host: auto-detected IP, domain, or manual host;
- SSL mode: domain via acme.sh, custom paths, or skip with warning;
- protocols to install now: VLESS default yes, Hysteria2 optional, MTProto optional;
- ports for selected protocols with recommended defaults and conflict detection;
- whether to enable automatic updates for proxy data/config metadata.

Installer must do:

- root check;
- OS detection with supported distro matrix;
- architecture detection;
- package installation;
- app user and directories creation;
- `.env` creation with `0600` permissions;
- SQLite/data directories creation;
- acme.sh installation when SSL domain mode is selected;
- certificate installation into stable project-owned paths;
- selected core installation;
- systemd unit creation for `vpnbot`;
- systemd units/timers for protocol services where needed;
- firewall opening only for selected ports;
- final summary with bot status and safe next step.

Installer must not:

- grant broad passwordless sudo such as unrestricted `/bin/bash`;
- write secrets to world-readable files;
- log bot token, proxy secrets, private keys, full client links;
- delete existing protocol configs without backup;
- assume port 443 can be shared by multiple services unless a deliberate inbound
  routing design is implemented.

## 6. Port And Routing Decision

Do not bind VLESS TCP 443, Hysteria2 UDP 443, and MTProto TCP 443 blindly.

Safe MVP defaults:

- VLESS/REALITY: TCP 443 when available;
- Hysteria2: UDP 443 if TCP 443 is used by VLESS, otherwise ask;
- MTProto: TCP 8443 or another explicit port if TCP 443 is already used.

Later production routing can add advanced sharing through nginx/Caddy/SNI or
Xray fallback, but that is a separate phase and must be tested on a real VPS.

## 7. Database And Domain Changes

Move from minimal tables to production-ready state tracking through additive
migrations.

Required additions:

- migration mechanism with schema version table;
- `protocol_installations.capabilities_json`;
- `protocol_installations.last_health_json`;
- `client_credentials.secret_type`;
- encrypted `client_credentials.secret_value_encrypted`;
- `client_credentials.metadata_json`;
- `traffic_snapshots.source`;
- `traffic_snapshots.confidence` (`exact`, `estimated`, `best_effort`, `unsupported`);
- `certificate_assets` table for SSL state;
- `system_tasks` table for install/update/refresh jobs visible in the bot;
- audit events for every install, mutation, secret reveal, backup, restore.

Do not rewrite existing tables destructively. Use additive migrations and data
backfill.

## 8. Bot Admin UX

The bot is the production panel.

Main menu:

- Status;
- Protocols;
- Clients;
- Traffic;
- SSL;
- Backups;
- Settings;
- Help.

Protocol screen must show:

- installed/not installed;
- service status;
- listen port;
- certificate status if relevant;
- last config backup;
- buttons: install, restart, validate, clients, traffic, backup, logs summary.

Client screen must support:

- create client;
- delete/revoke client with confirmation;
- get access link;
- show traffic;
- rename label;
- disable/enable where supported.

Long operations must create visible task state:

- started;
- running;
- completed;
- failed with safe error message.

## 9. Development Phases

### Phase 0: Audit And Stabilize Current Code

Goal: understand what exists and prevent regressions.

Tasks:

- run current tests, ruff, mypy;
- map implemented protocol capabilities vs claimed capabilities;
- document broken/placeholder behavior;
- tighten `ShellRunner` and sudoers policy;
- add migration baseline without changing behavior;
- add tests around existing link generators and config writers.

Exit criteria:

- current test suite green;
- known gaps listed;
- no production claim remains undocumented.

### Phase 1: Production Bootstrap Foundation

Goal: one-command installer that prepares bot, SSL state, directories and safe
service permissions.

Tasks:

- redesign `scripts/install.sh` wizard;
- implement SSL manager around acme.sh/custom/skip modes;
- write stable `.env` fields for certificates and public host;
- remove broad sudo permissions;
- add `vpnbot-protocolctl` or narrow root helper commands if root operations are
  required by the running bot;
- update README/operator runbook.

Exit criteria:

- `bash -n scripts/install.sh` passes;
- install works on a clean Ubuntu/Debian VPS in dry-run or real smoke test;
- secrets are not printed except the recovery key explicitly once.

### Phase 2: Xray/VLESS As First Real Managed Protocol

Goal: one protocol fully works end-to-end.

Tasks:

- install Xray idempotently;
- generate and persist REALITY keys;
- validate Xray config before restart;
- backup config before mutation;
- create/delete clients from bot;
- generate links from persisted config, not volatile adapter fields;
- implement service health;
- implement real or explicitly unsupported traffic collection.

Exit criteria:

- create client from bot returns working VLESS link;
- delete client removes access and reloads Xray;
- restart failure rolls back or leaves a clear degraded state;
- tests cover config mutation and link generation.

### Phase 3: Hysteria2

Goal: add second production protocol without weakening architecture.

Tasks:

- verify official Hysteria2 install and config docs;
- implement adapter with same lifecycle contract;
- use certificate paths from SSL manager;
- add UDP firewall handling;
- add bot screens and capability flags;
- add tests for config and links.

Exit criteria:

- Hysteria2 can be installed, started, restarted, backed up and managed from bot;
- unsupported capabilities are hidden or marked clearly.

### Phase 4: MTProto

Goal: official Telegram MTProxy automated safely.

Tasks:

- build/install from `TelegramMessenger/MTProxy` or use a pinned package/artifact
  if a maintained option is chosen and documented;
- create system user and systemd unit;
- manage `proxy-secret`, `proxy-multi.conf`, client secrets and optional proxy tag;
- refresh Telegram config daily;
- parse stats endpoint after capturing real output;
- expose Telegram proxy links in bot.

Exit criteria:

- MTProxy starts after reboot;
- generated link opens in Telegram clients;
- secret revoke requires service reload and is audited;
- stats behavior is tested or marked as best-effort.

### Phase 5: Production Hardening

Goal: make the product supportable.

Tasks:

- structured logs with secret redaction;
- audit trail in bot;
- backup/restore tested;
- health checks per service;
- update flow;
- CI for lint/types/tests/shell syntax;
- operator docs for failure recovery.

Exit criteria:

- clean install, update, backup, restore and uninstall are documented;
- CI is green;
- operator can recover from broken protocol config without manual code edits.

## 10. Agent Rules

Every agent must follow `AGENTS.md` and this document.

Hard rules:

- read `AGENTS.md`, `docs/README.md`, this file, and the current phase document
  before coding;
- inspect current code before changing it;
- make minimal diffs;
- keep old behavior unless the phase explicitly replaces it;
- never edit secrets or `.env` values into git;
- never use direct `subprocess` outside `ShellRunner` or approved root helpers;
- never log full access links, private keys, bot tokens, MTProxy secrets or cert
  private keys;
- never add a dependency without documenting why;
- never mark a protocol capability as done unless it is installed, configured,
  managed and verified;
- all destructive bot actions require confirmation and audit;
- if a protocol cannot support per-client traffic reliably, expose that limitation
  honestly in capability flags.

Required verification before handoff:

```bash
ruff check .
mypy src
python -m pytest tests/ -v
bash -n scripts/install.sh
bash -n scripts/update.sh
bash -n scripts/restore.sh
```

If a check cannot run locally, the agent must state the exact reason and what was
verified instead.

## 11. Prompts For Agents

### Prompt: Phase 0 Audit Agent

```text
You are working on ViProxyBot. Read AGENTS.md, docs/README.md and
docs/01-product-rebuild-plan.md first. Do not write feature code.

Task: audit the current code against the rebuild plan. Produce a concise report
in docs/current-state-audit.md with:
- implemented capabilities;
- placeholders and broken assumptions;
- security risks, especially shell/sudo/secrets;
- protocol-specific gaps for VLESS, Hysteria2, MTProto;
- exact tests/checks run and results.

Keep the report factual. Do not rewrite architecture documents.
```

### Prompt: Installer Agent

```text
You are implementing Phase 1 of docs/01-product-rebuild-plan.md.
Read AGENTS.md and current installer code first.

Task: redesign scripts/install.sh into a production bootstrap wizard inspired by
3x-ui, but for ViProxyBot without a web panel. Implement only Phase 1 scope:
bot install, app user, directories, .env, SSL state, safe service setup, narrow
permissions, firewall helpers and final summary.

Rules:
- do not install all protocols yet unless the phase explicitly requires it;
- do not grant passwordless /bin/bash;
- do not print tokens or private keys in logs;
- keep idempotency and backups for existing files;
- update README and operator runbook.

Verification: bash -n scripts/install.sh, existing tests, and any shell helper
syntax checks.
```

### Prompt: VLESS Agent

```text
You are implementing Phase 2 of docs/01-product-rebuild-plan.md.
Read the existing VLESS adapter, config writer, tests and ShellRunner before
editing.

Task: make VLESS/REALITY the first fully working managed protocol from Telegram
bot to Xray config and systemd service.

Rules:
- persist REALITY public/private keys and shortId safely;
- generate links from persisted config/state, not process memory;
- backup config before every mutation;
- validate config before restart;
- rollback or mark degraded on reload failure;
- add focused tests for create/delete/link/config behavior.

Verification: ruff, mypy, pytest, install script syntax.
```

### Prompt: Hysteria2 Agent

```text
You are implementing Phase 3 of docs/01-product-rebuild-plan.md.
Before coding, verify current official Hysteria2 install and config docs.

Task: add production Hysteria2 lifecycle management through the existing
ProtocolAdapter contract and Telegram UI.

Rules:
- use SSL paths from the project's SSL manager;
- handle UDP firewall rules;
- hide unsupported features through capability flags;
- do not guess config schema;
- add tests for config writer and link generation.

Verification: ruff, mypy, pytest, shell syntax checks.
```

### Prompt: MTProto Agent

```text
You are implementing Phase 4 of docs/01-product-rebuild-plan.md.
Use the official repository https://github.com/TelegramMessenger/MTProxy as the
primary source.

Task: automate MTProxy install and management without pretending it is a full VPN
protocol. Implement install/build, systemd unit, proxy data refresh, secret
management, link generation and health/stats where reliable.

Rules:
- use official MTProxy commands and files;
- refresh proxy-multi.conf daily;
- generate one secret per bot client only if revoke and link behavior are tested;
- mark traffic as best_effort unless stats are verified against real output;
- never log MTProxy secrets or full proxy links;
- add tests around link generation and service config rendering.

Verification: ruff, mypy, pytest, shell syntax checks. Real VPS smoke test is
required before declaring production readiness.
```

### Prompt: Production Hardening Agent

```text
You are implementing Phase 5 of docs/01-product-rebuild-plan.md.

Task: harden ViProxyBot for production operations: logging redaction, audit,
backup/restore, health checks, update flow, CI and operator documentation.

Rules:
- do not change protocol behavior except to make errors safer;
- every admin mutation must be audited;
- backups must include DB, protocol configs and certificate metadata, but never
  expose secrets in logs;
- recovery docs must be executable by an operator on a VPS.

Verification: full local check suite and one documented clean VPS smoke test.
```

## 12. Immediate Next Step

Start with Phase 0 audit before rewriting installer or protocol code. The current
project already contains partial VLESS, Hysteria2 and MTProto code, but some
parts are placeholders and some installation behavior is too permissive for prod.

After Phase 0, implement Phase 1 installer foundation. Then make VLESS truly
production-ready before adding more protocol surface.
