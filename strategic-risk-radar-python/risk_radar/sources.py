from abc import ABC, abstractmethod
import time
from collections.abc import Iterable
from typing import Any

import feedparser
import httpx

from .models import KeywordResult, RawItem
from .util import contains_keyword, parse_datetime, stable_id


class Source(ABC):
    def __init__(self, config: dict[str, Any], client: httpx.Client):
        self.config = config
        self.client = client
        self.last_request_at: float | None = None

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        minimum = float(self.config.get("minimum_request_interval_seconds", 0))
        if self.last_request_at is not None:
            time.sleep(max(0, minimum - (time.monotonic() - self.last_request_at)))
        attempts = int(self.config.get("retry_attempts", 3))
        for attempt in range(attempts):
            self.last_request_at = time.monotonic()
            response = self.client.request(method, url, **kwargs)
            if response.status_code not in {429, 500, 502, 503, 504}:
                response.raise_for_status()
                return response
            if attempt == attempts - 1:
                response.raise_for_status()
            retry_after = response.headers.get("Retry-After", "")
            delay = float(retry_after) if retry_after.isdigit() else max(minimum, 2**attempt)
            time.sleep(delay)
        raise RuntimeError("Request retry loop exited unexpectedly")

    @abstractmethod
    def fetch(self, keywords: tuple[str, ...]) -> Iterable[KeywordResult]:
        raise NotImplementedError


class GdeltSource(Source):
    def fetch(self, keywords: tuple[str, ...]) -> Iterable[KeywordResult]:
        for keyword in keywords:
            response = self.request("GET", self.config["url"], params={
                "query": f'"{keyword}"', "mode": "artlist", "format": "json",
                "maxrecords": self.config.get("max_records", 50),
                "timespan": self.config.get("lookback", "24h"), "sort": "datedesc",
            })
            articles = response.json().get("articles", [])
            items = tuple(RawItem(
                self.config["id"], "api", stable_id(a.get("url", ""), a.get("title", "")),
                a.get("url", ""), a.get("title", ""), a.get("seendate", ""),
                parse_datetime(a.get("seendate")), keyword, a,
            ) for a in articles)
            yield KeywordResult(keyword, 1, len(articles), items)


class ReliefWebSource(Source):
    def fetch(self, keywords: tuple[str, ...]) -> Iterable[KeywordResult]:
        if not self.config.get("appname"):
            raise ValueError("RELIEFWEB_APPNAME must be set for ReliefWeb")
        for keyword in keywords:
            response = self.request("POST", self.config["url"],
                params={"appname": self.config["appname"]},
                json={"limit": self.config.get("max_records", 50),
                      "query": {"value": f'"{keyword}"'},
                      "sort": ["date.created:desc"],
                      "fields": {"include": ["title", "url", "body", "date.created"]}})
            records = response.json().get("data", [])
            items = []
            for record in records:
                fields = record.get("fields", {})
                items.append(RawItem(
                    self.config["id"], "api", str(record.get("id")),
                    fields.get("url", ""), fields.get("title", ""), fields.get("body", ""),
                    parse_datetime(fields.get("date", {}).get("created")), keyword, record,
                ))
            yield KeywordResult(keyword, 1, len(records), tuple(items))


class RssSource(Source):
    def fetch(self, keywords: tuple[str, ...]) -> Iterable[KeywordResult]:
        response = self.request("GET", self.config["url"])
        entries = feedparser.parse(response.content).entries
        for keyword in keywords:
            items = []
            for entry in entries:
                title, summary = entry.get("title", ""), entry.get("summary", "")
                if contains_keyword(f"{title} {summary}", keyword):
                    url = entry.get("link", "")
                    items.append(RawItem(
                        self.config["id"], "rss", str(entry.get("id") or stable_id(url, title)),
                        url, title, summary,
                        parse_datetime(entry.get("published") or entry.get("updated")),
                        keyword, dict(entry),
                    ))
            yield KeywordResult(keyword, 1 if keyword == keywords[0] else 0, len(entries), tuple(items))


SOURCE_TYPES = {"gdelt": GdeltSource, "reliefweb": ReliefWebSource, "rss": RssSource}


def build_source(config: dict[str, Any], client: httpx.Client) -> Source:
    return SOURCE_TYPES[config["type"]](config, client)
