from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "guardian-stream-agent"
    kafka_bootstrap_servers: str = Field(default="localhost:9092", alias="KAFKA_BOOTSTRAP_SERVERS")
    prompt_topic: str = Field(default="sanitized-prompts", alias="PROMPT_TOPIC")
    response_topic: str = Field(default="system-responses", alias="RESPONSE_TOPIC")
    consumer_group: str = Field(default="guardian-stream-agent", alias="KAFKA_CONSUMER_GROUP")
    sec_index_path: str = Field(default="data/indexes/sec", alias="SEC_INDEX_PATH")
    sec_collection_name: str = Field(default="sec_filings", alias="SEC_COLLECTION_NAME")
    sec_top_k: int = Field(default=3, alias="SEC_TOP_K")
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    synthesis_model: str = Field(default="claude-opus-4-7", alias="SYNTHESIS_MODEL")
    synthesis_max_tokens: int = Field(default=1024, alias="SYNTHESIS_MAX_TOKENS")
    model_config = SettingsConfigDict(
        populate_by_name=True,
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
