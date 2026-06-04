FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
COPY risk_radar ./risk_radar
COPY config ./config
COPY tests ./tests
RUN pip install --no-cache-dir ".[dev]"
CMD ["ingest-news", "--config", "config/sources.yaml"]

