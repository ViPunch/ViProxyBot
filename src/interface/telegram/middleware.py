from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from src.database.repositories import AdminRepository
from src.domain.audit import AuditAction, AuditLogger
from src.domain.exceptions import UnauthorizedError
from src.infrastructure.rate_limiter import RateLimiter
from src.interface.telegram.i18n import t


class AuthMiddleware(BaseMiddleware):
    def __init__(self, admin_repository: AdminRepository) -> None:
        self.admin_repository = admin_repository

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user_id = self._extract_user_id(event)
        lang = self._extract_language(event)
        data["lang"] = lang
        if user_id is None or not await self.admin_repository.is_admin(user_id):
            await self._reject(event, lang)
            raise UnauthorizedError("Unauthorized")
        return await handler(event, data)

    @staticmethod
    def _extract_user_id(event: TelegramObject) -> int | None:
        if isinstance(event, Message) and event.from_user:
            return event.from_user.id
        if isinstance(event, CallbackQuery) and event.from_user:
            return event.from_user.id
        return None

    @staticmethod
    def _extract_language(event: TelegramObject) -> str | None:
        if isinstance(event, Message) and event.from_user:
            return event.from_user.language_code
        if isinstance(event, CallbackQuery) and event.from_user:
            return event.from_user.language_code
        return None

    @staticmethod
    async def _reject(
        event: TelegramObject,
        lang: str | None,
    ) -> None:
        message = t(lang, "access_denied")
        if isinstance(event, Message):
            await event.answer(message)
        elif isinstance(event, CallbackQuery):
            await event.answer(message)


class RateLimitMiddleware(BaseMiddleware):
    def __init__(
        self,
        rate_limiter: RateLimiter,
        audit_logger: AuditLogger,
    ) -> None:
        self.rate_limiter = rate_limiter
        self.audit_logger = audit_logger

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user_id = self._extract_user_id(event)
        if user_id is None:
            return await handler(event, data)

        action = self._detect_action(event)
        if not self.rate_limiter.check(user_id, action):
            lang = data.get("lang")
            self.audit_logger.log(
                actor_id=user_id,
                action=AuditAction.RATE_LIMIT_HIT,
                target_type="user",
                target_id=str(user_id),
                status="blocked",
                details=action,
            )
            msg = t(lang, "unexpected_input")
            if isinstance(event, Message):
                await event.answer(msg)
            elif isinstance(event, CallbackQuery):
                await event.answer(msg)
            return

        return await handler(event, data)

    @staticmethod
    def _extract_user_id(event: TelegramObject) -> int | None:
        if isinstance(event, Message) and event.from_user:
            return event.from_user.id
        if isinstance(event, CallbackQuery) and event.from_user:
            return event.from_user.id
        return None

    @staticmethod
    def _detect_action(event: TelegramObject) -> str:
        if isinstance(event, Message) and event.text and event.text.startswith("/"):
            return "command"
        if isinstance(event, CallbackQuery):
            return "callback"
        return "message"
