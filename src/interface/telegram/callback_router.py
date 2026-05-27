from __future__ import annotations

import logging

from aiogram import Router
from aiogram.types import CallbackQuery

from src.domain.enums import ProtocolType
from src.domain.exceptions import ClientNotFoundError
from src.interface.telegram.i18n import t
from src.interface.telegram.screens.main_menu import (
    clients_inline_keyboard,
    main_menu_inline_keyboard,
    protocol_screen_keyboard,
)
from src.services.protocol_registry import ProtocolRegistry

logger = logging.getLogger(__name__)

router = Router()


@router.callback_query(lambda c: c.data == "menu:main")
async def callback_main_menu(
    callback: CallbackQuery,
    lang: str | None = None,
    protocol_registry: ProtocolRegistry = None,
) -> None:
    await callback.message.edit_text(
        t(lang, "main_menu"),
        reply_markup=main_menu_inline_keyboard(lang),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("protocol:"))
async def callback_protocol_screen(
    callback: CallbackQuery,
    lang: str | None = None,
    protocol_registry: ProtocolRegistry = None,
) -> None:
    protocol_name = callback.data.split(":")[1]
    try:
        protocol = ProtocolType(protocol_name)
    except ValueError:
        await callback.answer("Unknown protocol")
        return

    if protocol_registry is None or not protocol_registry.is_registered(protocol):
        await callback.answer(t(lang, "vless_not_installed"))
        return

    adapter = protocol_registry.get(protocol)
    health = await adapter.health()

    status_text = (
        t(lang, "status_healthy")
        if health.healthy
        else t(lang, "status_unhealthy", message=health.message)
    )

    await callback.message.edit_text(
        f"{protocol.value.upper()}\n{status_text}",
        reply_markup=protocol_screen_keyboard(protocol, lang),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("clients:"))
async def callback_clients(
    callback: CallbackQuery,
    lang: str | None = None,
    protocol_registry: ProtocolRegistry = None,
) -> None:
    protocol_name = callback.data.split(":")[1]
    try:
        protocol = ProtocolType(protocol_name)
    except ValueError:
        await callback.answer("Unknown protocol")
        return

    adapter = protocol_registry.get(protocol) if protocol_registry else None
    if adapter is None:
        await callback.answer("Protocol not available")
        return

    from src.infrastructure.protocols.vless.config_writer import (
        get_clients_from_config,
        load_config,
    )

    try:
        config_path = getattr(adapter, "config_path", None)
        if config_path is None:
            names = []
        else:
            config = load_config(config_path)
            clients = get_clients_from_config(config)
            names = [c.get("email", "?") for c in clients]
    except Exception:
        names = []

    if not names:
        await callback.message.edit_text(
            t(lang, "clients_empty"),
            reply_markup=clients_inline_keyboard([], protocol_name, lang),
        )
    else:
        await callback.message.edit_text(
            t(lang, "clients_header"),
            reply_markup=clients_inline_keyboard(names, protocol_name, lang),
        )
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("getlink:"))
async def callback_get_link(
    callback: CallbackQuery,
    lang: str | None = None,
    protocol_registry: ProtocolRegistry = None,
) -> None:
    parts = callback.data.split(":")
    protocol_name = parts[1]
    client_name = parts[2] if len(parts) > 2 else None

    try:
        protocol = ProtocolType(protocol_name)
    except ValueError:
        await callback.answer("Unknown protocol")
        return

    adapter = protocol_registry.get(protocol) if protocol_registry else None
    if adapter is None:
        await callback.answer("Protocol not available")
        return

    if client_name is None:
        await callback.answer("No client specified")
        return

    try:
        generate_link = getattr(adapter, "generate_link", None)
        if generate_link is None:
            await callback.answer("Not supported")
            return
        link = generate_link(client_name)
        await callback.message.edit_text(
            t(lang, "client_link", name=client_name, link=link),
            reply_markup=protocol_screen_keyboard(protocol, lang),
        )
    except ClientNotFoundError:
        await callback.answer(t(lang, "client_link_error", error="Not found"))
    except Exception as exc:
        logger.exception("Get link failed")
        await callback.answer(
            t(lang, "client_link_error", error=str(exc)),
        )
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("addclient:"))
async def callback_add_client(
    callback: CallbackQuery,
    lang: str | None = None,
    protocol_registry: ProtocolRegistry = None,
) -> None:
    await callback.message.edit_text(
        t(lang, "ask_client_name"),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("delclient:"))
async def callback_del_client(
    callback: CallbackQuery,
    lang: str | None = None,
    protocol_registry: ProtocolRegistry = None,
) -> None:
    await callback.message.edit_text(
        t(lang, "ask_delete_client_name"),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("traffic:"))
async def callback_traffic(
    callback: CallbackQuery,
    lang: str | None = None,
    protocol_registry: ProtocolRegistry = None,
) -> None:
    protocol_name = callback.data.split(":")[1]
    await callback.message.edit_text(
        f"Traffic for {protocol_name}",
        reply_markup=protocol_screen_keyboard(
            ProtocolType(protocol_name), lang
        ),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("status:"))
async def callback_status(
    callback: CallbackQuery,
    lang: str | None = None,
    protocol_registry: ProtocolRegistry = None,
) -> None:
    if protocol_registry is None:
        await callback.answer("No registry")
        return

    lines = [t(lang, "status_header")]
    for protocol in protocol_registry.list_registered():
        adapter = protocol_registry.get(protocol)
        if adapter:
            health = await adapter.health()
            status = "OK" if health.healthy else "FAIL"
            lines.append(f"  {protocol.value}: {status}")

    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=main_menu_inline_keyboard(lang),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("confirm:"))
async def callback_confirm(
    callback: CallbackQuery,
    lang: str | None = None,
    protocol_registry: ProtocolRegistry = None,
) -> None:
    parts = callback.data.split(":")
    decision = parts[3] if len(parts) > 3 else ""

    if decision == "no":
        await callback.message.edit_text(
            t(lang, "delete_cancelled"),
            reply_markup=main_menu_inline_keyboard(lang),
        )
        await callback.answer()
        return

    await callback.answer("Confirmed")


@router.callback_query(lambda c: c.data and c.data.startswith("port:"))
async def callback_port_selection(
    callback: CallbackQuery,
    lang: str | None = None,
    protocol_registry: ProtocolRegistry = None,
    state=None,
) -> None:
    parts = callback.data.split(":")
    protocol_name = parts[1] if len(parts) > 1 else ""
    port_value = parts[2] if len(parts) > 2 else ""

    try:
        protocol = ProtocolType(protocol_name)
    except ValueError:
        await callback.answer("Unknown protocol")
        return

    if port_value == "custom":
        await callback.message.edit_text(
            t(lang, "ask_custom_port"),
        )
        await callback.answer()
        return

    try:
        port = int(port_value)
    except ValueError:
        await callback.answer("Invalid port")
        return

    adapter = (
        protocol_registry.get(protocol)
        if protocol_registry
        else None
    )
    if adapter is None:
        await callback.answer("Protocol not available")
        return

    await callback.message.edit_text(
        f"Installing {protocol.value} on port {port}..."
    )
    await callback.answer()

    try:
        result = await adapter.install(
            port, getattr(adapter, "public_host", "")
        )
        success_key = f"install_{protocol.value}_success"
        success_text = t(lang, success_key, port=result.listen_port)
        if success_text == success_key:
            success_text = t(
                lang, "install_success", port=result.listen_port
            )
        await callback.message.edit_text(success_text)
    except Exception as exc:
        logger.exception(f"{protocol.value} install failed")
        error_key = f"install_{protocol.value}_error"
        error_text = t(lang, error_key, error=str(exc))
        if error_text == error_key:
            error_text = t(
                lang, "install_error", error=str(exc)
            )
        await callback.message.edit_text(error_text)
