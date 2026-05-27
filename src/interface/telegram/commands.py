from __future__ import annotations

import logging
from typing import Optional

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from src.domain.enums import ProtocolType
from src.domain.exceptions import (
    ClientAlreadyExistsError,
    ClientNotFoundError,
    ServiceReloadError,
)
from src.infrastructure.protocols.vless.config_writer import (
    get_clients_from_config,
    load_config,
)
from src.interface.telegram.i18n import t
from src.interface.telegram.keyboards import (
    back_keyboard,
    confirm_keyboard,
    main_menu_keyboard,
)
from src.services.protocol_registry import ProtocolRegistry

logger = logging.getLogger(__name__)

router = Router()


class MenuStates(StatesGroup):
    idle = State()
    ask_port = State()
    ask_port_hysteria2 = State()
    ask_port_mtproto = State()
    ask_client_name = State()
    ask_delete_client_name = State()
    confirm_delete = State()
    ask_link_client_name = State()


@router.message(Command("start"))
async def start_command(
    message: Message,
    lang: str | None = None,
    state: Optional[FSMContext] = None,
) -> None:
    await state.set_state(MenuStates.idle)
    await message.answer(
        t(lang, "bot_ready"),
        reply_markup=main_menu_keyboard(lang),
    )


@router.message(Command("menu"))
async def menu_command(
    message: Message,
    lang: str | None = None,
    state: Optional[FSMContext] = None,
) -> None:
    await state.set_state(MenuStates.idle)
    await message.answer(
        t(lang, "main_menu"),
        reply_markup=main_menu_keyboard(lang),
    )


@router.message(Command("status"))
async def status_command(
    message: Message,
    lang: str | None = None,
    protocol_registry: Optional[ProtocolRegistry] = None,
) -> None:
    adapter = protocol_registry.get(ProtocolType.VLESS)
    if adapter is None:
        await message.answer(t(lang, "status_not_implemented"))
        return
    health = await adapter.health()
    if health.healthy:
        await message.answer(
            f"{t(lang, 'status_header')}\n{t(lang, 'status_healthy')}"
        )
    else:
        await message.answer(
            f"{t(lang, 'status_header')}\n"
            f"{t(lang, 'status_unhealthy', message=health.message)}"
        )


@router.message(Command("help"))
async def help_command(
    message: Message,
    lang: str | None = None,
) -> None:
    await message.answer(t(lang, "help_text"))


# --- Idle state: menu button routing ---


@router.message(MenuStates.idle)
async def idle_handler(
    message: Message,
    lang: str | None = None,
    state: Optional[FSMContext] = None,
    protocol_registry: Optional[ProtocolRegistry] = None,
) -> None:
    text = (message.text or "").strip()

    if text == t(lang, "btn_install_vless"):
        await state.set_state(MenuStates.ask_port)
        await message.answer(
            t(lang, "ask_port"),
            reply_markup=back_keyboard(lang),
        )

    elif text == t(lang, "btn_install_hysteria2"):
        await state.set_state(MenuStates.ask_port_hysteria2)
        await message.answer(
            t(lang, "ask_port_hysteria2"),
            reply_markup=back_keyboard(lang),
        )

    elif text == t(lang, "btn_install_mtproto"):
        await state.set_state(MenuStates.ask_port_mtproto)
        await message.answer(
            t(lang, "ask_port_mtproto"),
            reply_markup=back_keyboard(lang),
        )

    elif text == t(lang, "btn_clients"):
        await _handle_clients(message, lang, protocol_registry)

    elif text == t(lang, "btn_add_client"):
        await state.set_state(MenuStates.ask_client_name)
        await message.answer(
            t(lang, "ask_client_name"),
            reply_markup=back_keyboard(lang),
        )

    elif text == t(lang, "btn_delete_client"):
        await state.set_state(MenuStates.ask_delete_client_name)
        await message.answer(
            t(lang, "ask_delete_client_name"),
            reply_markup=back_keyboard(lang),
        )

    elif text == t(lang, "btn_get_link"):
        await state.set_state(MenuStates.ask_link_client_name)
        await message.answer(
            t(lang, "ask_link_client_name"),
            reply_markup=back_keyboard(lang),
        )

    elif text == t(lang, "btn_status"):
        await status_command(message, lang, protocol_registry)

    elif text == t(lang, "btn_help"):
        await help_command(message, lang)

    else:
        await message.answer(t(lang, "unexpected_input"))


# --- Install VLESS: port input ---


@router.message(MenuStates.ask_port)
async def port_input_handler(
    message: Message,
    lang: str | None = None,
    state: Optional[FSMContext] = None,
    protocol_registry: Optional[ProtocolRegistry] = None,
) -> None:
    text = (message.text or "").strip()

    if text == t(lang, "btn_back"):
        await state.set_state(MenuStates.idle)
        await message.answer(
            t(lang, "main_menu"),
            reply_markup=main_menu_keyboard(lang),
        )
        return

    try:
        port = int(text)
    except ValueError:
        await message.answer(
            t(lang, "ask_port"),
            reply_markup=back_keyboard(lang),
        )
        return

    if port < 1 or port > 65535:
        await message.answer(
            t(lang, "ask_port"),
            reply_markup=back_keyboard(lang),
        )
        return

    adapter = _get_vless_adapter(protocol_registry, lang, message)
    if adapter is None:
        await state.set_state(MenuStates.idle)
        return

    try:
        result = await adapter.install(port, adapter.public_host)
        await state.set_state(MenuStates.idle)
        await message.answer(
            t(lang, "install_success", port=result.listen_port),
            reply_markup=main_menu_keyboard(lang),
        )
    except Exception as exc:
        logger.exception("VLESS install failed")
        await state.set_state(MenuStates.idle)
        await message.answer(
            t(lang, "install_error", error=str(exc)),
            reply_markup=main_menu_keyboard(lang),
        )


# --- Install Hysteria2: port input ---


@router.message(MenuStates.ask_port_hysteria2)
async def port_input_hysteria2_handler(
    message: Message,
    lang: str | None = None,
    state: Optional[FSMContext] = None,
    protocol_registry: Optional[ProtocolRegistry] = None,
) -> None:
    text = (message.text or "").strip()

    if text == t(lang, "btn_back"):
        await state.set_state(MenuStates.idle)
        await message.answer(
            t(lang, "main_menu"),
            reply_markup=main_menu_keyboard(lang),
        )
        return

    try:
        port = int(text)
    except ValueError:
        await message.answer(
            t(lang, "ask_port_hysteria2"),
            reply_markup=back_keyboard(lang),
        )
        return

    if port < 1 or port > 65535:
        await message.answer(
            t(lang, "ask_port_hysteria2"),
            reply_markup=back_keyboard(lang),
        )
        return

    adapter = (
        protocol_registry.get(ProtocolType.HYSTERIA2)
        if protocol_registry
        else None
    )
    if adapter is None:
        await state.set_state(MenuStates.idle)
        await message.answer(
            t(lang, "main_menu"),
            reply_markup=main_menu_keyboard(lang),
        )
        return

    try:
        result = await adapter.install(port, adapter.public_host)
        await state.set_state(MenuStates.idle)
        await message.answer(
            t(lang, "install_hysteria2_success", port=result.listen_port),
            reply_markup=main_menu_keyboard(lang),
        )
    except Exception as exc:
        logger.exception("Hysteria2 install failed")
        await state.set_state(MenuStates.idle)
        await message.answer(
            t(lang, "install_hysteria2_error", error=str(exc)),
            reply_markup=main_menu_keyboard(lang),
        )


# --- Install MTProto: port input ---


@router.message(MenuStates.ask_port_mtproto)
async def port_input_mtproto_handler(
    message: Message,
    lang: str | None = None,
    state: Optional[FSMContext] = None,
    protocol_registry: Optional[ProtocolRegistry] = None,
) -> None:
    text = (message.text or "").strip()

    if text == t(lang, "btn_back"):
        await state.set_state(MenuStates.idle)
        await message.answer(
            t(lang, "main_menu"),
            reply_markup=main_menu_keyboard(lang),
        )
        return

    try:
        port = int(text)
    except ValueError:
        await message.answer(
            t(lang, "ask_port_mtproto"),
            reply_markup=back_keyboard(lang),
        )
        return

    if port < 1 or port > 65535:
        await message.answer(
            t(lang, "ask_port_mtproto"),
            reply_markup=back_keyboard(lang),
        )
        return

    adapter = (
        protocol_registry.get(ProtocolType.MTPROTO)
        if protocol_registry
        else None
    )
    if adapter is None:
        await state.set_state(MenuStates.idle)
        await message.answer(
            t(lang, "main_menu"),
            reply_markup=main_menu_keyboard(lang),
        )
        return

    try:
        result = await adapter.install(port, adapter.public_host)
        await state.set_state(MenuStates.idle)
        await message.answer(
            t(lang, "install_mtproto_success", port=result.listen_port),
            reply_markup=main_menu_keyboard(lang),
        )
    except Exception as exc:
        logger.exception("MTProto install failed")
        await state.set_state(MenuStates.idle)
        await message.answer(
            t(lang, "install_mtproto_error", error=str(exc)),
            reply_markup=main_menu_keyboard(lang),
        )


# --- Add client: name input ---


@router.message(MenuStates.ask_client_name)
async def client_name_input_handler(
    message: Message,
    lang: str | None = None,
    state: Optional[FSMContext] = None,
    protocol_registry: Optional[ProtocolRegistry] = None,
) -> None:
    text = (message.text or "").strip()

    if text == t(lang, "btn_back"):
        await state.set_state(MenuStates.idle)
        await message.answer(
            t(lang, "main_menu"),
            reply_markup=main_menu_keyboard(lang),
        )
        return

    adapter = _get_vless_adapter(protocol_registry, lang, message)
    if adapter is None:
        await state.set_state(MenuStates.idle)
        return

    try:
        credential, label = await adapter.create_client(text)
        link = adapter.generate_link(label)
        await state.set_state(MenuStates.idle)
        await message.answer(
            t(lang, "client_created", link=link),
            reply_markup=main_menu_keyboard(lang),
        )
    except (ClientAlreadyExistsError, ServiceReloadError) as exc:
        await state.set_state(MenuStates.idle)
        await message.answer(
            t(lang, "client_create_error", error=str(exc)),
            reply_markup=main_menu_keyboard(lang),
        )
    except Exception as exc:
        logger.exception("Client creation failed")
        await state.set_state(MenuStates.idle)
        await message.answer(
            t(lang, "client_create_error", error=str(exc)),
            reply_markup=main_menu_keyboard(lang),
        )


# --- Delete client: name input ---


@router.message(MenuStates.ask_delete_client_name)
async def delete_client_name_handler(
    message: Message,
    lang: str | None = None,
    state: Optional[FSMContext] = None,
) -> None:
    text = (message.text or "").strip()

    if text == t(lang, "btn_back"):
        await state.set_state(MenuStates.idle)
        await message.answer(
            t(lang, "main_menu"),
            reply_markup=main_menu_keyboard(lang),
        )
        return

    await state.update_data(delete_client_name=text)
    await state.set_state(MenuStates.confirm_delete)
    await message.answer(
        t(lang, "ask_confirm_delete", name=text),
        reply_markup=confirm_keyboard(lang),
    )


# --- Delete client: confirmation ---


@router.message(MenuStates.confirm_delete)
async def confirm_delete_handler(
    message: Message,
    lang: str | None = None,
    state: Optional[FSMContext] = None,
    protocol_registry: Optional[ProtocolRegistry] = None,
) -> None:
    text = (message.text or "").strip()

    if text == t(lang, "btn_confirm_no"):
        await state.set_state(MenuStates.idle)
        await message.answer(
            t(lang, "delete_cancelled"),
            reply_markup=main_menu_keyboard(lang),
        )
        return

    if text != t(lang, "btn_confirm_yes"):
        await message.answer(
            t(lang, "ask_confirm_delete", name=""),
            reply_markup=confirm_keyboard(lang),
        )
        return

    data = await state.get_data()
    client_name = data.get("delete_client_name", "")

    adapter = _get_vless_adapter(protocol_registry, lang, message)
    if adapter is None:
        await state.set_state(MenuStates.idle)
        return

    try:
        await adapter.delete_client(client_name)
        await state.set_state(MenuStates.idle)
        await message.answer(
            t(lang, "client_deleted", name=client_name),
            reply_markup=main_menu_keyboard(lang),
        )
    except (ClientNotFoundError, ServiceReloadError) as exc:
        await state.set_state(MenuStates.idle)
        await message.answer(
            t(lang, "client_delete_error", error=str(exc)),
            reply_markup=main_menu_keyboard(lang),
        )
    except Exception as exc:
        logger.exception("Client deletion failed")
        await state.set_state(MenuStates.idle)
        await message.answer(
            t(lang, "client_delete_error", error=str(exc)),
            reply_markup=main_menu_keyboard(lang),
        )


# --- Get link: client name input ---


@router.message(MenuStates.ask_link_client_name)
async def link_client_name_handler(
    message: Message,
    lang: str | None = None,
    state: Optional[FSMContext] = None,
    protocol_registry: Optional[ProtocolRegistry] = None,
) -> None:
    text = (message.text or "").strip()

    if text == t(lang, "btn_back"):
        await state.set_state(MenuStates.idle)
        await message.answer(
            t(lang, "main_menu"),
            reply_markup=main_menu_keyboard(lang),
        )
        return

    adapter = _get_vless_adapter(protocol_registry, lang, message)
    if adapter is None:
        await state.set_state(MenuStates.idle)
        return

    try:
        link = adapter.generate_link(text)
        await state.set_state(MenuStates.idle)
        await message.answer(
            t(lang, "client_link", name=text, link=link),
            reply_markup=main_menu_keyboard(lang),
        )
    except ClientNotFoundError as exc:
        await state.set_state(MenuStates.idle)
        await message.answer(
            t(lang, "client_link_error", error=str(exc)),
            reply_markup=main_menu_keyboard(lang),
        )
    except Exception as exc:
        logger.exception("Get link failed")
        await state.set_state(MenuStates.idle)
        await message.answer(
            t(lang, "client_link_error", error=str(exc)),
            reply_markup=main_menu_keyboard(lang),
        )


# --- Clients list ---


async def _handle_clients(
    message: Message,
    lang: str | None = None,
    protocol_registry: Optional[ProtocolRegistry] = None,
) -> None:
    adapter = _get_vless_adapter(protocol_registry, lang, message)
    if adapter is None:
        return
    clients = get_clients_from_config(load_config(adapter.config_path))
    if not clients:
        await message.answer(t(lang, "clients_empty"))
        return
    lines = [t(lang, "clients_header")]
    for client in clients:
        lines.append(f"  • {client.get('email', '?')}")
    await message.answer("\n".join(lines))


# --- Helpers ---


def _get_vless_adapter(
    protocol_registry: Optional[ProtocolRegistry],
    lang: str | None,
    message: Message,
):
    if protocol_registry is None:
        return None
    adapter = protocol_registry.get(ProtocolType.VLESS)
    if adapter is None:
        return None
    return adapter
