"""Response schemas and decoding shared by the SDK response types and custom Pydantic models."""

from collections.abc import Sequence
from functools import cached_property
from typing import Any, TypeVar, cast

import httpx2
from pydantic import BaseModel, ConfigDict, ValidationError
from typing_extensions import Self

from typesafe_sdk._core.constants import REQUEST_ID_HEADER
from typesafe_sdk._core.errors import TypeSafeAPIResponseValidationError, TypeSafeError, api_error
from typesafe_sdk._core.json import deserialize

ResponseT = TypeVar("ResponseT", bound=BaseModel)


class Schema(BaseModel):
    """Base type for immutable response objects that tolerate unknown fields."""

    model_config = ConfigDict(extra="ignore", frozen=True, strict=True)


def format_path(segments: Sequence[str | int]) -> str:
    """Render path segments as the SDK's dotted `field_path`."""
    path = ""
    for segment in segments:
        if segment == "[key]":
            # Pydantic marks an invalid mapping key with a synthetic `[key]` segment; it is noise here.
            continue
        if isinstance(segment, int):
            path += f"[{segment}]"
        else:
            path += f".{segment}" if path else str(segment)
    return path


def format_error_path(prefix: Sequence[str | int], error: ValidationError) -> str:
    """Render the first Pydantic error location as the SDK's dotted `field_path`.

    Integer locations become bracketed indices (`models[1].name`); string locations are dotted.
    """
    first = error.errors(include_url=False)[0]["loc"]
    return format_path((*prefix, *first))


def _request_endpoint(response: httpx2.Response) -> str | None:
    """Describe the endpoint if the response has an originating request."""
    try:
        request = response.request
    except RuntimeError:
        return None
    return f"{request.method} {request.url.copy_with(userinfo=b'', query=None, fragment=None)}"


def validation_error(response: httpx2.Response, path: str) -> TypeSafeAPIResponseValidationError:
    """Build a `TypeSafeAPIResponseValidationError` locating a bad field in `response`."""
    return TypeSafeAPIResponseValidationError(
        response.status_code, deserialize(response.content), response.headers, path, _request_endpoint(response)
    )


class _ResponseMixin:
    """HTTP metadata and custom decoding shared by the SDK response types."""

    @classmethod
    def from_http_response(cls, response: httpx2.Response) -> Self:
        """Parse an HTTP response into this response type, attaching the raw response.

        A non-success status raises the matching `TypeSafeAPIError`; a body that does not
        match the schema raises a `TypeSafeAPIResponseValidationError`.
        """
        return cast(Self, parse_response(response, cast(Any, cls)))

    @classmethod
    def _decode(cls, response: httpx2.Response) -> Self:
        """Build the response from its HTTP body. Subclasses implement the type-specific decode."""
        raise NotImplementedError

    @cached_property
    def request_id(self) -> str:
        """The ``x-typesafe-request-id`` response header."""
        request_id: str | None = self.__dict__.get("_request_id")
        if request_id is None:
            raise TypeSafeError("The response did not include a request ID.")
        return request_id

    @property
    def raw_http_response(self) -> httpx2.Response:
        """The underlying `httpx2.Response`, exposing status, headers, and body."""
        response: httpx2.Response | None = self.__dict__.get("_raw")
        if response is None:
            raise TypeSafeError("The response was not created from a raw HTTP response.")
        return response


class Response(Schema, _ResponseMixin):
    """A response object with its originating HTTP response attached."""


def parse_response(response: httpx2.Response, response_type: type[ResponseT]) -> ResponseT:
    """Decode an SDK response or custom Pydantic model with consistent API and validation errors."""
    if not response.is_success:
        raise api_error(response.status_code, deserialize(response.content), response.headers, _request_endpoint(response))
    if issubclass(response_type, _ResponseMixin):
        result = response_type._decode(response)  # noqa: SLF001 - Dispatch to the SDK response decoder.
    else:
        try:
            result = response_type.model_validate_json(response.content)
        except ValidationError as error:
            raise validation_error(response, format_error_path((), error)) from error
    if isinstance(result, _ResponseMixin):
        # Transport metadata is runtime state, not part of the serializable response schema, so it is
        # kept in ``__dict__`` where ``model_dump`` and field iteration never see it.
        result.__dict__["_request_id"] = response.headers.get(REQUEST_ID_HEADER)
        result.__dict__["_raw"] = response
    # The subclass check narrows ResponseT to Response, but decoding preserves the concrete type.
    return cast(ResponseT, result)
