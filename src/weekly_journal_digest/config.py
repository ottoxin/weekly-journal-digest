from __future__ import annotations

from pathlib import Path

import yaml

from .models import AppConfig, SourceConfig


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    sources = [
        SourceConfig(
            id=item["id"],
            journal=item["journal"],
            category=item["category"],
            adapter=item.get("adapter", "crossref"),
            issns=list(item.get("issns", [])),
            title_query=item.get("title_query"),
            allowed_article_types=list(item.get("allowed_article_types", ["journal-article"])),
            exclude_title_prefixes=list(item.get("exclude_title_prefixes", [])),
            require_social_science_match=bool(item.get("require_social_science_match", False)),
        )
        for item in raw["sources"]
    ]
    return AppConfig(
        timezone=raw.get("timezone", "America/Chicago"),
        default_lookback_days=int(raw.get("default_lookback_days", 28)),
        state_dir=raw.get("state_dir", ".state"),
        recipients_file=raw.get("recipients_file", "config/recipients.json"),
        social_science_keywords=list(raw.get("social_science_keywords", [])),
        sources=sources,
    )
