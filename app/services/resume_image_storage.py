from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
import logging
from PIL import Image, UnidentifiedImageError
from starlette.concurrency import run_in_threadpool


ALLOWED_IMAGE_FORMATS = {
    "JPEG": (".jpg", "image/jpeg"),
    "PNG": (".png", "image/png"),
    "WEBP": (".webp", "image/webp"),
}


@dataclass(frozen=True)
class StoredResumeImage:
    filename: str
    key: str
    content_type: str
    size_bytes: int
    backend: str
    path: Path | None = None


@dataclass(frozen=True)
class ResumeImageContent:
    content: bytes
    content_type: str


class ResumeImageStorage(Protocol):
    async def save_upload(self, resume_id: str, upload: UploadFile, max_size_bytes: int) -> StoredResumeImage:
        ...

    async def read_public_image(self, filename: str) -> ResumeImageContent:
        ...

    async def delete(self, image: StoredResumeImage) -> None:
        ...


class LocalResumeImageStorage:
    backend = "local"

    def __init__(self, storage_dir: str | Path):
        self.storage_dir = Path(storage_dir)

    async def save_upload(self, resume_id: str, upload: UploadFile, max_size_bytes: int) -> StoredResumeImage:
        content = await read_image_upload(upload, max_size_bytes)
        extension, content_type = detect_image_type(content)
        filename = build_image_filename(resume_id, extension)

        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            path = self.storage_dir / filename
            path.write_bytes(content)
        except OSError as exc:
            logging.getLogger(__name__).exception(
                "Local resume image storage write failed directory=%s",
                self.storage_dir,
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to save resume image to local storage.",
            ) from exc

        return StoredResumeImage(
            filename=filename,
            key=filename,
            path=path,
            content_type=content_type,
            size_bytes=len(content),
            backend=self.backend,
        )

    async def read_public_image(self, filename: str) -> ResumeImageContent:
        path = self._resolve_public_file(filename)
        content = path.read_bytes()
        return ResumeImageContent(content=content, content_type=get_image_media_type(filename))

    async def delete(self, image: StoredResumeImage) -> None:
        if image.path is not None:
            image.path.unlink(missing_ok=True)

    def _resolve_public_file(self, filename: str) -> Path:
        validate_public_filename(filename)
        path = self.storage_dir / filename
        if not path.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resume image was not found.",
            )
        return path


class S3ResumeImageStorage:
    backend = "s3"

    def __init__(
        self,
        *,
        endpoint_url: str,
        region_name: str,
        bucket_name: str,
        access_key_id: str,
        secret_access_key: str,
        key_prefix: str = "resume-images",
    ):
        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:
            raise RuntimeError("boto3 is required when RESUME_IMAGE_STORAGE_BACKEND=s3.") from exc

        self.bucket_name = bucket_name
        self.key_prefix = key_prefix.strip("/")
        try:
            self.client = boto3.client(
                "s3",
                endpoint_url=endpoint_url,
                region_name=region_name,
                aws_access_key_id=access_key_id,
                aws_secret_access_key=secret_access_key,
                config=Config(signature_version="s3v4"),
            )
        except Exception as exc:  # pragma: no cover - defensive
            logging.getLogger(__name__).exception("Failed to construct S3 client.")
            raise RuntimeError("Failed to initialize S3 client for resume image storage.") from exc

    async def save_upload(self, resume_id: str, upload: UploadFile, max_size_bytes: int) -> StoredResumeImage:
        content = await read_image_upload(upload, max_size_bytes)
        extension, content_type = detect_image_type(content)
        filename = build_image_filename(resume_id, extension)
        key = self._object_key(filename)

        try:
            await run_in_threadpool(
                self.client.put_object,
                Bucket=self.bucket_name,
                Key=key,
                Body=content,
                ContentType=content_type,
            )
        except Exception as exc:  # pragma: no cover - integration error
            logging.getLogger(__name__).exception("S3 put_object failed for bucket=%s key=%s", self.bucket_name, key)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to upload resume image to S3 storage.",
            ) from exc

        return StoredResumeImage(
            filename=filename,
            key=key,
            content_type=content_type,
            size_bytes=len(content),
            backend=self.backend,
        )

    async def read_public_image(self, filename: str) -> ResumeImageContent:
        validate_public_filename(filename)
        key = self._object_key(filename)
        try:
            response = await run_in_threadpool(self.client.get_object, Bucket=self.bucket_name, Key=key)
        except Exception as exc:  # pragma: no cover - integration error
            logging.getLogger(__name__).exception("S3 get_object failed for bucket=%s key=%s", self.bucket_name, key)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resume image was not found.",
            ) from exc

        body = response["Body"]
        content = await run_in_threadpool(body.read)
        content_type = response.get("ContentType") or get_image_media_type(filename)
        return ResumeImageContent(content=content, content_type=content_type)

    async def delete(self, image: StoredResumeImage) -> None:
        await run_in_threadpool(self.client.delete_object, Bucket=self.bucket_name, Key=image.key)

    def _object_key(self, filename: str) -> str:
        return f"{self.key_prefix}/{filename}" if self.key_prefix else filename


async def read_image_upload(upload: UploadFile, max_size_bytes: int) -> bytes:
    if not upload.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded image must include a filename.",
        )

    chunks: list[bytes] = []
    total_size = 0

    while chunk := await upload.read(1024 * 1024):
        total_size += len(chunk)
        if total_size > max_size_bytes:
            max_mb = max_size_bytes / (1024 * 1024)
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Uploaded resume image exceeds the maximum size of {max_mb:.0f} MB.",
            )
        chunks.append(chunk)

    content = b"".join(chunks)
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded resume image is empty.",
        )

    return content


def detect_image_type(content: bytes) -> tuple[str, str]:
    try:
        with Image.open(BytesIO(content)) as image:
            image.verify()
            image_format = image.format
    except (OSError, UnidentifiedImageError) as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Uploaded file must be a valid JPEG, PNG, or WebP image.",
        ) from exc

    if image_format not in ALLOWED_IMAGE_FORMATS:
        allowed = ", ".join(sorted(format_name.lower() for format_name in ALLOWED_IMAGE_FORMATS))
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported image type '{image_format}'. Allowed image types: {allowed}.",
        )

    return ALLOWED_IMAGE_FORMATS[image_format]


def build_image_filename(resume_id: str, extension: str) -> str:
    return f"{resume_id}-{uuid4().hex}{extension}"


def validate_public_filename(filename: str) -> None:
    if Path(filename).name != filename:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume image was not found.",
        )


def get_image_media_type(filename: str) -> str:
    suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(suffix, "application/octet-stream")
