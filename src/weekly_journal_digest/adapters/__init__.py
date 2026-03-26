from __future__ import annotations

from ..crossref import CrossrefClient
from ..http_client import JsonHttpClient
from .crossref import CrossrefAdapter


def build_adapter_registry(mailto: str | None = None) -> dict[str, object]:
    client = CrossrefClient(http_client=JsonHttpClient(), mailto=mailto)
    return {
        "crossref": CrossrefAdapter(client),
    }
