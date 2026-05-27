from __future__ import annotations

TRANSLATIONS: dict[str, dict[str, str]] = {
    "ru": {
        "bot_ready": "ViProxyBot готов.",
        "main_menu": "Главное меню",
        "status_not_implemented": "Статус пока не реализован.",
        "help_text": "Доступные команды: /start, /menu, /status, /help",
        "access_denied": "Доступ запрещён",
        "btn_status": "Статус",
        "btn_install_vless": "Установить VLESS",
        "btn_install_hysteria2": "Установить Hysteria2",
        "btn_install_mtproto": "Установить MTProto",
        "btn_clients": "Клиенты",
        "btn_add_client": "Добавить клиента",
        "btn_delete_client": "Удалить клиента",
        "btn_get_link": "Получить ссылку",
        "btn_help": "Помощь",
        "btn_back": "Назад",
        "btn_confirm_yes": "Да",
        "btn_confirm_no": "Нет",
        "ask_port": (
            "Введите порт для VLESS (рекомендуется 443) "
            "или нажмите Назад:"
        ),
        "ask_port_hysteria2": (
            "Введите порт для Hysteria2 (рекомендуется 443/UDP) "
            "или нажмите Назад:"
        ),
        "ask_port_mtproto": (
            "Введите порт для MTProto (рекомендуется 443) "
            "или нажмите Назад:"
        ),
        "install_hysteria2_success": "Hysteria2 установлен на порту {port}.",
        "install_hysteria2_error": "Ошибка установки Hysteria2: {error}",
        "install_mtproto_success": "MTProto установлен на порту {port}.",
        "install_mtproto_error": "Ошибка установки MTProto: {error}",
        "ask_client_name": "Введите имя клиента или нажмите Назад:",
        "ask_delete_client_name": (
            "Введите имя клиента для удаления или нажмите Назад:"
        ),
        "ask_link_client_name": (
            "Введите имя клиента для получения ссылки или нажмите Назад:"
        ),
        "ask_confirm_delete": 'Подтвердите удаление клиента "{name}":',
        "install_success": "VLESS установлен на порту {port}.",
        "install_error": "Ошибка установки VLESS: {error}",
        "client_created": "Клиент создан.\n\nСсылка:\n{link}",
        "client_create_error": "Ошибка создания клиента: {error}",
        "client_deleted": 'Клиент "{name}" удалён.',
        "client_delete_error": "Ошибка удаления клиента: {error}",
        "delete_cancelled": "Удаление отменено.",
        "clients_header": "Клиенты VLESS:",
        "clients_empty": "Клиентов нет.",
        "client_link": "Ссылка для {name}:\n{link}",
        "client_link_error": "Ошибка: {error}",
        "vless_not_installed": "VLESS не установлен.",
        "status_header": "Статус VLESS:",
        "status_healthy": "Сервис работает.",
        "status_unhealthy": "Сервис не работает: {message}",
        "unexpected_input": "Используйте кнопки меню.",
    },
    "en": {
        "bot_ready": "VPNBot is ready.",
        "main_menu": "Main menu",
        "status_not_implemented": "Status is not implemented yet.",
        "help_text": "Available commands: /start, /menu, /status, /help",
        "access_denied": "Access denied",
        "btn_status": "Status",
        "btn_install_vless": "Install VLESS",
        "btn_install_hysteria2": "Install Hysteria2",
        "btn_install_mtproto": "Install MTProto",
        "btn_clients": "Clients",
        "btn_add_client": "Add Client",
        "btn_delete_client": "Delete Client",
        "btn_get_link": "Get Link",
        "btn_help": "Help",
        "btn_back": "Back",
        "btn_confirm_yes": "Yes",
        "btn_confirm_no": "No",
        "ask_port": (
            "Enter port for VLESS (recommended 443) "
            "or press Back:"
        ),
        "ask_port_hysteria2": (
            "Enter port for Hysteria2 (recommended 443/UDP) "
            "or press Back:"
        ),
        "ask_port_mtproto": (
            "Enter port for MTProto (recommended 443) "
            "or press Back:"
        ),
        "install_hysteria2_success": "Hysteria2 installed on port {port}.",
        "install_hysteria2_error": "Hysteria2 installation error: {error}",
        "install_mtproto_success": "MTProto installed on port {port}.",
        "install_mtproto_error": "MTProto installation error: {error}",
        "ask_client_name": "Enter client name or press Back:",
        "ask_delete_client_name": (
            "Enter client name to delete or press Back:"
        ),
        "ask_link_client_name": (
            "Enter client name to get link or press Back:"
        ),
        "ask_confirm_delete": 'Confirm deletion of client "{name}":',
        "install_success": "VLESS installed on port {port}.",
        "install_error": "VLESS installation error: {error}",
        "client_created": "Client created.\n\nLink:\n{link}",
        "client_create_error": "Client creation error: {error}",
        "client_deleted": 'Client "{name}" deleted.',
        "client_delete_error": "Client deletion error: {error}",
        "delete_cancelled": "Deletion cancelled.",
        "clients_header": "VLESS Clients:",
        "clients_empty": "No clients.",
        "client_link": "Link for {name}:\n{link}",
        "client_link_error": "Error: {error}",
        "vless_not_installed": "VLESS is not installed.",
        "status_header": "VLESS Status:",
        "status_healthy": "Service is running.",
        "status_unhealthy": "Service is not running: {message}",
        "unexpected_input": "Use menu buttons.",
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
