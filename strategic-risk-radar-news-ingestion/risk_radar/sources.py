from abc import ABC, abstractmethod
import time
from collections.abc import Iterable
from typing import Any

import feedparser
import httpx

from .models import KeywordResult, RawItem, TimeWindow
from .util import contains_keyword, parse_datetime, stable_id


class SourceSkipped(Exception):
    """Raised when a configured source cannot run without optional configuration."""


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
    def fetch(self, keywords: tuple[str, ...], window: TimeWindow) -> Iterable[KeywordResult]:
        raise NotImplementedError


class GdeltSource(Source):
    def fetch(self, keywords: tuple[str, ...], window: TimeWindow) -> Iterable[KeywordResult]:
        for keyword in keywords:
            try:
                response = self.request("GET", self.config["url"], params={
                    "query": f'"{keyword}" sourcelang:english',
                    "mode": "artlist", "format": "json",
                    "maxrecords": self.config.get("max_records", 50),
                    "startdatetime": window.start.strftime("%Y%m%d%H%M%S"),
                    "enddatetime": window.end.strftime("%Y%m%d%H%M%S"),
                    "sort": "datedesc",
                })
                articles = [
                    article for article in response.json().get("articles", [])
                    if article.get("language", "").casefold() == "english"
                ]
            except (httpx.HTTPError, ValueError) as exc:
                warning = f"Keyword '{keyword}' failed: {exc}"
                print(f"gdelt {warning}", flush=True)
                yield KeywordResult(keyword, 1, 0, (), warning)
                continue
            items = tuple(RawItem(
                self.config["id"], "api", stable_id(a.get("url", ""), a.get("title", "")),
                a.get("url", ""), a.get("title", ""), a.get("seendate", ""),
                parse_datetime(a.get("seendate")), keyword, a,
            ) for a in articles)
            yield KeywordResult(keyword, 1, len(articles), items)


class ReliefWebSource(Source):
    def fetch(self, keywords: tuple[str, ...], window: TimeWindow) -> Iterable[KeywordResult]:
        if not self.config.get("appname"):
            raise SourceSkipped("RELIEFWEB_APPNAME is not configured")
        for keyword in keywords:
            response = self.request("POST", self.config["url"],
                params={"appname": self.config["appname"]},
                json={"limit": self.config.get("max_records", 50),
                      "query": {"value": f'"{keyword}"'},
                      "filter": {"field": "date.created",
                                 "value": {"from": window.start.isoformat(),
                                           "to": window.end.isoformat()}},
                      "sort": ["date.created:desc"],
                      "fields": {"include": ["title", "url", "body", "date.created"]}})
            records = response.json().get("data", [])
            items = []
            for record in records:
                fields = record.get("fields", {})
                title = fields.get("title", "")
                body = fields.get("body", "")
                if not title.isascii() or not body.isascii():
                    continue
                items.append(RawItem(
                    self.config["id"], "api", str(record.get("id")),
                    fields.get("url", ""), title, body,
                    parse_datetime(fields.get("date", {}).get("created")), keyword, record,
                ))
            yield KeywordResult(keyword, 1, len(records), tuple(items))


class RssSource(Source):
    def fetch(self, keywords: tuple[str, ...], window: TimeWindow) -> Iterable[KeywordResult]:
        response = self.request("GET", self.config["url"])
        entries = []
        for entry in feedparser.parse(response.content).entries:
            published_at = parse_datetime(entry.get("published") or entry.get("updated"))
            if published_at and window.start <= published_at <= window.end:
                entries.append(entry)
        for keyword in keywords:
            items = []
            for entry in entries:
                title, summary = entry.get("title", ""), entry.get("summary", "")
                if not title.isascii() or not summary.isascii():
                    continue
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
