from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class APISettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    API_KEY: str

@lru_cache
def get_api_settings():
    return APISettings()
