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
                KeyboardButton(text=t(lang, "btn_status")),
            ],
            [
                KeyboardButton(text=t(lang, "btn_install_vless")),
                KeyboardButton(text=t(lang, "btn_install_hysteria2")),
                KeyboardButton(text=t(lang, "btn_install_mtproto")),
            ],
            [
                KeyboardButton(text=t(lang, "btn_clients")),
                KeyboardButton(text=t(lang, "btn_add_client")),
            ],
            [
                KeyboardButton(text=t(lang, "btn_delete_client")),
                KeyboardButton(text=t(lang, "btn_get_link")),
            ],
            [KeyboardButton(text=t(lang, "btn_help"))],
        ],
        resize_keyboard=True,
    )


def confirm_keyboard(lang: str | None = None) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=t(lang, "btn_confirm_yes")),
                KeyboardButton(text=t(lang, "btn_confirm_no")),
            ],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def back_keyboard(lang: str | None = None) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t(lang, "btn_back"))]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def port_selection_keyboard(
    protocol: str,
    lang: str | None = None,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="443",
                    callback_data=f"port:{protocol}:443",
                ),
                InlineKeyboardButton(
                    text="8443",
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
                    callback_data="menu:main",
                ),
            ],
        ]
    )
