from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @field_validator("qdrant_api_key", "openai_api_key", "telegram_bot_token", mode="before")
    @classmethod
    def empty_str_to_none(cls, v):
        return v or None

    # MongoDB
    mongo_uri: str
    mongo_db: str = "reddit_monitor"
    mongo_collection: str = "posts"

    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_api_key: str | None = None
    qdrant_collection: str = "reddit_posts"

    # Ollama
    ollama_url: str = "http://localhost:11434"
    embed_model: str = "nomic-embed-text"
    sparse_model: str = "Qdrant/bm25"

    # OpenAI
    openai_llm_model: str = "gpt-4o-mini"
    openai_api_key: str | None = None

    # Telegram
    telegram_bot_token: str | None = None
    telegram_allowed_usernames: list[str] = []
    notification_topics: list[str] = [
        (
            "Cloud infrastructure security: misconfiguration findings, IAM privilege escalation, "
            "S3 bucket exposure, publicly exposed services, attack techniques against AWS/GCP/Azure. "
            "NOT about: general DevOps, cost optimization, cloud architecture without security angle."
        ),
    ]

    # Reddit RSS
    subreddits: list[str] = [
        "netsec",
        "blueteamsec",
        "cybersecurity",
        "devsecops",
    ]
    poll_interval: int = 300

    # Indexing
    chunk_size: int = 1000
    chunk_overlap: int = 200

    # Agent
    top_k: int = 5
    score_threshold: float = 0.5
    max_iterations: int = 5


settings = Settings()
