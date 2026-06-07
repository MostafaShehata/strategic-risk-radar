from pydantic import BaseModel, Field


class CrawlRequest(BaseModel):
    url: str = Field(min_length=1)
    source_id: str = ""
    raw_news_item_id: str | None = None


class CrawlResponse(BaseModel):
    status: str
    url: str
    title: str = ""
    body: str = ""
    language: str | None = None
    published_at: str | None = None
    fetcher: str = "trafilatura"
    error_message: str | None = None
