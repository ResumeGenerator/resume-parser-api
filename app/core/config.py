from functools import lru_cache

from pydantic import AliasChoices
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="Resume Parser Service", alias="APP_NAME")
    public_api_base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("PUBLIC_API_BASE_URL", "API_PUBLIC_BASE_URL", "APP_PUBLIC_URL"),
    )
    max_file_size_mb: int = Field(default=5, alias="MAX_FILE_SIZE_MB")
    resume_image_max_size_mb: int = Field(default=5, alias="RESUME_IMAGE_MAX_SIZE_MB")
    resume_image_storage_backend: str = Field(default="local", alias="RESUME_IMAGE_STORAGE_BACKEND")
    resume_image_storage_dir: str = Field(default="resume-images", alias="RESUME_IMAGE_STORAGE_DIR")
    resume_image_s3_endpoint_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("RESUME_IMAGE_S3_ENDPOINT_URL", "S3_ENDPOINT_URL"),
    )
    resume_image_s3_region: str = Field(
        default="auto",
        validation_alias=AliasChoices("RESUME_IMAGE_S3_REGION", "S3_REGION", "AWS_DEFAULT_REGION"),
    )
    resume_image_s3_bucket_name: str | None = Field(
        default=None,
        validation_alias=AliasChoices("RESUME_IMAGE_S3_BUCKET_NAME", "S3_BUCKET_NAME", "AWS_S3_BUCKET"),
    )
    resume_image_s3_access_key_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("RESUME_IMAGE_S3_ACCESS_KEY_ID", "S3_ACCESS_KEY_ID", "AWS_ACCESS_KEY_ID"),
    )
    resume_image_s3_secret_access_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "RESUME_IMAGE_S3_SECRET_ACCESS_KEY",
            "S3_SECRET_ACCESS_KEY",
            "AWS_SECRET_ACCESS_KEY",
        ),
    )
    resume_image_s3_key_prefix: str = Field(default="resume-images", alias="RESUME_IMAGE_S3_KEY_PREFIX")
    cors_origins: str = Field(
        default="http://localhost:4200,http://127.0.0.1:4200,https://resume-generator-spa-staging.up.railway.app",
        validation_alias=AliasChoices("CORS_ORIGINS", "ALLOWED_ORIGIN", "ALLOWED_ORIGINS"),
    )
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
        default="parsed_resume",
        validation_alias=AliasChoices("MONGO_COLLECTION", "MONGODB_RESUME_COLLECTION"),
    )
    mongodb_edited_resume_collection: str = Field(
        default="edited_resume",
        validation_alias=AliasChoices("MONGO_EDITED_COLLECTION", "MONGODB_EDITED_RESUME_COLLECTION"),
    )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    @property
    def resume_image_max_size_bytes(self) -> int:
        return self.resume_image_max_size_mb * 1024 * 1024

    @property
    def allowed_cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
