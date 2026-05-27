from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from src.config import AppConfig
from src.database.connection import get_connection, set_db_path
from src.database.repositories import (
    AdminRepository,
    TrafficRepository,
)
from src.database.schema import apply_schema
from src.domain.audit import AuditLogger
from src.domain.enums import ProtocolType
from src.infrastructure.alerting import AlertDispatcher, TelegramAlertHandler
from src.infrastructure.protocols.hysteria2.adapter import Hysteria2Adapter
from src.infrastructure.protocols.mtproto.adapter import MtprotoAdapter
from src.infrastructure.protocols.vless.adapter import VlessAdapter
from src.infrastructure.rate_limiter import RateLimiter
from src.interface.telegram.callback_router import (
    router as callback_router,
)
from src.interface.telegram.commands import router as commands_router
from src.interface.telegram.middleware import (
    AuthMiddleware,
    RateLimitMiddleware,
)
from src.services.backup_service import BackupService
from src.services.health_checker import HealthChecker
from src.services.protocol_registry import ProtocolRegistry
from src.services.traffic_collector import TrafficCollector


async def create_bot(config: AppConfig) -> tuple[Bot, Dispatcher]:
    set_db_path(config.db_path)
    conn = await get_connection()
    await apply_schema(conn)

    admin_repository = AdminRepository(conn)
    for admin_id in config.admin_ids:
        await admin_repository.upsert_admin(admin_id)

    registry = ProtocolRegistry()

    vless_adapter = VlessAdapter(
        config_path=config.xray_config_dir / "config.json",
        backups_dir=config.backups_dir,
        public_host=config.vps_public_ip,
    )
    registry.register(ProtocolType.VLESS, vless_adapter)

    hysteria2_adapter = Hysteria2Adapter(
        config_path=config.xray_config_dir / "hysteria.yaml",
        backups_dir=config.backups_dir,
        public_host=config.vps_public_ip,
    )
    registry.register(ProtocolType.HYSTERIA2, hysteria2_adapter)

    mtproto_adapter = MtprotoAdapter(
        config_dir=config.xray_config_dir / "mtproto",
        backups_dir=config.backups_dir,
        public_host=config.vps_public_ip,
    )
    registry.register(ProtocolType.MTPROTO, mtproto_adapter)

    traffic_repo = TrafficRepository(conn)
    traffic_collector = TrafficCollector(registry, traffic_repo)

    backup_service = BackupService(
        registry=registry,
        backups_dir=config.backups_dir,
        db_path=config.db_path,
    )

    rate_limiter = RateLimiter()
    rate_limiter.configure(
        "command",
        max_requests=config.rate_limit_commands,
        window_seconds=config.rate_limit_window,
    )
    rate_limiter.configure(
        "callback",
        max_requests=config.rate_limit_commands,
        window_seconds=config.rate_limit_window,
    )
    rate_limiter.configure(
        "message",
        max_requests=config.rate_limit_heavy_ops,
        window_seconds=config.rate_limit_window,
    )

    audit_logger = AuditLogger()

    alert_dispatcher = AlertDispatcher()

    health_checker = HealthChecker(
        registry=registry,
        alert_dispatcher=alert_dispatcher,
    )

    bot = Bot(token=config.bot_token)

    if config.alert_chat_ids:
        telegram_handler = TelegramAlertHandler(
            bot=bot,
            admin_chat_ids=config.alert_chat_ids,
        )
        alert_dispatcher.register_handler(telegram_handler)

    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.message.middleware(AuthMiddleware(admin_repository))
    dispatcher.message.middleware(
        RateLimitMiddleware(rate_limiter, audit_logger)
    )
    dispatcher.callback_query.middleware(AuthMiddleware(admin_repository))
    dispatcher.callback_query.middleware(
        RateLimitMiddleware(rate_limiter, audit_logger)
    )
    dispatcher.include_router(commands_router)
    dispatcher.include_router(callback_router)
    dispatcher["db_connection"] = conn
    dispatcher["protocol_registry"] = registry
    dispatcher["traffic_collector"] = traffic_collector
    dispatcher["backup_service"] = backup_service
    dispatcher["health_checker"] = health_checker
    dispatcher["audit_logger"] = audit_logger
    dispatcher["alert_dispatcher"] = alert_dispatcher
    return bot, dispatcher


async def run_bot(config: AppConfig) -> None:
    bot, dispatcher = await create_bot(config)
    await dispatcher.start_polling(bot)
