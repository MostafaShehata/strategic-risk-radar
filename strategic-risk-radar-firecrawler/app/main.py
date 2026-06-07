from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .crawler import ArticleCrawler
from .schemas import CrawlRequest, CrawlResponse


app = FastAPI(title="Strategic Risk Radar Firecrawler")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
crawler = ArticleCrawler()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/crawl", response_model=CrawlResponse)
async def crawl(request: CrawlRequest) -> CrawlResponse:
    return await crawler.crawl(request.url)
