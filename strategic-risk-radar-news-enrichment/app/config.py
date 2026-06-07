from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    firecrawler_url: str = "http://firecrawler:8300"
    rag_api_url: str = "http://rag-api:8100"
    model_base_url: str = "http://model:11434"
    model_name: str = "deepseek-r1:1.5b"
    enrichment_interval_seconds: int = 300
    enrichment_batch_size: int = 2
    crawler_min_body_chars: int = 400
    topic_match_threshold: float = 0.90
    enable_llm: bool = False
    enable_rag_indexing: bool = True
    model_request_timeout_seconds: int = 90
    model_num_predict: int = 350
    claim_timeout_seconds: int = 1800


settings = Settings()
