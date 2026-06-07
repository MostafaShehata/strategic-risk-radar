from datetime import datetime, timezone
from html import unescape
import re
from typing import Any
import xml.etree.ElementTree as ET
from urllib.parse import urljoin


def strip_html(value: str) -> str:
    return re.sub(r"<[^>]+>", "", value or "").strip()


def clean_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", unescape(strip_html(value or ""))).strip()


def parse_faa_airport_status(xml_text: str, year: int) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_text)
    notices = []
    for delay_type in root.findall("Delay_type"):
        notice_type = clean_text(delay_type.findtext("Name"))
        for airport in delay_type.findall(".//Airport"):
            code = clean_text(airport.findtext("ARPT"))
            reason = clean_text(airport.findtext("Reason"))
            start = clean_text(airport.findtext("Start"))
            reopen = clean_text(airport.findtext("Reopen"))
            published_at = parse_faa_time(start, year)
            notices.append({
                "title": f"{notice_type}: {code}" if code else notice_type,
                "url": "https://nasstatus.faa.gov/",
                "summary": notice_type,
                "body": " ".join(part for part in (reason, start, reopen) if part),
                "published_at": published_at,
                "airport": code,
                "reason": reason,
                "start": start,
                "reopen": reopen,
            })
    return notices


def parse_faa_time(value: str, year: int) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(f"{value} {year}", "%b %d at %H:%M UTC. %Y").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def parse_wco_newsroom(html: str, base_url: str) -> list[dict[str, Any]]:
    pattern = re.compile(
        r'<li>\s*<div class="dateFields">.*?<p class="news-date date">\s*(?P<date>.*?)\s*</p>'
        r'.*?<a href=[\'"](?P<href>.*?)[\'"] class="headline">\s*(?P<title>.*?)\s*</a>',
        re.IGNORECASE | re.DOTALL,
    )
    return [
        {
            "title": clean_text(match.group("title")),
            "url": urljoin(base_url, match.group("href")),
            "summary": "WCO Newsroom",
            "published_at": parse_wco_date(clean_text(match.group("date"))),
        }
        for match in pattern.finditer(html)
    ]


def parse_wco_date(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%d %B %Y").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def extract_page_body(html: str) -> str:
    match = re.search(r'<div id="contentCol".*?>(?P<body>.*?)<div id="footerWrapper">', html, re.IGNORECASE | re.DOTALL)
    return clean_text(match.group("body") if match else html)[:20000]
