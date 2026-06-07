from ..config import settings
from ..models import EnrichmentState
from .base import BaseAgent


class NormalizeAgent(BaseAgent):
    def __call__(self, state: EnrichmentState) -> EnrichmentState:
        raw = state["raw"]
        body = raw.body.strip()
        body_source = "source_api" if body else "none"
        fetch_status = "not_needed" if len(body) >= settings.crawler_min_body_chars else "not_attempted"
        fetch_error = None
        if len(body) < settings.crawler_min_body_chars and raw.url:
            result = self.firecrawler.crawl(raw.url, raw.source_id, str(raw.id))
            self.repository.save_content_fetch(raw.id, raw.url, result)
            fetch_status = result.get("status", "failed")
            fetch_error = result.get("error_message")
            if result.get("body"):
                body = result["body"]
                body_source = "crawler"
            if result.get("title") and len(result["title"]) > len(state.get("title", "")):
                state["title"] = result["title"]
        language = self.detect_language(" ".join([state.get("title", ""), state.get("summary", ""), body]))
        return {
            **state,
            "language": language,
            "normalized_body": self.clean_text(body),
            "body_source": body_source,
            "content_fetch_status": fetch_status,
            "content_fetch_error": fetch_error,
        }
