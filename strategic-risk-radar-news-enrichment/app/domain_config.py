import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .config import settings


@lru_cache(maxsize=1)
def enrichment_config() -> dict[str, Any]:
    path = Path(settings.enrichment_config_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    with path.open(encoding="utf-8") as config_file:
        return json.load(config_file)


def business_context() -> str:
    return str(enrichment_config().get("business_context", "")).strip()


def kpi_catalog_text() -> str:
    catalog = enrichment_config().get("kpi_catalog", [])
    if isinstance(catalog, list):
        return ", ".join(str(item).strip() for item in catalog if str(item).strip())
    return str(catalog).strip()
