import socket
import uuid
from datetime import datetime

__all__ = (
    "now",
    "is_valid_uuid",
    "unused_port",
    "make_uuid",
    "make_request_id",
)

LOCALHOST = "127.0.0.1"


def now() -> datetime:
    return datetime.now()


def is_valid_uuid(uuid_string: str, version: int = 4) -> bool:
    try:
        uuid_obj = uuid.UUID(uuid_string, version=version)
    except ValueError:  # pragma: no cover
        return False
    return str(uuid_obj) == uuid_string


def unused_port(host: str = LOCALHOST) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        address = (host, 0)
        s.bind(address)
        return s.getsockname()[1]


def make_uuid() -> str:
    return str(uuid.uuid4())


make_request_id = make_uuid
