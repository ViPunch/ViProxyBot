# ViProxyBot — Current State Audit (Phase 0)

> Дата: 2026-05-27
> Цель: зафиксировать реальное состояние кода перед перестройкой по `01-product-rebuild-plan.md`.

---

## 1. Verification Results

| Check | Result |
|-------|--------|
| `ruff check .` | ✅ All checks passed |
| `mypy src` | ✅ Success (49 files, 1 note about untyped defs) |
| `pytest tests/ -v` | ✅ 22 passed, 1 deprecation warning |
| `bash -n scripts/install.sh` | ✅ exit 0 |
| `bash -n scripts/update.sh` | ✅ exit 0 |
| `bash -n scripts/restore.sh` | ✅ exit 0 |

**Note:** mypy note at `src/interface/telegram/commands.py:384` — untyped function body not checked. Non-blocking.

---

## 2. Architecture Overview

Clean layered architecture, well-structured:

```
domain/              — business entities, enums, exceptions, capabilities
services/            — orchestration (registry, health, traffic, backup)
infrastructure/      — shell, http, ssl, secrets, protocol adapters
interface/telegram/  — bot, commands, callbacks, keyboards, middleware, i18n
database/            — schema, connection, repositories
scripts/             — install.sh, update.sh, restore.sh
```

**Strengths:**
- Proper `ProtocolAdapter` ABC with 7 abstract methods
- Capability matrix pattern (`ProtocolCapabilities` + `CAPABILITY_MATRIX`)
- Structured JSON logging + `AuditLogger`
- Auth + rate-limit middleware on all Telegram paths
- i18n (RU/EN)
- Interactive installer with systemd integration
- Update mechanism with automatic rollback

---

## 3. Protocol Capabilities: Implemented vs Claimed

| Capability | VLESS | Hysteria2 | MTProto |
|---|---|---|---|
| Install | ✅ Full | ✅ Full | ✅ Full (build from source) |
| Detect | ✅ | ✅ | ✅ |
| Create client | ✅ Per-UUID | ⚠️ Shared password | ⚠️ Shared secret |
| Delete client | ✅ | ❌ Stub (`pass`) | ❌ Stub (`pass`) |
| Link generation | ✅ `vless://` | ✅ `hysteria2://` | ✅ `t.me/proxy?` + `tg://proxy?` |
| Per-client traffic | ✅ Xray stats API | ✅ Stats HTTP endpoint | ❌ Not supported |
| Hot reload | ✅ systemctl | ✅ systemctl | ❌ Hardcoded |
| Backup | ✅ Config copy | ✅ Config copy | ✅ Directory copy |
| Health | ✅ | ✅ | ✅ |

**Critical gaps:**
- Hysteria2 `delete_client()` is a no-op — clients cannot be removed
- MTProto `delete_client()` is a no-op
- Hysteria2 shares single auth password for all clients
- `_get_client_names()` only reads VLESS config — Hysteria2/MTProto clients never listed in UI
- MTProto has no per-client management

---

## 4. Security Issues

### CRITICAL

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| 1 | Sudoers grants `NOPASSWD: /bin/bash` | `scripts/install.sh:124` | Unrestricted root access for service user |
| 2 | Sudoers grants `NOPASSWD: /bin/cp` | `scripts/install.sh:125` | Can overwrite any file as root |
| 3 | `sudo bash -c "curl ... \| bash"` pattern | All adapters + ssl_manager | Bypasses `create_subprocess_exec` safety |
| 4 | curl \| bash for Xray/Hysteria2/acme.sh | Multiple adapters | No checksum verification of downloaded scripts |
| 5 | `ENCRYPTION_KEY` printed to stdout | `scripts/install.sh:112` | May end up in shell history or CI logs |

### HIGH

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| 6 | Weak key derivation in SecretStore | `src/infrastructure/secret_store.py` | `_derive_key` pads with `b"0"`, not proper KDF |
| 7 | No `encryption_key` validation | `src/config.py` | Short key → weak Fernet key |
| 8 | REALITY private key in plaintext | Xray config JSON on disk | No additional encryption |
| 9 | SecretStore file has no permission enforcement | `src/infrastructure/secret_store.py` | No `chmod 600` on encrypted file |

### MEDIUM

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| 10 | `datetime.utcnow()` deprecated | Multiple files | Deprecated in Python 3.12 |
| 11 | RateLimiter memory leak | `src/infrastructure/rate_limiter.py` | `_requests` dict grows unboundedly |
| 12 | No input sanitization on client names | Adapters | Special characters written to configs |

---

## 5. Test Coverage

**22 tests total**, all passing. Coverage is limited to pure functions:

| Module | Tested | Not Tested |
|--------|--------|------------|
| Domain enums | ✅ | — |
| Domain capabilities | ✅ | — |
| Domain audit | ✅ (smoke) | — |
| VLESS config_writer | ✅ | — |
| VLESS link_generator | ✅ | — |
| Hysteria2 config_writer | ✅ | — |
| Hysteria2 link_generator | ✅ | — |
| MTProto link_generator | ✅ | — |
| Rate limiter | ✅ | — |
| Protocol adapters (all 3) | ❌ | install, detect, create_client, delete_client, health, backup |
| Shell runner | ❌ | Command execution, timeout, redaction |
| Secret store | ❌ | Encrypt/decrypt |
| SSL manager | ❌ | Cert generation, paths |
| Database repositories | ❌ | All CRUD operations |
| Telegram handlers | ❌ | Commands, callbacks, middleware |
| Services | ❌ | BackupService, HealthChecker, TrafficCollector |
| Updater | ❌ | Git-based update flow |

---

## 6. Database Schema

**6 tables, 3 indexes.** Applied via `CREATE TABLE IF NOT EXISTS` (no migration framework).

| Table | Purpose |
|-------|---------|
| `admins` | Admin whitelist (telegram_user_id) |
| `protocol_installations` | One row per protocol (status, port, config_path) |
| `clients` | Client records (protocol, external_name, status) |
| `client_credentials` | Credentials per client (uuid/password/secret) |
| `traffic_snapshots` | Traffic history |
| `audit_events` | Audit log |

**Issues:**
- No migration system — schema changes require manual ALTER TABLE
- All datetime columns stored as TEXT (ISO format)
- `client_credentials.uuid` column name misleading for non-VLESS protocols
- `AuditRepository` defined but never instantiated (audit goes to Python logging, not DB)
- Dead code in `TrafficRepository` (lines 256-265, unreachable)

---

## 7. Unused / Disconnected Components

| Component | Status |
|-----------|--------|
| `AuditRepository` | Defined in repositories.py, never wired to bot |
| `SecretStore` | Defined, never wired to bot |
| `HealthChecker` | Wired in bot.py, but `check_all()` never called on schedule |
| `TrafficCollector` | Wired in bot.py, but `collect_all()` never called on schedule |
| `Updater` | Defined, never wired to bot |
| `screens/main_menu.py` | Empty file |

---

## 8. Scripts State

| Script | Lines | Quality |
|--------|-------|---------|
| `install.sh` | 192 | Well-structured, `set -euo pipefail`, supports `--repo`/`--branch` |
| `update.sh` | 53 | Clean with rollback logic |
| `restore.sh` | 43 | Minimal, functional |

**Issues:**
- Excessive sudoers (see Security #1, #2)
- `ENCRYPTION_KEY` printed to stdout
- No `--force` or `--non-interactive` mode
- `update.sh` does not verify git remote/branch before pulling

---

## 9. Dependencies

`pyyaml` correctly listed in runtime `dependencies` (line 18 of pyproject.toml). Previous audit finding about it being dev-only was incorrect.

**Note:** Python 3.14.5 used for this audit (project requires >=3.11). All tests pass.

---

## 10. Summary: What Works vs What Doesn't

### Works (tested or verifiable)
- Lint, typecheck, tests all pass
- VLESS: full lifecycle (install → create client → link → delete → backup)
- Hysteria2: install, create client (shared password), link, backup
- MTProto: install (build from source), link, backup
- Telegram bot: commands, callbacks, auth, rate limiting, i18n
- Installer: interactive wizard, systemd setup

### Doesn't work / Broken
- Hysteria2/MTProto client deletion (stubs)
- Client list UI only shows VLESS clients
- HealthChecker/TrafficCollector never run on schedule
- Audit trail goes to logs, not DB
- SecretStore never used
- No migration system for schema changes

### Dangerous for production
- Unrestricted sudoers (`/bin/bash`, `/bin/cp`)
- curl | bash without checksums
- Secrets printed to stdout during install
- Weak key derivation in SecretStore
- REALITY private keys in plaintext on disk

---

## 11. Recommendations for Phase 1+

1. **Phase 1 (Installer):** Replace broad sudoers with narrow root helpers; stop printing secrets; add `.env.example`
2. **Phase 2 (VLESS):** Already mostly done — focus on making it robust (validation, rollback, traffic from persisted state)
3. **Phase 3 (Hysteria2):** Implement real per-client auth, fix `delete_client()`, fix client list UI
4. **Phase 4 (MTProto):** Implement `delete_client()`, decide on per-client vs shared model
5. **Phase 5 (Hardening):** Wire AuditRepository to DB, add scheduled health/traffic, migration system, expand test coverage
