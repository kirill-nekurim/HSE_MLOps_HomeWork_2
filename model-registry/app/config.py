from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(default="sqlite:///./registry.db", alias="DATABASE_URL")
    registry_root_path: Path = Field(default=Path("./models"), alias="REGISTRY_ROOT_PATH")
    registry_actor: str = Field(default="unknown", alias="REGISTRY_ACTOR")


settings = Settings()

