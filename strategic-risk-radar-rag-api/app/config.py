from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    qdrant_url: str = "http://strategic-risk-radar-vectordb:6333"
    rag_collection_name: str = "strategic_risk_radar_docs"
    embedding_model_name: str = "BAAI/bge-small-en-v1.5"
    rag_vector_size: int = 384
    rag_top_k: int = 5
    chunk_max_words: int = 180


settings = Settings()
