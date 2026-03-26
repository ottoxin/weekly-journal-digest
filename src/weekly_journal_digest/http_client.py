from __future__ import annotations

import json
from typing import Any
from urllib.request import Request, urlopen


class JsonHttpClient:
    def __init__(self, timeout: int = 30, user_agent: str = "weekly-journal-digest/0.1.0"):
        self.timeout = timeout
        self.user_agent = user_agent

    def get_json(self, url: str) -> dict[str, Any]:
        request = Request(url, headers={"User-Agent": self.user_agent})
        with urlopen(request, timeout=self.timeout) as response:
            return json.load(response)
