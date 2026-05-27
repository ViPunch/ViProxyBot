from src.infrastructure.protocols.mtproto.adapter import MtprotoAdapter
from src.infrastructure.protocols.mtproto.link_generator import (
    generate_mtproto_link,
    generate_mtproto_tg_link,
)

__all__ = [
    "MtprotoAdapter",
    "generate_mtproto_link",
    "generate_mtproto_tg_link",
]
