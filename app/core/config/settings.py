from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class CoreSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    OPENAI_CHAT_MODEL: str
    OPENAI_CODE_MODEL: str
    OPENAI_TEXT_EMBEDDING_MODEL: str
    OPENAI_API_KEY: str

    GOOGLEAI_MODEL: str
    GOOGLEAI_MODEL_THINKING: str
    GOOGLEAI_MODEL_EDITOR: str
    GOOGLEAI_API_KEY: str

    QDRANT_BASE_COLLECTION_NAME: str
    QDRANT_URL: str
    QDRANT_HOST: str
    QDRANT_PORT: int

    MONGODB_CONNECTION_STRING: str
    MONGODB_BASE_DATABASE_NAME: str
    MONGODB_BASE_CHAT_HISTORY_COLLECTION_NAME: str
    MONGODB_BASE_DOC_COLLECTION_NAME: str

    OPS_AGENT_PROMPT_PATH: str
    OPS_AGENT_THINKING_PROMPT_PATH: str
    HR_AGENT_PROMPT_PATH: str
    HGGPT_AGENT_PROMPT_PATH: str

    SQL_DB_PATH: str

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

    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int
    POSTGRES_DB: str

@lru_cache
def get_core_settings():
    return CoreSettings()

@lru_cache
def get_sql_db_path():
    settings = get_core_settings()

    POSTGRES_USER = settings.POSTGRES_USER
    POSTGRES_PASSWORD = settings.POSTGRES_PASSWORD
    POSTGRES_HOST = settings.POSTGRES_HOST
    POSTGRES_PORT = settings.POSTGRES_PORT
    POSTGRES_DB = settings.POSTGRES_DB

    return f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
