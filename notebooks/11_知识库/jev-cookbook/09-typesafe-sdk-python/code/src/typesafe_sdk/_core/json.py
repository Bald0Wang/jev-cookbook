"""JSON encoding and lenient response decoding, backed by pydantic-core's fast codec."""

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic_core import from_json, to_json


def _fallback(value: object) -> object:
    """Materialize abstract input containers (any `Mapping`/`Sequence`) into JSON-encodable types.

    Public input types are declared as `Mapping`/`Sequence` so callers may pass, for example, a
    `MappingProxyType` or a custom mapping; pydantic-core's serializer encodes only concrete
    containers natively, so anything else is coerced here before it is re-serialized.
    """
    if isinstance(value, str):
        return str(value)
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    raise TypeError(f"Encoding objects of type {type(value).__name__} is unsupported")


def serialize(value: object) -> bytes:
    return to_json(value, fallback=_fallback)


def deserialize(content: bytes) -> Any:
    if not content:
        return None
    try:
        return from_json(content)
    except ValueError:
        return content.decode("utf-8", errors="replace")
