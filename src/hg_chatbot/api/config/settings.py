from pathlib import Path
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class APISettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    API_KEY: str

    ENV: str
    VALIDATE_API: bool

    JWKS_HG_APP_URL: str
    JWKS_HG_DEV_URL: str
    JWT_ISSUER_HG_APP: str
    JWT_ISSUER_HG_DEV: str
    JWT_ALGORITHM: str

@lru_cache
def get_api_settings():
    return APISettings()
