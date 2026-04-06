from __future__ import annotations

import json
import socket
import time
from typing import Any, Callable, TypeVar
from urllib.error import URLError
from urllib.request import Request, urlopen


NETWORK_RETRY_ATTEMPTS = 4
NETWORK_RETRY_BASE_DELAY_SECONDS = 1.0
TRANSIENT_NETWORK_MARKERS = (
    "temporary failure in name resolution",
    "name or service not known",
    "name resolution",
    "nodename nor servname provided",
    "failed to establish a new connection",
    "max retries exceeded",
    "server not found",
    "connection aborted",
    "connection reset by peer",
    "timed out",
    "timeout",
    "temporarily unavailable",
)
T = TypeVar("T")


class TransientHttpError(RuntimeError):
    def __init__(self, operation: str, attempts: int, cause: Exception):
        detail = str(cause).strip() or cause.__class__.__name__
        super().__init__(
            f"Temporary network or DNS failure during {operation} after {attempts} attempts: {detail}"
        )
        self.operation = operation
        self.attempts = attempts
        self.cause = cause


class JsonHttpClient:
    def __init__(self, timeout: int = 30, user_agent: str = "weekly-journal-digest/0.1.0"):
        self.timeout = timeout
        self.user_agent = user_agent

    def get_json(self, url: str, headers: dict[str, str] | None = None) -> Any:
        request = Request(url, headers=self._build_headers(headers))
        return self._call_with_retry(
            lambda: self._load_json(request),
            operation=f"HTTP GET {url}",
        )

    def post_json(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> Any:
        body = json.dumps(payload).encode("utf-8")
        request = Request(
            url,
            data=body,
            headers=self._build_headers({"Content-Type": "application/json", **(headers or {})}),
            method="POST",
        )
        return self._call_with_retry(
            lambda: self._load_json(request),
            operation=f"HTTP POST {url}",
        )

    def _build_headers(self, extra_headers: dict[str, str] | None = None) -> dict[str, str]:
        return {"User-Agent": self.user_agent, **(extra_headers or {})}

    def _load_json(self, request: Request) -> Any:
        with urlopen(request, timeout=self.timeout) as response:
            return json.load(response)

    def _call_with_retry(self, func: Callable[[], T], operation: str) -> T:
        last_error: Exception | None = None
        for attempt in range(1, NETWORK_RETRY_ATTEMPTS + 1):
            try:
                return func()
            except Exception as exc:
                if not is_transient_network_error(exc):
                    raise
                last_error = exc
                if attempt == NETWORK_RETRY_ATTEMPTS:
                    raise TransientHttpError(operation, attempt, exc) from exc
                time.sleep(NETWORK_RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1)))
        raise TransientHttpError(
            operation,
            NETWORK_RETRY_ATTEMPTS,
            last_error or RuntimeError("unknown network error"),
        )


def is_transient_network_error(exc: BaseException) -> bool:
    for current in _iter_exception_chain(exc):
        if isinstance(current, (socket.gaierror, TimeoutError, ConnectionError)):
            return True
        if isinstance(current, (URLError, OSError)):
            message = str(current).lower()
            if any(marker in message for marker in TRANSIENT_NETWORK_MARKERS):
                return True
    return False


def _iter_exception_chain(exc: BaseException):
    pending = [exc]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        yield current
        if current.__cause__ is not None:
            pending.append(current.__cause__)
        if current.__context__ is not None:
            pending.append(current.__context__)
