from functools import lru_cache

from pydantic import AliasChoices
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="Resume Parser Service", alias="APP_NAME")
    max_file_size_mb: int = Field(default=5, alias="MAX_FILE_SIZE_MB")
    cors_origins: str = Field(
        default="http://localhost:4200,http://127.0.0.1:4200,https://resume-generator-spa-staging.up.railway.app",
        validation_alias=AliasChoices("CORS_ORIGINS", "ALLOWED_ORIGIN", "ALLOWED_ORIGINS"),
    )
    print('Parser Allowed Origins',cors_origins)
    llm_provider: str = Field(default="openai", alias="LLM_PROVIDER")

    openai_api_key: str | None = Field(default=None, validation_alias=AliasChoices("OPENAI_API_KEY", "OPENAI_KEY"))
    openai_model: str = Field(default="gpt-4.1-mini", alias="OPENAI_MODEL")

    ocr_fallback_enabled: bool = Field(default=True, alias="OCR_FALLBACK_ENABLED")
    ocr_min_text_length: int = Field(default=300, alias="OCR_MIN_TEXT_LENGTH")
    ocr_model: str = Field(default="gpt-4.1-mini", alias="OCR_MODEL")
    ocr_max_pages: int = Field(default=5, alias="OCR_MAX_PAGES")
    ocr_dpi: int = Field(default=200, alias="OCR_DPI")

    mongodb_uri: str | None = Field(default=None, validation_alias=AliasChoices("MONGO_URI", "MONGODB_URI", "MONGO_URL"))
    mongodb_database: str = Field(
        default="resume_parser",
        validation_alias=AliasChoices("MONGO_DATABASE", "MONGO_DB", "MONGODB_DATABASE"),
    )
    mongodb_resume_collection: str = Field(
        default="parsed_resumes",
        validation_alias=AliasChoices("MONGO_COLLECTION", "MONGODB_RESUME_COLLECTION"),
    )
    mongodb_template_resume_collection: str = Field(
        default="template_resumes",
        validation_alias=AliasChoices("MONGODB_TEMPLATE_RESUME_COLLECTION", "MONGO_TEMPLATE_COLLECTION"),
    )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    @property
    def allowed_cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
