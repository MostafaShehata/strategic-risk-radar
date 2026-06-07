from typing import Any
from uuid import uuid4

from qdrant_client import QdrantClient
from qdrant_client.http import models

from .embeddings import FastEmbedTextEmbedder
from .schemas import SearchHit


class QdrantRagStore:
    def __init__(
        self,
        url: str,
        collection_name: str,
        vector_size: int,
        embedder: FastEmbedTextEmbedder,
    ) -> None:
        self.url = url
        self.collection_name = collection_name
        self.vector_size = vector_size
        self.embedder = embedder

    def client(self) -> QdrantClient:
        return QdrantClient(url=self.url)

    def ensure_collection(self) -> None:
        client = self.client()
        existing = {collection.name for collection in client.get_collections().collections}
        if self.collection_name in existing:
            return
        client.create_collection(
            collection_name=self.collection_name,
            vectors_config=models.VectorParams(
                size=self.vector_size,
                distance=models.Distance.COSINE,
            ),
        )

    def upsert_chunks(
        self,
        source: str,
        document_type: str,
        chunks: list[str],
        metadata: dict[str, Any],
    ) -> int:
        self.ensure_collection()
        points = [
            models.PointStruct(
                id=str(uuid4()),
                vector=self.embedder.embed(chunk),
                payload={
                    "source": source,
                    "document_type": document_type,
                    "chunk_index": index,
                    "text": chunk,
                    "metadata": metadata,
                },
            )
            for index, chunk in enumerate(chunks)
        ]
        if points:
            self.client().upsert(collection_name=self.collection_name, points=points)
        return len(points)

    def search(self, query: str, top_k: int, filters: dict[str, Any] | None = None) -> list[SearchHit]:
        self.ensure_collection()
        hits = self.client().search(
            collection_name=self.collection_name,
            query_vector=self.embedder.embed(query),
            limit=top_k,
            query_filter=self.build_filter(filters or {}),
            with_payload=True,
        )
        return [self.to_hit(hit) for hit in hits]

    def status(self) -> dict[str, Any]:
        self.ensure_collection()
        client = self.client()
        collection = client.get_collection(self.collection_name)
        document_types: dict[str, int] = {}
        sources: dict[str, int] = {}
        indexed_articles: set[str] = set()
        latest_indexed_at = ""
        next_offset = None
        scanned = 0
        while scanned < 5000:
            points, next_offset = client.scroll(
                collection_name=self.collection_name,
                limit=500,
                offset=next_offset,
                with_payload=True,
                with_vectors=False,
            )
            if not points:
                break
            for point in points:
                payload = point.payload or {}
                metadata = dict(payload.get("metadata") or {})
                document_type = str(payload.get("document_type") or "unknown")
                source = str(payload.get("source") or "unknown")
                document_types[document_type] = document_types.get(document_type, 0) + 1
                sources[source] = sources.get(source, 0) + 1
                article_id = str(metadata.get("enriched_news_item_id") or metadata.get("raw_news_item_id") or "")
                if article_id:
                    indexed_articles.add(article_id)
                indexed_at = str(metadata.get("indexed_at") or metadata.get("created_at") or "")
                if indexed_at and indexed_at > latest_indexed_at:
                    latest_indexed_at = indexed_at
            scanned += len(points)
            if next_offset is None:
                break
        return {
            "status": "ok",
            "collection": self.collection_name,
            "qdrant_url": self.url,
            "vector_size": self.vector_size,
            "points_count": collection.points_count or 0,
            "indexed_article_count": len(indexed_articles),
            "scanned_points": scanned,
            "scan_limited": bool(next_offset),
            "document_types": document_types,
            "sources": dict(sorted(sources.items(), key=lambda item: item[1], reverse=True)[:10]),
            "latest_indexed_at": latest_indexed_at,
        }

    def build_filter(self, filters: dict[str, Any]) -> models.Filter | None:
        must = [
            models.FieldCondition(key=f"metadata.{key}", match=models.MatchValue(value=value))
            for key, value in filters.items()
            if value not in (None, "")
        ]
        return models.Filter(must=must) if must else None

    def to_hit(self, hit) -> SearchHit:
        payload = hit.payload or {}
        return SearchHit(
            source=str(payload.get("source", "")),
            document_type=str(payload.get("document_type", "")),
            chunk_index=int(payload.get("chunk_index", 0)),
            score=float(hit.score or 0),
            text=str(payload.get("text", "")),
            metadata=dict(payload.get("metadata") or {}),
        )
