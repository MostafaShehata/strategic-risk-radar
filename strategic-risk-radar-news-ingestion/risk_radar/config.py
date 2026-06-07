import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .models import KeywordSpec


@dataclass(frozen=True)
class Settings:
    keywords: tuple[KeywordSpec, ...]
    sources: tuple[dict[str, Any], ...]
    snapshot: dict[str, Any]


def load_settings(path: str | Path) -> Settings:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    keywords = tuple(
        KeywordSpec(
            keyword["name"],
            tuple(keyword["terms"]),
            keyword.get("guardian_query"),
        )
        for keyword in data.get("keywords", [])
    )
    sources = []
    for source in data.get("sources", []):
        if not source.get("enabled", True):
            continue
        resolved = dict(source)
        if env_name := resolved.get("appname_env"):
            resolved["appname"] = os.getenv(env_name, "")
        if env_name := resolved.get("api_key_env"):
            resolved["api_key"] = os.getenv(env_name, resolved.get("api_key", ""))
        sources.append(resolved)
    return Settings(keywords, tuple(sources), data)
