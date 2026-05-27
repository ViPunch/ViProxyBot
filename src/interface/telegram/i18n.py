from __future__ import annotations

TRANSLATIONS: dict[str, dict[str, str]] = {
    "ru": {
        "bot_ready": "ViProxyBot готов.",
        "main_menu": "Главное меню",
        "help_text": (
            "ViProxyBot — управление VPN через Telegram.\n\n"
            "📦 Установка — установка протоколов\n"
            "👥 Клиенты — управление пользователями\n"
            "📊 Мониторинг — статус и трафик\n"
            "❓ Помощь — эта справка"
        ),
        "access_denied": "Доступ запрещён",
        "unexpected_input": "Используйте кнопки меню.",

        # Reply keyboard
        "btn_install": "📦 Установка",
        "btn_clients": "👥 Клиенты",
        "btn_monitoring": "📊 Мониторинг",
        "btn_help": "❓ Помощь",

        # Common
        "btn_back": "⬅️ Назад",
        "btn_confirm_yes": "✅ Да",
        "btn_confirm_no": "❌ Нет",

        # Installation screen
        "install_screen_title": "📦 Установка протоколов",
        "install_vless": "VLESS",
        "install_hysteria2": "Hysteria2",
        "install_mtproto": "MTProto",
        "btn_install_protocol": "Установить",
        "btn_delete_protocol": "Удалить",
        "protocol_installed": "✅ установлен (порт {port})",
        "protocol_not_installed": "❌ не установлен",
        "btn_port_443": "443",
        "btn_port_8443": "8443",
        "btn_custom_port": "✏️ Другой порт",
        "ask_port": "Выберите порт для {protocol}:",
        "ask_custom_port": "Введите номер порта (1-65535):",
        "ask_domain": "Введите домен/SNI для {protocol}:",
        "ask_custom_domain": "Введите домен (например, www.google.com):",
        "btn_sni_microsoft": "www.microsoft.com",
        "btn_sni_google": "www.google.com",
        "btn_sni_apple": "www.apple.com",
        "btn_sni_cloudflare": "cloudflare.com",
        "btn_custom_domain": "✏️ Другой домен",
        "install_success": "✅ {protocol} установлен на порту {port}.",
        "install_error": "❌ Ошибка установки {protocol}: {error}",

        # Client management screen
        "clients_screen_title": "👥 Управление клиентами",
        "select_protocol": "Выберите протокол:",
        "clients_list_title": "Клиенты {protocol}:",
        "clients_empty": "Клиентов нет.",
        "btn_add_client": "➕ Добавить клиента",
        "btn_get_link": "🔗 Получить ссылку",
        "btn_delete_client": "❌ Удалить клиента",
        "ask_client_name": "Введите имя клиента:",
        "client_created": "✅ Клиент \"{name}\" создан!\n\n🔗 Ссылка:\n{link}",
        "client_create_error": "❌ Ошибка: {error}",
        "select_client_link": "Выберите клиента для получения ссылки:",
        "select_client_delete": "Выберите клиента для удаления:",
        "client_link": "🔗 Ссылка для {name}:\n{link}",
        "client_link_error": "❌ Ошибка: {error}",
        "ask_confirm_delete": 'Подтвердите удаление клиента "{name}":',
        "client_deleted": '✅ Клиент "{name}" удалён.',
        "client_delete_error": "❌ Ошибка: {error}",
        "delete_cancelled": "Удаление отменено.",

        # Monitoring screen
        "monitoring_title": "📊 Мониторинг",
        "status_header": "Статус протоколов:",
        "status_line": "  {protocol}: {status}",
        "status_healthy": "✅ работает",
        "status_unhealthy": "❌ {message}",
        "status_not_installed": "⬜ не установлен",
        "btn_refresh": "🔄 Обновить",
    },
    "en": {
        "bot_ready": "ViProxyBot is ready.",
        "main_menu": "Main menu",
        "help_text": (
            "ViProxyBot — VPN management via Telegram.\n\n"
            "📦 Installation — install protocols\n"
            "👥 Clients — manage users\n"
            "📊 Monitoring — status and traffic\n"
            "❓ Help — this help"
        ),
        "access_denied": "Access denied",
        "unexpected_input": "Use menu buttons.",

        # Reply keyboard
        "btn_install": "📦 Installation",
        "btn_clients": "👥 Clients",
        "btn_monitoring": "📊 Monitoring",
        "btn_help": "❓ Help",

        # Common
        "btn_back": "⬅️ Back",
        "btn_confirm_yes": "✅ Yes",
        "btn_confirm_no": "❌ No",

        # Installation screen
        "install_screen_title": "📦 Protocol Installation",
        "install_vless": "VLESS",
        "install_hysteria2": "Hysteria2",
        "install_mtproto": "MTProto",
        "btn_install_protocol": "Install",
        "btn_delete_protocol": "Delete",
        "protocol_installed": "✅ installed (port {port})",
        "protocol_not_installed": "❌ not installed",
        "btn_port_443": "443",
        "btn_port_8443": "8443",
        "btn_custom_port": "✏️ Custom port",
        "ask_port": "Select port for {protocol}:",
        "ask_custom_port": "Enter port number (1-65535):",
        "ask_domain": "Enter domain/SNI for {protocol}:",
        "ask_custom_domain": "Enter domain (e.g., www.google.com):",
        "btn_sni_microsoft": "www.microsoft.com",
        "btn_sni_google": "www.google.com",
        "btn_sni_apple": "www.apple.com",
        "btn_sni_cloudflare": "cloudflare.com",
        "btn_custom_domain": "✏️ Other domain",
        "install_success": "✅ {protocol} installed on port {port}.",
        "install_error": "❌ {protocol} installation error: {error}",

        # Client management screen
        "clients_screen_title": "👥 Client Management",
        "select_protocol": "Select protocol:",
        "clients_list_title": "{protocol} Clients:",
        "clients_empty": "No clients.",
        "btn_add_client": "➕ Add Client",
        "btn_get_link": "🔗 Get Link",
        "btn_delete_client": "❌ Delete Client",
        "ask_client_name": "Enter client name:",
        "client_created": "✅ Client \"{name}\" created!\n\n🔗 Link:\n{link}",
        "client_create_error": "❌ Error: {error}",
        "select_client_link": "Select client for link:",
        "select_client_delete": "Select client to delete:",
        "client_link": "🔗 Link for {name}:\n{link}",
        "client_link_error": "❌ Error: {error}",
        "ask_confirm_delete": 'Confirm deletion of client "{name}":',
        "client_deleted": '✅ Client "{name}" deleted.',
        "client_delete_error": "❌ Error: {error}",
        "delete_cancelled": "Deletion cancelled.",

        # Monitoring screen
        "monitoring_title": "📊 Monitoring",
        "status_header": "Protocol status:",
        "status_line": "  {protocol}: {status}",
        "status_healthy": "✅ running",
        "status_unhealthy": "❌ {message}",
        "status_not_installed": "⬜ not installed",
        "btn_refresh": "🔄 Refresh",
    },
}

DEFAULT_LANG = "en"


def t(lang: str | None, key: str, **kwargs: object) -> str:
    effective = lang if lang in TRANSLATIONS else DEFAULT_LANG
    template = TRANSLATIONS[effective].get(
        key, TRANSLATIONS[DEFAULT_LANG].get(key, key)
    )
    if kwargs:
        return template.format(**kwargs)
    return template
