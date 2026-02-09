from fastapi import UploadFile, HTTPException
import config


def validate_file_size(file: UploadFile) -> None:
    """Validate file size doesn't exceed maximum allowed."""
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # Reset to beginning

    if file_size > config.MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File size ({file_size / 1024 / 1024:.2f}MB) exceeds maximum allowed size ({config.MAX_FILE_SIZE_MB}MB)"
        )


def get_file_extension(filename: str) -> str:
    """Safely extract file extension."""
    if not filename or '.' not in filename:
        raise HTTPException(status_code=400, detail="File must have an extension")

    extension = filename.rsplit('.', 1)[1].lower()

    if extension not in config.ALLOWED_FILE_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{extension}' not allowed. Allowed types: {', '.join(config.ALLOWED_FILE_EXTENSIONS)}"
        )

    return extension


def validate_text_length(text: str, max_length: int, field_name: str) -> None:
    """Validate text field doesn't exceed maximum length."""
    if len(text) > max_length:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} exceeds maximum length of {max_length} characters"
        )
