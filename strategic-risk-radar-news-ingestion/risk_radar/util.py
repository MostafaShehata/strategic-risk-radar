import hashlib
from datetime import datetime
from email.utils import parsedate_to_datetime


def contains_keyword(text: str, keyword: str) -> bool:
    return keyword.casefold() in text.casefold()


def stable_id(*parts: str) -> str:
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            return parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None

