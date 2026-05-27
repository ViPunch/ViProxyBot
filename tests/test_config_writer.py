from src.infrastructure.protocols.vless.config_writer import (
    add_client_to_config,
    create_initial_config,
    get_clients_from_config,
    get_listen_port_from_config,
    load_config,
    remove_client_from_config,
)


def test_create_and_load_config(temp_config_path) -> None:
    create_initial_config(temp_config_path, 443)

    config = load_config(temp_config_path)
    assert get_listen_port_from_config(config) == 443
    assert get_clients_from_config(config) == []


def test_add_and_remove_client(temp_config_path) -> None:
    create_initial_config(temp_config_path, 443)
    config = load_config(temp_config_path)

    updated = add_client_to_config(config, 'uuid-1', 'user1')
    assert len(get_clients_from_config(updated)) == 1
    assert get_clients_from_config(updated)[0]['email'] == 'user1'

    removed = remove_client_from_config(updated, 'user1')
    assert get_clients_from_config(removed) == []
