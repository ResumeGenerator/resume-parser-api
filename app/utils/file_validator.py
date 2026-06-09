from pathlib import Path

from fastapi import HTTPException, UploadFile, status


ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}


def validate_file_extension(filename: str | None) -> str:
    if not filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must include a filename.",
        )

    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type '{extension}'. Allowed file types: {allowed}.",
        )

    return extension


async def read_and_validate_file(upload: UploadFile, max_size_bytes: int) -> tuple[bytes, str]:
    extension = validate_file_extension(upload.filename)
    chunks: list[bytes] = []
    total_size = 0

    while chunk := await upload.read(1024 * 1024):
        total_size += len(chunk)
        if total_size > max_size_bytes:
            max_mb = max_size_bytes / (1024 * 1024)
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Uploaded resume exceeds the maximum size of {max_mb:.0f} MB.",
            )
        chunks.append(chunk)

    content = b"".join(chunks)

    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded resume file is empty.",
        )

    return content, extension
