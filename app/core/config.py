from functools import lru_cache

from pydantic import AliasChoices
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="Resume Parser Service", alias="APP_NAME")
    max_file_size_mb: int = Field(default=5, alias="MAX_FILE_SIZE_MB")

    llm_provider: str = Field(default="openai", alias="LLM_PROVIDER")

    openai_api_key: str | None = Field(default=None, validation_alias=AliasChoices("OPENAI_API_KEY", "OPENAI_KEY"))
    openai_model: str = Field(default="gpt-4.1-mini", alias="OPENAI_MODEL")

    mongodb_uri: str | None = Field(default=None, validation_alias=AliasChoices("MONGO_URI", "MONGODB_URI", "MONGO_URL"))
    mongodb_database: str = Field(
        default="resume_parser",
        validation_alias=AliasChoices("MONGO_DATABASE", "MONGO_DB", "MONGODB_DATABASE"),
    )
    mongodb_resume_collection: str = Field(
        default="parsed_resumes",
        validation_alias=AliasChoices("MONGO_COLLECTION", "MONGODB_RESUME_COLLECTION"),
    )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
