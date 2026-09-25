"""Shared JSON value types.

Defined with `TypeAliasType` so the recursive aliases build a Pydantic core schema
without hitting the recursion limit that a plain recursive `TypeAlias` triggers.
"""

from collections.abc import Mapping, Sequence

from typing_extensions import TypeAliasType

JSONValue = TypeAliasType(
    "JSONValue",
    "str | int | float | bool | Sequence[JSONValue | None] | Mapping[str, JSONValue | None]",
)
"""A JSON-like value. May be nested and contain `None`."""

JSONContent = TypeAliasType(
    "JSONContent",
    "str | Mapping[str, JSONValue | None] | Sequence[JSONValue | None]",
)
"""Either a plain string or a mapping/sequence of [`JSONValue`][typesafe_sdk.JSONValue] entries."""
