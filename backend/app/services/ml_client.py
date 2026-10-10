from __future__ import annotations

import asyncio
import re
from collections.abc import Mapping
from time import monotonic
from typing import Any
from uuid import uuid4

import httpx

_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_CIRCUIT_FAILURE_LIMIT = 3
_CIRCUIT_OPEN_SECONDS = 30.0


class MLServiceError(Exception):
    """Safe upstream failure with a stable backend error code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class MLServiceClient:
    """HTTP-only client for the optional internal inference service."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        request_timeout_seconds: float = 10.0,
        status_timeout_seconds: float = 5.0,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._request_timeout_seconds = request_timeout_seconds
        self._status_timeout_seconds = status_timeout_seconds
        self._http = client or httpx.AsyncClient(
            timeout=httpx.Timeout(request_timeout_seconds),
        )
        self._owns_client = client is None
        self._failure_count = 0
        self._open_until = 0.0
        self._state_lock = asyncio.Lock()

    async def close(self) -> None:
        if self._owns_client:
            await self._http.aclose()

    async def health(self, request_id: str | None = None) -> dict[str, Any]:
        return await self._request_json(
            "GET",
            "/health",
            request_id=request_id,
            timeout=self._status_timeout_seconds,
        )

    async def ready(self, request_id: str | None = None) -> dict[str, Any]:
        return await self._request_json(
            "GET",
            "/ready",
            request_id=request_id,
            timeout=self._status_timeout_seconds,
        )

    async def model_info(self, request_id: str | None = None) -> dict[str, Any]:
        return await self._request_json(
            "GET",
            "/v1/model-info",
            request_id=request_id,
            authenticated=True,
        )

    async def score(
        self,
        payload: Mapping[str, Any],
        request_id: str | None = None,
    ) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            "/v1/score",
            request_id=request_id,
            authenticated=True,
            json=dict(payload),
        )

    async def score_batch(
        self,
        payload: Mapping[str, Any],
        request_id: str | None = None,
    ) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            "/v1/score/batch",
            request_id=request_id,
            authenticated=True,
            json=dict(payload),
        )

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        request_id: str | None,
        authenticated: bool = False,
        timeout: float | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        await self._ensure_circuit_closed()
        headers = {"X-Request-ID": self._request_id(request_id)}
        if authenticated:
            headers["X-Service-Key"] = self._api_key

        try:
            response = await self._send_with_connection_retry(
                method,
                path,
                headers=headers,
                timeout=timeout or self._request_timeout_seconds,
                json=json,
            )
        except httpx.TimeoutException as error:
            await self._record_failure()
            raise MLServiceError("ML_WAKING", "ML service request timed out") from error
        except httpx.ConnectError as error:
            await self._record_failure()
            raise MLServiceError(
                "ML_WAKING",
                "ML service could not be reached",
            ) from error
        except httpx.RequestError as error:
            await self._record_failure()
            raise MLServiceError(
                "ML_UNAVAILABLE",
                "ML service request failed",
            ) from error

        if not response.is_success:
            await self._record_failure()
            raise MLServiceError(
                "ML_UNAVAILABLE",
                "ML service returned an error",
            )
        try:
            value = response.json()
        except ValueError as error:
            await self._record_failure()
            raise MLServiceError(
                "ML_UNAVAILABLE",
                "ML service returned an invalid response",
            ) from error
        if not isinstance(value, dict):
            await self._record_failure()
            raise MLServiceError(
                "ML_UNAVAILABLE",
                "ML service returned an invalid response",
            )
        await self._record_success()
        return value

    async def _send_with_connection_retry(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str],
        timeout: float,
        json: dict[str, Any] | None,
    ) -> httpx.Response:
        for attempt in range(2):
            try:
                return await self._http.request(
                    method,
                    f"{self._base_url}{path}",
                    headers=headers,
                    timeout=timeout,
                    json=json,
                )
            except httpx.ConnectError:
                if attempt == 1:
                    raise
        raise RuntimeError("unreachable connection retry state")

    @staticmethod
    def _request_id(value: str | None) -> str:
        if value is not None and _REQUEST_ID_PATTERN.fullmatch(value):
            return value
        return str(uuid4())

    async def _ensure_circuit_closed(self) -> None:
        async with self._state_lock:
            if self._open_until > monotonic():
                raise MLServiceError(
                    "ML_UNAVAILABLE",
                    "ML service circuit breaker is open",
                )
            if self._open_until:
                self._open_until = 0.0
                self._failure_count = 0

    async def _record_failure(self) -> None:
        async with self._state_lock:
            self._failure_count += 1
            if self._failure_count >= _CIRCUIT_FAILURE_LIMIT:
                self._open_until = monotonic() + _CIRCUIT_OPEN_SECONDS

    async def _record_success(self) -> None:
        async with self._state_lock:
            self._failure_count = 0
            self._open_until = 0.0
