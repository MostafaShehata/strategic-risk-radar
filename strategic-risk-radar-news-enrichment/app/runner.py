import time
import traceback

from .clients import FirecrawlerClient, OllamaClient, RagApiClient
from .config import settings
from .graph import build_graph
from .models import EnrichmentState
from .nodes import EnrichmentNodes
from .repository import EnrichmentRepository


class EnrichmentRunner:
    def __init__(self) -> None:
        self.repository = EnrichmentRepository(settings.database_url)
        self.graph = build_graph(
            EnrichmentNodes(
                repository=self.repository,
                firecrawler=FirecrawlerClient(settings.firecrawler_url, settings.firecrawler_timeout_seconds),
                ollama=OllamaClient(
                    settings.model_base_url,
                    settings.model_name,
                    settings.enable_llm,
                    settings.model_request_timeout_seconds,
                    settings.model_num_predict,
                ),
                topic_ollama=OllamaClient(
                    settings.model_base_url,
                    settings.model_name,
                    settings.enable_topic_llm,
                    settings.model_request_timeout_seconds,
                    settings.model_num_predict,
                ),
                rag=RagApiClient(settings.rag_api_url, settings.enable_rag_indexing),
            )
        )

    def run_once(self) -> tuple[int, int, int]:
        run_id = self.repository.begin_run(settings.model_name)
        processed = success = failed = 0
        run_error = None
        try:
            recovered = self.repository.reset_stale_claims(settings.claim_timeout_seconds)
            if recovered:
                print(f"recovered stale enrichment claims count={recovered}", flush=True)
            articles = self.repository.claim_articles(settings.enrichment_batch_size, run_id)
            for article in articles:
                processed += 1
                try:
                    self.graph.invoke(EnrichmentState(raw=article))
                    success += 1
                    print(f"enrichment completed raw_item_id={article.id}", flush=True)
                except Exception as exc:
                    failed += 1
                    self.repository.mark_failed(article.id, str(exc))
                    print(f"enrichment failed raw_item_id={article.id}: {exc}", flush=True)
            return processed, success, failed
        except Exception as exc:
            run_error = traceback.format_exc()
            raise exc
        finally:
            self.repository.finish_run(run_id, processed, success, failed, run_error)

    def run_forever(self) -> None:
        while True:
            processed, success, failed = self.run_once()
            print(
                f"enrichment cycle completed processed={processed} success={success} failed={failed} "
                f"sleep={settings.enrichment_interval_seconds}s",
                flush=True,
            )
            time.sleep(settings.enrichment_interval_seconds)
