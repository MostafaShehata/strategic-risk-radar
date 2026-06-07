from typing import Any

import httpx


class FirecrawlerClient:
    def __init__(self, base_url: str, timeout_seconds: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def crawl(self, url: str, source_id: str, raw_news_item_id: str) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(
                f"{self.base_url}/api/crawl",
                json={"url": url, "source_id": source_id, "raw_news_item_id": raw_news_item_id},
            )
            response.raise_for_status()
            return response.json()
