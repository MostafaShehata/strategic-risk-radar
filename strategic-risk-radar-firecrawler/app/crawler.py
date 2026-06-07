import json

import httpx
import trafilatura

from .schemas import CrawlResponse


class ArticleCrawler:
    def __init__(self, timeout_seconds: float = 45) -> None:
        self.timeout_seconds = timeout_seconds

    async def crawl(self, url: str) -> CrawlResponse:
        try:
            html = await self.fetch(url)
        except httpx.TimeoutException as exc:
            return self.error(url, "timeout", exc)
        except httpx.HTTPStatusError as exc:
            status = "blocked" if exc.response.status_code in {401, 403, 429} else "failed"
            return self.error(url, status, exc)
        except httpx.HTTPError as exc:
            return self.error(url, "failed", exc)

        extracted = trafilatura.extract(
            html,
            url=url,
            output_format="json",
            include_comments=False,
            include_tables=False,
            favor_precision=True,
        )
        if not extracted:
            return CrawlResponse(status="empty_content", url=url, error_message="No readable article content extracted")
        data = json.loads(extracted)
        body = str(data.get("text") or "").strip()
        if not body:
            return CrawlResponse(status="empty_content", url=url, error_message="Extracted content was empty")
        return CrawlResponse(
            status="success",
            url=url,
            title=str(data.get("title") or ""),
            body=body,
            language=data.get("language"),
            published_at=data.get("date"),
        )

    async def fetch(self, url: str) -> str:
        headers = {
            "User-Agent": "Strategic-Risk-Radar-Firecrawler/0.1",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        async with httpx.AsyncClient(timeout=self.timeout_seconds, follow_redirects=True, headers=headers) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text

    def error(self, url: str, status: str, exc: Exception) -> CrawlResponse:
        return CrawlResponse(status=status, url=url, error_message=str(exc))
