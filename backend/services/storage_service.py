import logging
from fastapi import UploadFile


logger = logging.getLogger(__name__)


def upload_file_to_storage(bucket, blob_name: str, file: UploadFile) -> str:
    """
    Upload a file to Firebase Storage.

    Args:
        bucket: Firebase Storage bucket instance
        blob_name: Full path for the file in storage
        file: The file to upload

    Returns:
        public_url: The public URL of the uploaded file
    """
    try:
        blob = bucket.blob(blob_name)
        blob.upload_from_file(file.file, content_type=file.content_type)
        logger.info(f"File uploaded to storage: {blob_name}")
        return blob.public_url
    except Exception as e:
        logger.error(f"Failed to upload to storage: {str(e)}")
        raise e


def delete_file_from_storage(bucket, storage_path: str) -> None:
    """
    Delete a file from Firebase Storage.

    Args:
        bucket: Firebase Storage bucket instance
        storage_path: Path to the file in storage
    """
    try:
        blob = bucket.blob(storage_path)
        blob.delete()
        logger.info(f"Deleted storage file: {storage_path}")
    except Exception as e:
        logger.warning(f"Error deleting from storage: {e}. Continuing anyway.")
        # Continue even if storage deletion fails
