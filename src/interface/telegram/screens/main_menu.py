from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.domain.capability import get_capabilities
from src.domain.enums import ProtocolType
from src.interface.telegram.i18n import t


def main_menu_inline_keyboard(
    lang: str | None = None,
) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text="VLESS",
                callback_data="protocol:vless",
            ),
            InlineKeyboardButton(
                text="Hysteria2",
                callback_data="protocol:hysteria2",
            ),
        ],
        [
            InlineKeyboardButton(
                text="MTProto",
                callback_data="protocol:mtproto",
            ),
        ],
        [
            InlineKeyboardButton(
                text=t(lang, "btn_status"),
                callback_data="status:all",
            ),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def protocol_screen_keyboard(
    protocol: ProtocolType,
    lang: str | None = None,
) -> InlineKeyboardMarkup:
    caps = get_capabilities(protocol)
    buttons: list[list[InlineKeyboardButton]] = []

    if caps.supports_individual_clients:
        buttons.append([
            InlineKeyboardButton(
                text=t(lang, "btn_clients"),
                callback_data=f"clients:{protocol.value}",
            ),
            InlineKeyboardButton(
                text=t(lang, "btn_add_client"),
                callback_data=f"addclient:{protocol.value}",
            ),
        ])
        buttons.append([
            InlineKeyboardButton(
                text=t(lang, "btn_get_link"),
                callback_data=f"getlink:{protocol.value}",
            ),
            InlineKeyboardButton(
                text=t(lang, "btn_delete_client"),
                callback_data=f"delclient:{protocol.value}",
            ),
        ])

    if caps.supports_per_client_traffic or caps.supports_aggregate_traffic:
        buttons.append([
            InlineKeyboardButton(
                text="Traffic",
                callback_data=f"traffic:{protocol.value}",
            ),
        ])

    buttons.append([
        InlineKeyboardButton(
            text=t(lang, "btn_back"),
            callback_data="menu:main",
        ),
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def clients_inline_keyboard(
    clients: list[str],
    protocol: str,
    lang: str | None = None,
) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text=name,
                callback_data=f"getlink:{protocol}:{name}",
            ),
        ]
        for name in clients
    ]
    buttons.append([
        InlineKeyboardButton(
            text=t(lang, "btn_back"),
            callback_data=f"protocol:{protocol}",
        ),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_inline_keyboard(
    action: str,
    target: str,
    lang: str | None = None,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t(lang, "btn_confirm_yes"),
                    callback_data=f"confirm:{action}:{target}:yes",
                ),
                InlineKeyboardButton(
                    text=t(lang, "btn_confirm_no"),
                    callback_data=f"confirm:{action}:{target}:no",
                ),
            ],
        ]
    )
