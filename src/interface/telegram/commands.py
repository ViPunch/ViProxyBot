from __future__ import annotations

import logging
from typing import Optional

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from src.domain.enums import ProtocolType
from src.interface.telegram.i18n import t
from src.interface.telegram.keyboards import (
    main_menu_keyboard,
)
from src.services.protocol_registry import ProtocolRegistry

logger = logging.getLogger(__name__)

router = Router()


class MenuStates(StatesGroup):
    idle = State()
    ask_domain = State()
    ask_custom_port = State()
    ask_client_name = State()
    ask_ssl_domain = State()
    ask_custom_sni = State()


@router.message(Command("start"))
async def start_command(
    message: Message,
    lang: str | None = None,
    state: Optional[FSMContext] = None,
) -> None:
    await state.set_state(None)
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
    await state.set_state(None)
    await message.answer(
        t(lang, "main_menu"),
        reply_markup=main_menu_keyboard(lang),
    )


@router.message(Command("help"))
async def help_command(
    message: Message,
    lang: str | None = None,
) -> None:
    await message.answer(t(lang, "help_text"))


# --- Reply keyboard button routing ---


@router.message()
async def message_handler(
    message: Message,
    lang: str | None = None,
    state: Optional[FSMContext] = None,
    protocol_registry: Optional[ProtocolRegistry] = None,
) -> None:
    text = (message.text or "").strip()
    current_state = await state.get_state() if state else None

    # Handle custom SNI input
    if current_state == "MenuStates:ask_custom_sni":
        await _handle_custom_sni(message, lang, state)
        return

    # Handle custom port input
    if current_state == "MenuStates:ask_custom_port":
        await _handle_custom_port(message, lang, state, protocol_registry)
        return

    # Handle custom domain input
    if current_state == "MenuStates:ask_domain":
        await _handle_custom_domain(message, lang, state, protocol_registry)
        return

    # Handle SSL domain input
    if current_state == "MenuStates:ask_ssl_domain":
        await _handle_ssl_domain(message, lang, state, protocol_registry)
        return

    # Handle client name input
    if current_state == "MenuStates:ask_client_name":
        await _handle_client_name(message, lang, state, protocol_registry)
        return

    # Handle reply keyboard buttons
    if text == t(lang, "btn_install"):
        await state.set_state(None)
        await message.answer(
            t(lang, "install_screen_title"),
            reply_markup=await _build_install_keyboard(lang, protocol_registry),
        )
        return

    if text == t(lang, "btn_clients"):
        from src.interface.telegram.keyboards import client_protocol_keyboard

        await state.set_state(None)
        await message.answer(
            t(lang, "clients_screen_title"),
            reply_markup=client_protocol_keyboard(lang),
        )
        return

    if text == t(lang, "btn_monitoring"):
        await state.set_state(None)
        await _show_monitoring(message, lang, protocol_registry)
        return

    if text == t(lang, "btn_help"):
        await message.answer(t(lang, "help_text"))
        return

    await message.answer(t(lang, "unexpected_input"))


async def _handle_custom_domain(
    message: Message,
    lang: str | None,
    state: Optional[FSMContext],
    protocol_registry: Optional[ProtocolRegistry],
) -> None:
    text = (message.text or "").strip()

    if text == t(lang, "btn_back"):
        await state.set_state(None)
        await message.answer(
            t(lang, "install_screen_title"),
            reply_markup=await _build_install_keyboard(lang, protocol_registry),
        )
        return

    domain = text.strip()
    if not domain:
        await message.answer(t(lang, "ask_custom_domain"))
        return

    data = await state.get_data()
    protocol_name = data.get("install_protocol", "vless")

    await state.set_state(MenuStates.ask_custom_port)
    await state.update_data(install_domain=domain)

    from src.interface.telegram.keyboards import port_selection_keyboard

    await message.answer(
        t(lang, "ask_port", protocol=protocol_name.upper()),
        reply_markup=port_selection_keyboard(protocol_name, lang),
    )


async def _handle_ssl_domain(
    message: Message,
    lang: str | None,
    state: Optional[FSMContext],
    protocol_registry: Optional[ProtocolRegistry],
) -> None:
    text = (message.text or "").strip()

    if text == t(lang, "btn_back"):
        await state.set_state(None)
        await message.answer(
            t(lang, "install_screen_title"),
            reply_markup=await _build_install_keyboard(lang, protocol_registry),
        )
        return

    ssl_domain = text.strip()
    if not ssl_domain:
        await message.answer(t(lang, "ask_ssl_domain"))
        return

    data = await state.get_data()
    protocol_name = data.get("install_protocol", "hysteria2")

    await state.set_state(MenuStates.ask_custom_port)
    await state.update_data(install_ssl_domain=ssl_domain)

    from src.interface.telegram.keyboards import port_selection_keyboard

    await message.answer(
        t(lang, "ask_port", protocol=protocol_name.upper()),
        reply_markup=port_selection_keyboard(protocol_name, lang),
    )


async def _handle_custom_sni(
    message: Message,
    lang: str | None,
    state: Optional[FSMContext],
) -> None:
    text = (message.text or "").strip()

    if text == t(lang, "btn_back"):
        await state.set_state(None)
        from src.interface.telegram.keyboards import vless_sni_keyboard

        await message.answer(
            t(lang, "vless_step_sni"),
            reply_markup=vless_sni_keyboard(lang),
        )
        return

    sni = text.strip()
    if not sni:
        await message.answer(t(lang, "ask_custom_sni"))
        return

    await state.set_state(None)
    await state.update_data(vless_sni=sni)

    from src.interface.telegram.keyboards import vless_transport_keyboard

    await message.answer(
        t(lang, "vless_step_transport"),
        reply_markup=vless_transport_keyboard(lang),
    )


async def _handle_custom_port(
    message: Message,
    lang: str | None,
    state: Optional[FSMContext],
    protocol_registry: Optional[ProtocolRegistry],
) -> None:
    text = (message.text or "").strip()

    if text == t(lang, "btn_back"):
        await state.set_state(None)
        await message.answer(
            t(lang, "install_screen_title"),
            reply_markup=await _build_install_keyboard(lang, protocol_registry),
        )
        return

    try:
        port = int(text)
    except ValueError:
        await message.answer(t(lang, "ask_custom_port"))
        return

    if port < 1 or port > 65535:
        await message.answer(t(lang, "ask_custom_port"))
        return

    data = await state.get_data()
    protocol_name = data.get("install_protocol", "vless")

    try:
        protocol = ProtocolType(protocol_name)
    except ValueError:
        await state.set_state(None)
        return

    adapter = (
        protocol_registry.get(protocol) if protocol_registry else None
    )
    if adapter is None:
        await state.set_state(None)
        return

    await state.set_state(None)
    try:
        result = await adapter.install(
            port, getattr(adapter, "public_host", "")
        )
        await message.answer(
            t(
                lang,
                "install_success",
                protocol=protocol.value.upper(),
                port=result.listen_port,
            ),
            reply_markup=await _build_install_keyboard(lang, protocol_registry),
        )
    except Exception as exc:
        logger.exception("Install failed")
        await message.answer(
            t(
                lang,
                "install_error",
                protocol=protocol.value.upper(),
                error=str(exc),
            ),
            reply_markup=await _build_install_keyboard(lang, protocol_registry),
        )


async def _handle_client_name(
    message: Message,
    lang: str | None,
    state: Optional[FSMContext],
    protocol_registry: Optional[ProtocolRegistry],
) -> None:
    text = (message.text or "").strip()

    if text == t(lang, "btn_back"):
        await state.set_state(None)
        from src.interface.telegram.keyboards import client_protocol_keyboard

        await message.answer(
            t(lang, "clients_screen_title"),
            reply_markup=client_protocol_keyboard(lang),
        )
        return

    data = await state.get_data()
    protocol_name = data.get("add_client_protocol", "vless")

    try:
        protocol = ProtocolType(protocol_name)
    except ValueError:
        await state.set_state(None)
        return

    adapter = (
        protocol_registry.get(protocol) if protocol_registry else None
    )
    if adapter is None:
        await state.set_state(None)
        return

    await state.set_state(None)

    # Check if protocol is installed before creating client
    detect = getattr(adapter, "detect", None)
    if detect:
        status = await detect()
        from src.domain.enums import ProtocolStatus

        if status == ProtocolStatus.NOT_INSTALLED:
            await message.answer(
                t(lang, "protocol_not_installed_warning",
                  protocol=protocol_name.upper()),
            )
            return

    try:
        credential, label = await adapter.create_client(text)
        generate_link = getattr(adapter, "generate_link", None)
        link = generate_link(label) if generate_link else "N/A"
        from src.interface.telegram.keyboards import client_list_keyboard

        clients = _get_client_names(adapter)
        await message.answer(
            t(lang, "client_created", name=text, link=link),
            reply_markup=client_list_keyboard(
                protocol_name, clients, lang
            ),
        )
    except Exception as exc:
        logger.exception("Client creation failed")
        await message.answer(
            t(lang, "client_create_error", error=str(exc)),
        )


async def _show_monitoring(
    message: Message,
    lang: str | None,
    protocol_registry: Optional[ProtocolRegistry],
) -> None:
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    lines = [t(lang, "monitoring_title"), "", t(lang, "status_header")]

    if protocol_registry:
        for protocol_type in ProtocolType:
            adapter = protocol_registry.get(protocol_type)
            if adapter is None:
                lines.append(
                    t(
                        lang,
                        "status_line",
                        protocol=protocol_type.value.upper(),
                        status=t(lang, "status_not_installed"),
                    )
                )
                continue
            try:
                health = await adapter.health()
                if health.healthy:
                    status = t(lang, "status_healthy")
                else:
                    status = t(
                        lang,
                        "status_unhealthy",
                        message=health.message,
                    )
            except Exception:
                status = t(lang, "status_unhealthy", message="error")
            lines.append(
                t(
                    lang,
                    "status_line",
                    protocol=protocol_type.value.upper(),
                    status=status,
                )
            )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t(lang, "btn_refresh"),
                    callback_data="menu:monitoring",
                ),
            ],
        ]
    )

    await message.answer("\n".join(lines), reply_markup=kb)


async def _build_install_keyboard(lang, protocol_registry):
    from src.interface.telegram.keyboards import install_screen_keyboard

    statuses: dict[str, tuple[bool, int | None]] = {}
    for protocol_type in ProtocolType:
        adapter = (
            protocol_registry.get(protocol_type)
            if protocol_registry
            else None
        )
        if adapter is None:
            statuses[protocol_type.value] = (False, None)
            continue
        try:
            health = await adapter.health()
            statuses[protocol_type.value] = (health.healthy, None)
        except Exception:
            statuses[protocol_type.value] = (False, None)
    return install_screen_keyboard(statuses, lang)


def _get_client_names(adapter) -> list[str]:
    config_path = getattr(adapter, "config_path", None)
    if config_path is None:
        return []

    try:
        if str(config_path).endswith(".json"):
            from src.infrastructure.protocols.vless.config_writer import (
                get_clients_from_config,
                load_config,
            )
            config = load_config(config_path)
            clients = get_clients_from_config(config)
            return [c.get("email", "?") for c in clients]
        elif str(config_path).endswith((".yaml", ".yml")):
            return []
    except Exception:
        pass
    return []
