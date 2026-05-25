"""Application configuration.

All settings are read from environment variables (12-factor). Defaults target
local development; Docker Compose injects the in-network DATABASE_URL.

SECRETS: openai_api_key is read from the OPENAI_API_KEY env var (or a gitignored
.env file). It is never hardcoded and never committed.

Provider switches (all default to free/offline/deterministic for cheap evals):
  extractor : "mock" | "openai"   document field extraction
  embedder  : "mock" | "openai"   rule/query embeddings for RAG
  reasoner  : "rules" | "openai"  decision reasoning (rules = deterministic)
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = (
        "postgresql+psycopg://clearkyc:clearkyc@localhost:5432/clearkyc"
    )
    app_name: str = "ClearKYC"

    # Pluggable providers.
    extractor: str = "mock"
    embedder: str = "mock"
    reasoner: str = "rules"

    # Where mock "document" JSON fixtures live (mounted in the container).
    fixtures_dir: str = "/srv/fixtures"
    # Where user-uploaded document images are stored (writable volume).
    uploads_dir: str = "/srv/uploads"

    # OpenAI.
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o"
    openai_embedding_model: str = "text-embedding-3-small"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
