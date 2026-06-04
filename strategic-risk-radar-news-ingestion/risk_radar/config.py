import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class Settings:
    keywords: tuple[str, ...]
    sources: tuple[dict[str, Any], ...]
    snapshot: dict[str, Any]


def load_settings(path: str | Path) -> Settings:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    sources = []
    for source in data.get("sources", []):
        if not source.get("enabled", True):
            continue
        resolved = dict(source)
        if env_name := resolved.get("appname_env"):
            resolved["appname"] = os.getenv(env_name, "")
        sources.append(resolved)
    return Settings(tuple(data.get("keywords", [])), tuple(sources), data)

