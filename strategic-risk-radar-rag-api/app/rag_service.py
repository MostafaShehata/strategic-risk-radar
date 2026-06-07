from typing import Any

from .config import settings
from .document_loader import DocumentParser, TextChunker
from .embeddings import FastEmbedTextEmbedder
from .schemas import IngestResponse, SearchHit
from .vector_store import QdrantRagStore


class RagIngestionService:
    def __init__(self, parser: DocumentParser, chunker: TextChunker, store: QdrantRagStore) -> None:
        self.parser = parser
        self.chunker = chunker
        self.store = store

    def ingest_text(
        self,
        source: str,
        text: str,
        document_type: str,
        metadata: dict[str, Any],
    ) -> IngestResponse:
        chunks = self.chunker.chunk_text(text)
        indexed = self.store.upsert_chunks(source, document_type, chunks, metadata)
        return IngestResponse(
            source=source,
            document_type=document_type,
            chunks_indexed=indexed,
            collection=settings.rag_collection_name,
        )

    def ingest_file(
        self,
        filename: str,
        content: bytes,
        content_type: str | None,
        source: str,
        metadata: dict[str, Any],
    ) -> IngestResponse:
        document_type, text = self.parser.parse_bytes(filename, content, content_type)
        return self.ingest_text(source or filename, text, document_type, metadata)

    def search(self, query: str, top_k: int, filters: dict[str, Any]) -> list[SearchHit]:
        return self.store.search(query, top_k, filters)


rag_service = RagIngestionService(
    parser=DocumentParser(),
    chunker=TextChunker(settings.chunk_max_words),
    store=QdrantRagStore(
        url=settings.qdrant_url,
        collection_name=settings.rag_collection_name,
        vector_size=settings.rag_vector_size,
        embedder=FastEmbedTextEmbedder(settings.embedding_model_name),
    ),
)
