from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from src.interface.telegram.i18n import t


def main_menu_keyboard(lang: str | None = None) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=t(lang, "btn_install")),
                KeyboardButton(text=t(lang, "btn_clients")),
            ],
            [
                KeyboardButton(text=t(lang, "btn_monitoring")),
                KeyboardButton(text=t(lang, "btn_help")),
            ],
        ],
        resize_keyboard=True,
    )


def install_screen_keyboard(
    statuses: dict[str, tuple[bool, int | None]],
    lang: str | None = None,
) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = []
    for protocol in ("vless", "hysteria2", "mtproto"):
        installed, port = statuses.get(protocol, (False, None))
        if installed:
            status_text = t(
                lang, "protocol_installed", port=port or "?"
            )
            buttons.append([
                InlineKeyboardButton(
                    text=f"{protocol.upper()} {status_text}",
                    callback_data="noop",
                ),
            ])
        else:
            buttons.append([
                InlineKeyboardButton(
                    text=f"{protocol.upper()} {t(lang, 'protocol_not_installed')}",
                    callback_data="noop",
                ),
                InlineKeyboardButton(
                    text=t(lang, "btn_install_protocol"),
                    callback_data=f"install:{protocol}",
                ),
            ])
    buttons.append([
        InlineKeyboardButton(
            text=t(lang, "btn_back"),
            callback_data="menu:main",
        ),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def port_selection_keyboard(
    protocol: str,
    lang: str | None = None,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t(lang, "btn_port_443"),
                    callback_data=f"port:{protocol}:443",
                ),
                InlineKeyboardButton(
                    text=t(lang, "btn_port_8443"),
                    callback_data=f"port:{protocol}:8443",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=t(lang, "btn_custom_port"),
                    callback_data=f"port:{protocol}:custom",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=t(lang, "btn_back"),
                    callback_data="menu:install",
                ),
            ],
        ]
    )


def client_protocol_keyboard(
    lang: str | None = None,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="VLESS",
                    callback_data="clients:vless",
                ),
                InlineKeyboardButton(
                    text="Hysteria2",
                    callback_data="clients:hysteria2",
                ),
                InlineKeyboardButton(
                    text="MTProto",
                    callback_data="clients:mtproto",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=t(lang, "btn_back"),
                    callback_data="menu:main",
                ),
            ],
        ]
    )


def client_list_keyboard(
    protocol: str,
    clients: list[str],
    lang: str | None = None,
) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = []
    for client_name in clients:
        buttons.append([
            InlineKeyboardButton(
                text=client_name,
                callback_data=f"getlink:{protocol}:{client_name}",
            ),
        ])
    buttons.append([
        InlineKeyboardButton(
            text=t(lang, "btn_add_client"),
            callback_data=f"addclient:{protocol}",
        ),
        InlineKeyboardButton(
            text=t(lang, "btn_delete_client"),
            callback_data=f"delselect:{protocol}",
        ),
    ])
    buttons.append([
        InlineKeyboardButton(
            text=t(lang, "btn_back"),
            callback_data="menu:clients",
        ),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def client_select_keyboard(
    protocol: str,
    clients: list[str],
    action: str,
    lang: str | None = None,
) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = []
    for client_name in clients:
        buttons.append([
            InlineKeyboardButton(
                text=client_name,
                callback_data=f"{action}:{protocol}:{client_name}",
            ),
        ])
    buttons.append([
        InlineKeyboardButton(
            text=t(lang, "btn_back"),
            callback_data=f"clients:{protocol}",
        ),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_keyboard(
    protocol: str,
    client_name: str,
    lang: str | None = None,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t(lang, "btn_confirm_yes"),
                    callback_data=f"confirmdel:{protocol}:{client_name}:yes",
                ),
                InlineKeyboardButton(
                    text=t(lang, "btn_confirm_no"),
                    callback_data=f"clients:{protocol}",
                ),
            ],
        ]
    )


def back_inline_keyboard(
    callback_data: str,
    lang: str | None = None,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t(lang, "btn_back"),
                    callback_data=callback_data,
                ),
            ],
        ]
    )
