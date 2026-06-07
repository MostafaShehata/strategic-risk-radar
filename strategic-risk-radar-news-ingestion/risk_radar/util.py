import hashlib
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime


def contains_keyword(text: str, keyword: str) -> bool:
    pattern = r"(?<![A-Za-z0-9])" + r"\s+".join(re.escape(part) for part in keyword.split()) + r"(?![A-Za-z0-9])"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


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
            pass
    for date_format in ("%a, %d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(value, date_format).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return None
