from __future__ import annotations

import logging
from pathlib import Path

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from src.domain.enums import ProtocolType
from src.domain.exceptions import ClientNotFoundError
from src.interface.telegram.commands import MenuStates, _get_client_names
from src.interface.telegram.i18n import t
from src.interface.telegram.keyboards import (
    client_list_keyboard,
    client_protocol_keyboard,
    client_select_keyboard,
    confirm_keyboard,
    install_screen_keyboard,
    main_menu_keyboard,
    port_selection_keyboard,
    vless_confirm_keyboard,
    vless_fingerprint_keyboard,
    vless_port_keyboard,
    vless_security_keyboard,
    vless_sni_keyboard,
    vless_sniffing_keyboard,
    vless_transport_keyboard,
)
from src.services.protocol_registry import ProtocolRegistry

logger = logging.getLogger(__name__)

router = Router()


# --- Main menu ---


@router.callback_query(lambda c: c.data == "menu:main")
async def callback_main_menu(
    callback: CallbackQuery,
    lang: str | None = None,
    state: FSMContext = None,
) -> None:
    await state.set_state(MenuStates.idle)
    await callback.message.edit_text(
        t(lang, "main_menu"),
    )
    await callback.message.answer(
        t(lang, "main_menu"),
        reply_markup=main_menu_keyboard(lang),
    )
    await callback.answer()


# --- Installation screen ---


@router.callback_query(lambda c: c.data == "menu:install")
async def callback_install_screen(
    callback: CallbackQuery,
    lang: str | None = None,
    protocol_registry: ProtocolRegistry = None,
    state: FSMContext = None,
) -> None:
    await state.set_state(MenuStates.idle)
    statuses = await _get_statuses(protocol_registry)

    await callback.message.edit_text(
        t(lang, "install_screen_title"),
        reply_markup=install_screen_keyboard(statuses, lang),
    )
    await callback.answer()


# --- Install protocol: show domain selection ---


@router.callback_query(
    lambda c: c.data and c.data.startswith("install:")
)
async def callback_install_protocol(
    callback: CallbackQuery,
    lang: str | None = None,
    state: FSMContext = None,
) -> None:
    protocol_name = callback.data.split(":")[1]
    logger.info(
        "Install callback: protocol=%s, user=%s",
        protocol_name, callback.from_user.id,
    )
    await state.update_data(install_protocol=protocol_name)

    if protocol_name == "vless":
        await callback.message.edit_text(
            t(lang, "vless_step_port"),
            reply_markup=vless_port_keyboard(lang),
        )
    elif protocol_name == "hysteria2":
        await state.set_state(MenuStates.ask_custom_port)
        await callback.message.edit_text(
            t(lang, "ask_port", protocol=protocol_name.upper()),
            reply_markup=port_selection_keyboard(protocol_name, lang),
        )
    await callback.answer()


# --- Domain selection: show port selection ---


@router.callback_query(
    lambda c: c.data and c.data.startswith("domain:")
)
async def callback_domain_selection(
    callback: CallbackQuery,
    lang: str | None = None,
    state: FSMContext = None,
) -> None:
    parts = callback.data.split(":")
    protocol_name = parts[1] if len(parts) > 1 else ""
    domain_value = parts[2] if len(parts) > 2 else ""

    if domain_value == "custom":
        await state.set_state(MenuStates.ask_domain)
        await state.update_data(install_protocol=protocol_name)
        await callback.message.edit_text(
            t(lang, "ask_custom_domain"),
        )
        await callback.answer()
        return

    # For VLESS: store SNI domain and go to port selection
    await state.set_state(MenuStates.ask_custom_port)
    await state.update_data(
        install_protocol=protocol_name,
        install_sni=domain_value,
    )

    await callback.message.edit_text(
        t(lang, "ask_port", protocol=protocol_name.upper()),
        reply_markup=port_selection_keyboard(protocol_name, lang),
    )
    await callback.answer()


# --- SSL selection: show port selection ---


@router.callback_query(
    lambda c: c.data and c.data.startswith("ssl:")
)
async def callback_ssl_selection(
    callback: CallbackQuery,
    lang: str | None = None,
    state: FSMContext = None,
) -> None:
    parts = callback.data.split(":")
    protocol_name = parts[1] if len(parts) > 1 else ""
    ssl_type = parts[2] if len(parts) > 2 else ""

    await state.update_data(install_ssl_type=ssl_type)

    if ssl_type == "domain":
        await state.set_state(MenuStates.ask_ssl_domain)
        await callback.message.edit_text(
            t(lang, "ask_ssl_domain"),
        )
        await callback.answer()
        return

    await state.set_state(MenuStates.ask_custom_port)
    await callback.message.edit_text(
        t(lang, "ask_port", protocol=protocol_name.upper()),
        reply_markup=port_selection_keyboard(protocol_name, lang),
    )
    await callback.answer()


# --- Port selection: install on selected port ---


@router.callback_query(
    lambda c: c.data and c.data.startswith("port:")
)
async def callback_port_selection(
    callback: CallbackQuery,
    lang: str | None = None,
    protocol_registry: ProtocolRegistry = None,
    state: FSMContext = None,
) -> None:
    parts = callback.data.split(":")
    protocol_name = parts[1] if len(parts) > 1 else ""
    port_value = parts[2] if len(parts) > 2 else ""

    if port_value == "custom":
        await state.set_state(MenuStates.ask_custom_port)
        await state.update_data(install_protocol=protocol_name)
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

    await _do_install(
        callback, lang, protocol_registry, state, protocol_name, port
    )


async def _do_install(
    callback: CallbackQuery,
    lang: str | None,
    protocol_registry: ProtocolRegistry | None,
    state: FSMContext | None,
    protocol_name: str,
    port: int,
) -> None:
    try:
        protocol = ProtocolType(protocol_name)
    except ValueError:
        await callback.answer("Unknown protocol")
        return

    adapter = (
        protocol_registry.get(protocol) if protocol_registry else None
    )
    if adapter is None:
        await callback.answer("Protocol not available")
        return

    # Get SNI domain from state data (VLESS uses install_sni)
    data = await state.get_data() if state else {}
    sni_domain = data.get("install_sni", "")

    await state.set_state(MenuStates.idle)
    await callback.message.edit_text(
        f"Installing {protocol.value} on port {port}..."
    )
    await callback.answer()

    try:
        # Set SNI domain for VLESS REALITY config
        if protocol_name == "vless" and sni_domain:
            logger.info("Setting VLESS SNI: %s", sni_domain)
            setattr(adapter, "_sni_domain", sni_domain)

        host = getattr(adapter, "public_host", "")
        logger.info("Calling adapter.install(%s, %s)", port, host)
        result = await adapter.install(port, host)
        logger.info(
            "Install result: success=%s, port=%s",
            result.success, result.listen_port,
        )
        # After successful install, show client list for this protocol
        from src.interface.telegram.keyboards import client_list_keyboard

        clients = _get_client_names(adapter)
        await callback.message.edit_text(
            t(
                lang,
                "install_success",
                protocol=protocol.value.upper(),
                port=result.listen_port,
            )
            + "\n\n"
            + t(lang, "clients_list_title", protocol=protocol.value.upper())
            + "\n"
            + t(lang, "clients_empty"),
            reply_markup=client_list_keyboard(
                protocol_name, clients, lang
            ),
        )
    except Exception as exc:
        logger.exception("Install failed")
        statuses = await _get_statuses(protocol_registry)
        await callback.message.edit_text(
            t(
                lang,
                "install_error",
                protocol=protocol.value.upper(),
                error=str(exc),
            ),
            reply_markup=install_screen_keyboard(statuses, lang),
        )


# --- Clients screen: select protocol ---


@router.callback_query(lambda c: c.data == "menu:clients")
async def callback_clients_screen(
    callback: CallbackQuery,
    lang: str | None = None,
    state: FSMContext = None,
) -> None:
    await state.set_state(MenuStates.idle)
    await callback.message.edit_text(
        t(lang, "clients_screen_title"),
        reply_markup=client_protocol_keyboard(lang),
    )
    await callback.answer()


# --- Clients list for protocol ---


@router.callback_query(
    lambda c: c.data and c.data.startswith("clients:")
)
async def callback_client_list(
    callback: CallbackQuery,
    lang: str | None = None,
    protocol_registry: ProtocolRegistry = None,
    state: FSMContext = None,
) -> None:
    await state.set_state(MenuStates.idle)
    protocol_name = callback.data.split(":")[1]
    try:
        protocol = ProtocolType(protocol_name)
    except ValueError:
        await callback.answer("Unknown protocol")
        return

    adapter = (
        protocol_registry.get(protocol) if protocol_registry else None
    )
    if adapter is None:
        await callback.answer("Protocol not available")
        return

    clients = _get_client_names(adapter)
    title = t(lang, "clients_list_title", protocol=protocol.value.upper())
    if not clients:
        text = f"{title}\n\n{t(lang, 'clients_empty')}"
    else:
        lines = [title, ""]
        for name in clients:
            lines.append(f"  • {name}")
        text = "\n".join(lines)

    await callback.message.edit_text(
        text,
        reply_markup=client_list_keyboard(
            protocol_name, clients, lang
        ),
    )
    await callback.answer()


# --- Get link: show link for client ---


@router.callback_query(
    lambda c: c.data and c.data.startswith("getlink:")
)
async def callback_get_link(
    callback: CallbackQuery,
    lang: str | None = None,
    protocol_registry: ProtocolRegistry = None,
    state: FSMContext = None,
) -> None:
    await state.set_state(MenuStates.idle)
    parts = callback.data.split(":")
    protocol_name = parts[1]
    client_name = parts[2] if len(parts) > 2 else None

    try:
        protocol = ProtocolType(protocol_name)
    except ValueError:
        await callback.answer("Unknown protocol")
        return

    adapter = (
        protocol_registry.get(protocol) if protocol_registry else None
    )
    if adapter is None:
        await callback.answer("Protocol not available")
        return

    if client_name is None:
        clients = _get_client_names(adapter)
        await callback.message.edit_text(
            t(lang, "select_client_link"),
            reply_markup=client_select_keyboard(
                protocol_name, clients, "getlink", lang
            ),
        )
        await callback.answer()
        return

    try:
        generate_link = getattr(adapter, "generate_link", None)
        if generate_link is None:
            await callback.answer("Not supported")
            return
        link = generate_link(client_name)
        await callback.message.edit_text(
            t(lang, "client_link", name=client_name, link=link),
            reply_markup=client_list_keyboard(
                protocol_name, _get_client_names(adapter), lang
            ),
        )
    except ClientNotFoundError:
        await callback.answer(
            t(lang, "client_link_error", error="Not found")
        )
    except Exception as exc:
        logger.exception("Get link failed")
        await callback.answer(
            t(lang, "client_link_error", error=str(exc))
        )
    await callback.answer()


# --- Add client: ask for name ---


@router.callback_query(
    lambda c: c.data and c.data.startswith("addclient:")
)
async def callback_add_client(
    callback: CallbackQuery,
    lang: str | None = None,
    state: FSMContext = None,
) -> None:
    protocol_name = callback.data.split(":")[1]
    await state.set_state(MenuStates.ask_client_name)
    await state.update_data(add_client_protocol=protocol_name)
    await callback.message.edit_text(
        t(lang, "ask_client_name"),
    )
    await callback.answer()


# --- Delete client: select client ---


@router.callback_query(
    lambda c: c.data and c.data.startswith("delselect:")
)
async def callback_delete_select(
    callback: CallbackQuery,
    lang: str | None = None,
    protocol_registry: ProtocolRegistry = None,
    state: FSMContext = None,
) -> None:
    await state.set_state(MenuStates.idle)
    protocol_name = callback.data.split(":")[1]
    try:
        protocol = ProtocolType(protocol_name)
    except ValueError:
        await callback.answer("Unknown protocol")
        return

    adapter = (
        protocol_registry.get(protocol) if protocol_registry else None
    )
    if adapter is None:
        await callback.answer("Protocol not available")
        return

    clients = _get_client_names(adapter)
    await callback.message.edit_text(
        t(lang, "select_client_delete"),
        reply_markup=client_select_keyboard(
            protocol_name, clients, "deldone", lang
        ),
    )
    await callback.answer()


# --- Delete client: confirm ---


@router.callback_query(
    lambda c: c.data and c.data.startswith("deldone:")
)
async def callback_delete_confirm(
    callback: CallbackQuery,
    lang: str | None = None,
    state: FSMContext = None,
) -> None:
    parts = callback.data.split(":")
    protocol_name = parts[1]
    client_name = parts[2] if len(parts) > 2 else ""
    await callback.message.edit_text(
        t(lang, "ask_confirm_delete", name=client_name),
        reply_markup=confirm_keyboard(protocol_name, client_name, lang),
    )
    await callback.answer()


# --- Delete client: execute ---


@router.callback_query(
    lambda c: c.data and c.data.startswith("confirmdel:")
)
async def callback_delete_execute(
    callback: CallbackQuery,
    lang: str | None = None,
    protocol_registry: ProtocolRegistry = None,
    state: FSMContext = None,
) -> None:
    await state.set_state(MenuStates.idle)
    parts = callback.data.split(":")
    protocol_name = parts[1]
    client_name = parts[2]
    decision = parts[3] if len(parts) > 3 else ""

    if decision != "yes":
        await callback.message.edit_text(
            t(lang, "delete_cancelled"),
        )
        await callback.answer()
        return

    try:
        protocol = ProtocolType(protocol_name)
    except ValueError:
        await callback.answer("Unknown protocol")
        return

    adapter = (
        protocol_registry.get(protocol) if protocol_registry else None
    )
    if adapter is None:
        await callback.answer("Protocol not available")
        return

    try:
        await adapter.delete_client(client_name)
        clients = _get_client_names(adapter)
        await callback.message.edit_text(
            t(lang, "client_deleted", name=client_name),
            reply_markup=client_list_keyboard(
                protocol_name, clients, lang
            ),
        )
    except Exception as exc:
        logger.exception("Delete client failed")
        await callback.message.edit_text(
            t(lang, "client_delete_error", error=str(exc)),
            reply_markup=client_list_keyboard(
                protocol_name, _get_client_names(adapter), lang
            ),
        )
    await callback.answer()


# --- Monitoring screen ---


@router.callback_query(lambda c: c.data == "menu:monitoring")
async def callback_monitoring(
    callback: CallbackQuery,
    lang: str | None = None,
    protocol_registry: ProtocolRegistry = None,
    state: FSMContext = None,
) -> None:
    await state.set_state(MenuStates.idle)
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

    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t(lang, "btn_refresh"),
                    callback_data="menu:monitoring",
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

    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=kb,
    )
    await callback.answer()


# --- VLESS setup flow ---


@router.callback_query(
    lambda c: c.data and c.data.startswith("vless:port:")
)
async def callback_vless_port(
    callback: CallbackQuery,
    lang: str | None = None,
    state: FSMContext = None,
) -> None:
    value = callback.data.split(":")[2]

    if value == "custom":
        await state.set_state(MenuStates.ask_custom_port)
        await state.update_data(vless_setup_step="port")
        await callback.message.edit_text(t(lang, "ask_custom_port"))
        await callback.answer()
        return

    try:
        port = int(value)
    except ValueError:
        await callback.answer("Invalid port")
        return

    await state.update_data(vless_port=port)
    await callback.message.edit_text(
        t(lang, "vless_step_sni"),
        reply_markup=vless_sni_keyboard(lang),
    )
    await callback.answer()


@router.callback_query(
    lambda c: c.data and c.data.startswith("vless:sni:")
)
async def callback_vless_sni(
    callback: CallbackQuery,
    lang: str | None = None,
    state: FSMContext = None,
) -> None:
    value = callback.data.split(":")[2]

    if value == "custom":
        await state.set_state(MenuStates.ask_custom_sni)
        await callback.message.edit_text(t(lang, "ask_custom_sni"))
        await callback.answer()
        return

    await state.update_data(vless_sni=value)
    await callback.message.edit_text(
        t(lang, "vless_step_transport"),
        reply_markup=vless_transport_keyboard(lang),
    )
    await callback.answer()


@router.callback_query(
    lambda c: c.data and c.data.startswith("vless:transport:")
)
async def callback_vless_transport(
    callback: CallbackQuery,
    lang: str | None = None,
    state: FSMContext = None,
) -> None:
    transport = callback.data.split(":")[2]
    await state.update_data(vless_transport=transport)
    await callback.message.edit_text(
        t(lang, "vless_step_security"),
        reply_markup=vless_security_keyboard(lang),
    )
    await callback.answer()


@router.callback_query(
    lambda c: c.data and c.data.startswith("vless:security:")
)
async def callback_vless_security(
    callback: CallbackQuery,
    lang: str | None = None,
    state: FSMContext = None,
) -> None:
    security = callback.data.split(":")[2]
    await state.update_data(vless_security=security)
    await callback.message.edit_text(
        t(lang, "vless_step_fingerprint"),
        reply_markup=vless_fingerprint_keyboard(lang),
    )
    await callback.answer()


@router.callback_query(
    lambda c: c.data and c.data.startswith("vless:fingerprint:")
)
async def callback_vless_fingerprint(
    callback: CallbackQuery,
    lang: str | None = None,
    state: FSMContext = None,
) -> None:
    fingerprint = callback.data.split(":")[2]
    await state.update_data(vless_fingerprint=fingerprint)
    await state.update_data(vless_sniffing=[])
    await callback.message.edit_text(
        t(lang, "vless_step_sniffing"),
        reply_markup=vless_sniffing_keyboard([], lang),
    )
    await callback.answer()


@router.callback_query(
    lambda c: c.data and c.data.startswith("vless:sniffing:")
)
async def callback_vless_sniffing(
    callback: CallbackQuery,
    lang: str | None = None,
    state: FSMContext = None,
) -> None:
    value = callback.data.split(":")[2]

    if value == "done":
        data = await state.get_data()
        sniffing = data.get("vless_sniffing", [])
        port = data.get("vless_port", 443)
        sni = data.get("vless_sni", VLESS_REALITY_SNI)
        transport = data.get("vless_transport", "tcp")
        security = data.get("vless_security", "reality")
        fingerprint = data.get("vless_fingerprint", "chrome")

        lines = [
            t(lang, "vless_confirm_title"),
            "",
            t(lang, "vless_confirm_port", port=port),
            t(lang, "vless_confirm_sni", sni=sni),
            t(lang, "vless_confirm_transport", transport=transport),
            t(lang, "vless_confirm_security", security=security),
            t(lang, "vless_confirm_fingerprint", fingerprint=fingerprint),
            t(lang, "vless_confirm_sniffing", sniffing=", ".join(sniffing) or "none"),
        ]
        await callback.message.edit_text(
            "\n".join(lines),
            reply_markup=vless_confirm_keyboard(lang),
        )
        await callback.answer()
        return

    data = await state.get_data()
    selected: list[str] = data.get("vless_sniffing", [])
    if value in selected:
        selected.remove(value)
    else:
        selected.append(value)
    await state.update_data(vless_sniffing=selected)
    await callback.message.edit_text(
        t(lang, "vless_step_sniffing"),
        reply_markup=vless_sniffing_keyboard(selected, lang),
    )
    await callback.answer()


@router.callback_query(
    lambda c: c.data and c.data.startswith("vless:confirm:")
)
async def callback_vless_confirm(
    callback: CallbackQuery,
    lang: str | None = None,
    protocol_registry: ProtocolRegistry = None,
    state: FSMContext = None,
) -> None:
    decision = callback.data.split(":")[2]
    if decision != "yes":
        await callback.answer()
        return

    data = await state.get_data()
    port = data.get("vless_port", 443)
    sni = data.get("vless_sni", VLESS_REALITY_SNI)
    transport = data.get("vless_transport", "tcp")
    security = data.get("vless_security", "reality")
    fingerprint = data.get("vless_fingerprint", "chrome")
    sniffing_protocols = data.get("vless_sniffing", ["http", "tls"])

    await state.set_state(MenuStates.idle)

    adapter = (
        protocol_registry.get(ProtocolType.VLESS)
        if protocol_registry
        else None
    )
    if adapter is None:
        await callback.answer("Protocol not available")
        return

    from src.infrastructure.protocols.vless.adapter import InboundConfig

    await callback.message.edit_text("Creating VLESS inbound...")
    await callback.answer()

    try:
        host = getattr(adapter, "public_host", "")

        inbound_config = InboundConfig(
            port=port,
            sni=sni,
            transport=transport,
            security=security,
            fingerprint=fingerprint,
            sniffing_protocols=sniffing_protocols,
        )

        config_path = getattr(adapter, "config_path", None)
        xray_installed = Path("/usr/local/bin/xray").exists()
        if not xray_installed or not config_path or not config_path.exists():
            await adapter.install_base(host)  # type: ignore[attr-defined]

        await adapter.create_inbound(inbound_config)  # type: ignore[attr-defined]

        clients = _get_client_names(adapter)
        await callback.message.edit_text(
            t(lang, "vless_created", port=port),
            reply_markup=client_list_keyboard("vless", clients, lang),
        )
    except Exception as exc:
        logger.exception("VLESS inbound creation failed")
        await callback.message.edit_text(
            t(lang, "vless_created_error", error=str(exc)),
            reply_markup=install_screen_keyboard(
                await _get_statuses(protocol_registry), lang
            ),
        )


VLESS_REALITY_SNI = "www.microsoft.com"


# --- Noop handler for non-clickable buttons ---


@router.callback_query(lambda c: c.data == "noop")
async def callback_noop(callback: CallbackQuery) -> None:
    await callback.answer()


# --- Helpers ---


async def _get_statuses(
    protocol_registry: ProtocolRegistry | None,
) -> dict[str, tuple[bool, int | None]]:
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
            if health.healthy:
                statuses[protocol_type.value] = (True, None)
            else:
                statuses[protocol_type.value] = (False, None)
        except Exception:
            statuses[protocol_type.value] = (False, None)
    return statuses
