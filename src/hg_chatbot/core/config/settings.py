from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class CoreSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    API_KEY: str

    OPENAI_CHAT_MODEL: str
    OPENAI_AGENT_MODEL: str
    OPENAI_VALIDATOR_MODEL: str
    OPENAI_STEMMING_MODEL: str
    OPENAI_TEXT_EMBEDDING_MODEL: str
    OPENAI_API_KEY: str

    GOOGLEAI_MODEL: str
    GOOGLEAI_MODEL_THINKING: str
    GOOGLEAI_API_KEY: str

    QDRANT_BASE_COLLECTION_NAME: str
    QDRANT_URL: str
    QDRANT_HOST: str
    QDRANT_PORT: int

    LANCEDB_PATH: str
    LANCEDB_COLLECTION_NAME: str

    MONGODB_CONNECTION_STRING: str
    MONGODB_BASE_DATABASE_NAME: str
    MONGODB_BASE_CHAT_HISTORY_COLLECTION_NAME: str
    MONGODB_BASE_DOC_COLLECTION_NAME: str

    VAHACHA_CHATBOT_PROMPT_PATH: str
    VAHACHA_AGENT_PROMPT_PATH: str

    BASE_PROMPT_PATH: str

    BASE_QUERY: str

    DISCORD_BOT_TOKEN: str
    DISCORD_BOT_URL: str
    DISCORD_BOT_ID: str

    DISCORD_BOT_RATE_LIMIT_PERIOD: int
    DISCORD_BOT_MAX_MESSAGES_PER_PERIOD: int
    DISCORD_BOT_COOLDOWN_MESSAGE: str
    DISCORD_BOT_NUM_WORKERS: int

    LANGFUSE_PUBLIC_KEY: str
    LANGFUSE_SECRET_KEY: str
    LANGFUSE_HOST: str
    LANGFUSE_TRACING_ENVIRONMENT: str

@lru_cache
def get_core_settings():
    return CoreSettings()
