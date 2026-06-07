import time
from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Any

import feedparser
import httpx

from .models import KeywordResult, KeywordSpec, RawItem, TimeWindow
from .source_parsers import extract_page_body, parse_faa_airport_status, parse_wco_newsroom, strip_html
from .util import contains_keyword, parse_datetime, stable_id


class SourceSkipped(Exception):
    """Raised when a configured source cannot run without optional configuration."""


class Source(ABC):
    source_type = "api"

    def __init__(self, config: dict[str, Any], client: httpx.Client):
        self.config = config
        self.client = client
        self.last_request_at: float | None = None

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        self._apply_headers(kwargs)
        minimum_interval = float(self.config.get("minimum_request_interval_seconds", 0))
        self._wait_for_rate_limit(minimum_interval)
        return self._request_with_retries(method, url, minimum_interval, kwargs)

    def _apply_headers(self, kwargs: dict[str, Any]) -> None:
        headers = dict(self.config.get("headers", {}))
        headers.update(kwargs.pop("headers", {}))
        if headers:
            kwargs["headers"] = headers

    def _wait_for_rate_limit(self, minimum_interval: float) -> None:
        if self.last_request_at is None:
            return
        elapsed = time.monotonic() - self.last_request_at
        time.sleep(max(0, minimum_interval - elapsed))

    def _request_with_retries(
        self,
        method: str,
        url: str,
        minimum_interval: float,
        kwargs: dict[str, Any],
    ) -> httpx.Response:
        attempts = int(self.config.get("retry_attempts", 3))
        retry_statuses = {429, 500, 502, 503, 504}
        for attempt in range(attempts):
            self.last_request_at = time.monotonic()
            response = self.client.request(method, url, **kwargs)
            if response.status_code not in retry_statuses:
                response.raise_for_status()
                return response
            if attempt == attempts - 1:
                response.raise_for_status()
            time.sleep(self._retry_delay(response, attempt, minimum_interval))
        raise RuntimeError("Request retry loop exited unexpectedly")

    @staticmethod
    def _retry_delay(response: httpx.Response, attempt: int, minimum_interval: float) -> float:
        retry_after = response.headers.get("Retry-After", "")
        if retry_after.isdigit():
            return float(retry_after)
        if response.status_code == 429:
            return 60
        return max(minimum_interval, 2**attempt)

    @abstractmethod
    def fetch(self, keywords: tuple[KeywordSpec, ...], window: TimeWindow) -> Iterable[KeywordResult]:
        raise NotImplementedError


class GdeltSource(Source):
    def fetch(self, keywords: tuple[KeywordSpec, ...], window: TimeWindow) -> Iterable[KeywordResult]:
        for keyword in keywords:
            yield self._fetch_keyword(keyword, window)

    def _fetch_keyword(self, keyword: KeywordSpec, window: TimeWindow) -> KeywordResult:
        try:
            response = self.request("GET", self.config["url"], params=self._params(keyword, window))
            articles = [
                article for article in response.json().get("articles", [])
                if article.get("language", "").casefold() == "english"
            ]
        except (httpx.HTTPError, ValueError) as exc:
            warning = f"Keyword group '{keyword.name}' failed: {exc}"
            print(f"gdelt {warning}", flush=True)
            return KeywordResult(keyword.name, 1, 0, (), warning)
        return KeywordResult(keyword.name, 1, len(articles), self._items(keyword, articles))

    def _params(self, keyword: KeywordSpec, window: TimeWindow) -> dict[str, Any]:
        return {
            "query": f"{keyword.gdelt_query} sourcelang:english",
            "mode": "artlist",
            "format": "json",
            "maxrecords": self.config.get("max_records", 50),
            "startdatetime": window.start.strftime("%Y%m%d%H%M%S"),
            "enddatetime": window.end.strftime("%Y%m%d%H%M%S"),
            "sort": "datedesc",
        }

    def _items(self, keyword: KeywordSpec, articles: list[dict[str, Any]]) -> tuple[RawItem, ...]:
        return tuple(
            RawItem(
                self.config["id"],
                "api",
                stable_id(article.get("url", ""), article.get("title", "")),
                article.get("url", ""),
                article.get("title", ""),
                article.get("seendate", ""),
                "",
                parse_datetime(article.get("seendate")),
                keyword.name,
                article,
            )
            for article in articles
        )


class GuardianSource(Source):
    def fetch(self, keywords: tuple[KeywordSpec, ...], window: TimeWindow) -> Iterable[KeywordResult]:
        api_key = self.config.get("api_key")
        if not api_key:
            raise SourceSkipped("GUARDIAN_API_KEY is not configured")
        for keyword in keywords:
            yield self._fetch_keyword(api_key, keyword, window)

    def _fetch_keyword(self, api_key: str, keyword: KeywordSpec, window: TimeWindow) -> KeywordResult:
        response = self.request("GET", self.config["url"], params={
            "api-key": api_key,
            "q": keyword.guardian_query,
            "from-date": window.start.date().isoformat(),
            "to-date": window.end.date().isoformat(),
            "order-by": "newest",
            "page-size": self._page_size(),
            "show-fields": "headline,trailText,bodyText",
            "lang": "en",
        })
        results = response.json().get("response", {}).get("results", [])
        return KeywordResult(keyword.name, 1, len(results), self._items(keyword, results))

    def _page_size(self) -> int:
        return min(int(self.config.get("max_records", 50)), 200)

    def _items(self, keyword: KeywordSpec, articles: list[dict[str, Any]]) -> tuple[RawItem, ...]:
        return tuple(self._item(keyword, article) for article in articles)

    def _item(self, keyword: KeywordSpec, article: dict[str, Any]) -> RawItem:
        fields = article.get("fields", {})
        title = strip_html(fields.get("headline") or article.get("webTitle", ""))
        summary = strip_html(fields.get("trailText") or fields.get("bodyText", ""))
        body = strip_html(fields.get("bodyText") or summary)
        return RawItem(
            self.config["id"],
            "api",
            article.get("id", stable_id(article.get("webUrl", ""), title)),
            article.get("webUrl", ""),
            title,
            summary,
            body,
            parse_datetime(article.get("webPublicationDate")),
            keyword.name,
            article,
        )


class RssSource(Source):
    source_type = "rss"

    def fetch(self, keywords: tuple[KeywordSpec, ...], window: TimeWindow) -> Iterable[KeywordResult]:
        entries = self._window_entries(window)
        for keyword in keywords:
            items = tuple(self._matching_items(keyword, entries))
            yield KeywordResult(keyword.name, 1 if keyword == keywords[0] else 0, len(entries), items)

    def _window_entries(self, window: TimeWindow) -> list[dict[str, Any]]:
        response = self.request("GET", self.config["url"])
        entries = []
        for entry in feedparser.parse(response.content).entries:
            published_at = parse_datetime(entry.get("published") or entry.get("updated"))
            if published_at and window.start <= published_at <= window.end:
                entries.append(entry)
        return entries

    def _matching_items(self, keyword: KeywordSpec, entries: list[dict[str, Any]]) -> Iterable[RawItem]:
        for entry in entries:
            title = entry.get("title", "")
            summary = entry.get("summary", "")
            if not any(contains_keyword(f"{title} {summary}", term) for term in keyword.terms):
                continue
            url = entry.get("link", "")
            body = strip_html(entry.get("content", [{}])[0].get("value", "") if entry.get("content") else summary)
            yield RawItem(
                self.config["id"],
                self.source_type,
                str(entry.get("id") or stable_id(url, title)),
                url,
                title,
                summary,
                body,
                parse_datetime(entry.get("published") or entry.get("updated")),
                keyword.name,
                dict(entry),
            )


class StateTravelAdvisoriesSource(RssSource):
    source_type = "government_advisory"


class FaaAirportStatusSource(Source):
    source_type = "aviation_notice"

    def fetch(self, keywords: tuple[KeywordSpec, ...], window: TimeWindow) -> Iterable[KeywordResult]:
        candidates = self._candidates(window)
        for keyword in keywords:
            items = tuple(self._matching_items(keyword, candidates))
            yield KeywordResult(keyword.name, 1 if keyword == keywords[0] else 0, len(candidates), items)

    def _candidates(self, window: TimeWindow) -> list[dict[str, Any]]:
        response = self.request("GET", self.config["url"])
        return [
            item for item in parse_faa_airport_status(response.text, window.end.year)
            if item["published_at"] is None or window.start <= item["published_at"] <= window.end
        ]

    def _matching_items(self, keyword: KeywordSpec, candidates: list[dict[str, Any]]) -> Iterable[RawItem]:
        for candidate in candidates:
            title = str(candidate["title"])
            body = str(candidate.get("body") or "")
            if not any(contains_keyword(f"{title} {body}", term) for term in keyword.terms):
                continue
            yield RawItem(
                self.config["id"],
                self.source_type,
                stable_id(str(candidate["url"]), title),
                str(candidate["url"]),
                title,
                str(candidate.get("summary") or ""),
                body,
                candidate["published_at"],
                keyword.name,
                candidate,
            )


class WcoCustomsAnnouncementsSource(Source):
    source_type = "customs_announcement"

    def fetch(self, keywords: tuple[KeywordSpec, ...], window: TimeWindow) -> Iterable[KeywordResult]:
        candidates = self._candidates(window)
        body_cache = self._body_cache(candidates)
        for keyword in keywords:
            items = tuple(self._matching_items(keyword, candidates, body_cache))
            yield KeywordResult(keyword.name, 1 if keyword == keywords[0] else 0, len(candidates), items)

    def _candidates(self, window: TimeWindow) -> list[dict[str, Any]]:
        response = self.request("GET", self.config["url"])
        candidates = [
            item for item in parse_wco_newsroom(response.text, self.config["url"])
            if item["published_at"] is None or window.start <= item["published_at"] <= window.end
        ]
        return candidates[:int(self.config.get("max_records", 20))]

    def _body_cache(self, candidates: list[dict[str, Any]]) -> dict[str, str]:
        bodies = {}
        for candidate in candidates:
            url = str(candidate["url"])
            try:
                bodies[url] = extract_page_body(self.request("GET", url).text)
            except httpx.HTTPError as exc:
                print(f"wco detail fetch failed for {url}: {exc}", flush=True)
                bodies[url] = ""
        return bodies

    def _matching_items(
        self,
        keyword: KeywordSpec,
        candidates: list[dict[str, Any]],
        body_cache: dict[str, str],
    ) -> Iterable[RawItem]:
        for candidate in candidates:
            title = str(candidate["title"])
            body = body_cache.get(str(candidate["url"]), "")
            if not any(contains_keyword(f"{title} {body}", term) for term in keyword.terms):
                continue
            yield RawItem(
                self.config["id"],
                self.source_type,
                stable_id(str(candidate["url"]), title),
                str(candidate["url"]),
                title,
                str(candidate.get("summary") or ""),
                body,
                candidate["published_at"],
                keyword.name,
                candidate,
            )


SOURCE_TYPES = {
    "gdelt": GdeltSource,
    "guardian": GuardianSource,
    "rss": RssSource,
    "state_travel_advisories": StateTravelAdvisoriesSource,
    "faa_airport_status": FaaAirportStatusSource,
    "wco_customs": WcoCustomsAnnouncementsSource,
}


def build_source(config: dict[str, Any], client: httpx.Client) -> Source:
    return SOURCE_TYPES[config["type"]](config, client)
