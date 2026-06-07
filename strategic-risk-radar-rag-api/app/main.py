import json
from typing import Annotated

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .rag_service import rag_service
from .schemas import IngestResponse, IngestTextRequest, SearchRequest, SearchResponse


app = FastAPI(title="Strategic Risk Radar RAG API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    rag_service.store.ensure_collection()
    return {"status": "ok", "collection": settings.rag_collection_name}


@app.post("/api/ingest/text", response_model=IngestResponse)
def ingest_text(request: IngestTextRequest) -> IngestResponse:
    return rag_service.ingest_text(
        source=request.source,
        text=request.text,
        document_type=request.document_type,
        metadata=request.metadata,
    )


@app.post("/api/ingest/file", response_model=IngestResponse)
async def ingest_file(
    file: Annotated[UploadFile, File()],
    source: Annotated[str, Form()] = "",
    metadata_json: Annotated[str, Form()] = "{}",
) -> IngestResponse:
    metadata = json.loads(metadata_json or "{}")
    return rag_service.ingest_file(
        filename=file.filename or "uploaded-document",
        content=await file.read(),
        content_type=file.content_type,
        source=source,
        metadata=metadata,
    )


@app.post("/api/search", response_model=SearchResponse)
def search(request: SearchRequest) -> SearchResponse:
    hits = rag_service.search(
        query=request.query,
        top_k=request.top_k or settings.rag_top_k,
        filters=request.filters,
    )
    return SearchResponse(query=request.query, hits=hits)
