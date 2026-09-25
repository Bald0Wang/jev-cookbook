"""Model resource for the asynchronous client, exposed as `AsyncTypeSafeClient.models`."""

from collections.abc import Mapping

import httpx2
from tenacity import AsyncRetrying

from typesafe_sdk._core.config import Config
from typesafe_sdk._core.endpoints import prepare_models
from typesafe_sdk._core.response_types import ListModelsResponse
from typesafe_sdk._core.retry import RetryPolicy
from typesafe_sdk._core.transport import send_async


class AsyncModels:
    """Access to the models available to the account, reached through `AsyncTypeSafeClient.models`."""

    def __init__(self, config: Config, http_client: httpx2.AsyncClient, retry: AsyncRetrying) -> None:
        self._config = config
        self._http_client = http_client
        self._retry = retry

    async def list(
        self,
        *,
        retry: RetryPolicy | None = None,
        timeout: float | httpx2.Timeout | None = None,
        extra_headers: Mapping[str, str] | None = None,
    ) -> ListModelsResponse:
        """List the models available to the account.

        Args:
            retry: An optional retry policy to override the client-level value for this call only.
            timeout: Per-operation timeout override; `None` inherits the client setting.
            extra_headers: Overrides for additional request headers; authentication, SDK identification,
                and `Accept` remain protected.

        Returns:
            A `ListModelsResponse` whose `models` holds each model's name, description,
            and release date.

        Raises:
            TypeSafeAPIError: The server returns an unsuccessful HTTP response after any retries.
            TypeSafeAPIConnectionError: The request cannot connect or times out after any retries.

        Examples:
            ```python
            from typesafe_sdk import AsyncTypeSafeClient


            async def main() -> None:
                async with AsyncTypeSafeClient() as client:
                    models = await client.models.list()
            ```
        """
        return await send_async(self._http_client, self._retry, prepare_models(self._config, timeout, extra_headers), retry)
