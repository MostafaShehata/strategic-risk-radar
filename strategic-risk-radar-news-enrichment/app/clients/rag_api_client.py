from typing import Any

import httpx


class RagApiClient:
    def __init__(self, base_url: str, enabled: bool = True) -> None:
        self.base_url = base_url.rstrip("/")
        self.enabled = enabled

    def index_article(self, source: str, text: str, metadata: dict[str, Any]) -> None:
        if not self.enabled or not text.strip():
            return
        try:
            with httpx.Client(timeout=60) as client:
                client.post(
                    f"{self.base_url}/api/ingest/text",
                    json={
                        "source": source,
                        "text": text,
                        "document_type": "enriched_news",
                        "metadata": metadata,
                    },
                ).raise_for_status()
        except Exception:
            return
