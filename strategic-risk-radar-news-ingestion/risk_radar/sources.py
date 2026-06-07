from abc import ABC, abstractmethod
import re
import time
from collections.abc import Iterable
from typing import Any

import feedparser
import httpx

from .models import KeywordResult, KeywordSpec, RawItem, TimeWindow
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
            if response.status_code == 429:
                delay = float(retry_after) if retry_after.isdigit() else 60
            else:
                delay = float(retry_after) if retry_after.isdigit() else max(minimum, 2**attempt)
            time.sleep(delay)
        raise RuntimeError("Request retry loop exited unexpectedly")

    @abstractmethod
    def fetch(self, keywords: tuple[KeywordSpec, ...], window: TimeWindow) -> Iterable[KeywordResult]:
        raise NotImplementedError


class GdeltSource(Source):
    def fetch(self, keywords: tuple[KeywordSpec, ...], window: TimeWindow) -> Iterable[KeywordResult]:
        for keyword in keywords:
            try:
                response = self.request("GET", self.config["url"], params={
                    "query": f"{keyword.gdelt_query} sourcelang:english",
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
                warning = f"Keyword group '{keyword.name}' failed: {exc}"
                print(f"gdelt {warning}", flush=True)
                yield KeywordResult(keyword.name, 1, 0, (), warning)
                continue
            items = tuple(RawItem(
                self.config["id"], "api", stable_id(a.get("url", ""), a.get("title", "")),
                a.get("url", ""), a.get("title", ""), a.get("seendate", ""),
                "",
                parse_datetime(a.get("seendate")), keyword.name, a,
            ) for a in articles)
            yield KeywordResult(keyword.name, 1, len(articles), items)


class GuardianSource(Source):
    def fetch(self, keywords: tuple[KeywordSpec, ...], window: TimeWindow) -> Iterable[KeywordResult]:
        api_key = self.config.get("api_key")
        if not api_key:
            raise SourceSkipped("GUARDIAN_API_KEY is not configured")
        for keyword in keywords:
            response = self.request("GET", self.config["url"], params={
                "api-key": api_key,
                "q": keyword.guardian_query,
                "from-date": window.start.date().isoformat(),
                "to-date": window.end.date().isoformat(),
                "order-by": "newest",
                "page-size": self.config.get("max_records", 50),
                "show-fields": "headline,trailText,bodyText",
                "lang": "en",
            })
            results = response.json().get("response", {}).get("results", [])
            items = []
            for article in results:
                fields = article.get("fields", {})
                title = strip_html(fields.get("headline") or article.get("webTitle", ""))
                summary = strip_html(fields.get("trailText") or fields.get("bodyText", ""))
                body = strip_html(fields.get("bodyText") or summary)
                items.append(RawItem(
                    self.config["id"], "api", article.get("id", stable_id(article.get("webUrl", ""), title)),
                    article.get("webUrl", ""), title, summary, body,
                    parse_datetime(article.get("webPublicationDate")), keyword.name, article,
                ))
            yield KeywordResult(keyword.name, 1, len(results), tuple(items))


class RssSource(Source):
    def fetch(self, keywords: tuple[KeywordSpec, ...], window: TimeWindow) -> Iterable[KeywordResult]:
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
                if any(contains_keyword(f"{title} {summary}", term) for term in keyword.terms):
                    url = entry.get("link", "")
                    body = strip_html(entry.get("content", [{}])[0].get("value", "") if entry.get("content") else summary)
                    items.append(RawItem(
                        self.config["id"], "rss", str(entry.get("id") or stable_id(url, title)),
                        url, title, summary, body,
                        parse_datetime(entry.get("published") or entry.get("updated")),
                        keyword.name, dict(entry),
                    ))
            yield KeywordResult(
                keyword.name, 1 if keyword == keywords[0] else 0, len(entries), tuple(items)
            )


def strip_html(value: str) -> str:
    return re.sub(r"<[^>]+>", "", value or "").strip()


SOURCE_TYPES = {
    "gdelt": GdeltSource,
    "guardian": GuardianSource,
    "rss": RssSource,
}


def build_source(config: dict[str, Any], client: httpx.Client) -> Source:
    return SOURCE_TYPES[config["type"]](config, client)
