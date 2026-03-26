from __future__ import annotations

import json
from typing import Any
from urllib.request import Request, urlopen


class JsonHttpClient:
    def __init__(self, timeout: int = 30, user_agent: str = "weekly-journal-digest/0.1.0"):
        self.timeout = timeout
        self.user_agent = user_agent

    def get_json(self, url: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
        request = Request(url, headers=self._build_headers(headers))
        with urlopen(request, timeout=self.timeout) as response:
            return json.load(response)

    def post_json(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        request = Request(
            url,
            data=body,
            headers=self._build_headers({"Content-Type": "application/json", **(headers or {})}),
            method="POST",
        )
        with urlopen(request, timeout=self.timeout) as response:
            return json.load(response)

    def _build_headers(self, extra_headers: dict[str, str] | None = None) -> dict[str, str]:
        return {"User-Agent": self.user_agent, **(extra_headers or {})}
