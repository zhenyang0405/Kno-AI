import uuid
import json
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import UploadFile, HTTPException
from utils.validators import validate_file_size, get_file_extension
from services import storage_service
from dependencies import get_db_connection


logger = logging.getLogger(__name__)


def upload_document(
    bucket,
    firebase_uid: str,
    knowledge_id: str,
    file: UploadFile,
    topic_id: Optional[str] = None
) -> str:
    """
    Upload a document to a knowledge entry (material).

    Args:
        bucket: Cloud Storage bucket instance
        firebase_uid: Firebase User ID
        knowledge_id: Material ID (knowledge entry ID)
        file: The file to upload
        topic_id: Optional topic ID for categorization

    Returns:
        storage_path: The path where the file is stored
    """
    # Validate file
    validate_file_size(file)
    file_extension = get_file_extension(file.filename)

    with get_db_connection() as conn:
        cur = conn.cursor()
        
        # Get user_id from firebase_uid
        cur.execute(
            "SELECT id FROM users WHERE firebase_uid = %s",
            (firebase_uid,)
        )
        user_row = cur.fetchone()
        if user_row is None:
            raise HTTPException(status_code=404, detail="User not found")
        user_id = user_row[0]
        
        # Check if knowledge exists for this user
        cur.execute(
            "SELECT id FROM knowledge WHERE id = %s AND user_id = %s",
            (int(knowledge_id), user_id)
        )
        if cur.fetchone() is None:
            raise HTTPException(status_code=404, detail="Knowledge not found")

        # Generate blob name and upload
        blob_name = f"users/{firebase_uid}/knowledge/{knowledge_id}/{str(uuid.uuid4())}.{file_extension}"
        public_url = storage_service.upload_file_to_storage(bucket, blob_name, file)

        # Store document metadata in materials table
        metadata = {
            'url': public_url,
            'topicId': topic_id,
            'uploadedAt': datetime.now(timezone.utc).isoformat()
        }
        
        cur.execute(
            """
            INSERT INTO materials 
            (knowledge_id, user_id, original_filename, storage_path, storage_bucket, mime_type, status, pdf_metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (int(knowledge_id), user_id, file.filename, blob_name, bucket.name, file.content_type, "uploaded", json.dumps(metadata))
        )

        logger.info(f"Document uploaded: {file.filename} to knowledge {knowledge_id} by firebase_uid {firebase_uid}")
        return blob_name


def delete_document(bucket, firebase_uid: str, knowledge_id: str, document_id: str):
    """
    Delete a document from a knowledge entry.

    Args:
        bucket: Cloud Storage bucket instance
        firebase_uid: Firebase User ID
        knowledge_id: Knowledge ID
        document_id: Document ID (material ID)
    """
    with get_db_connection() as conn:
        cur = conn.cursor()
        
        # Get user_id
        cur.execute(
            "SELECT id FROM users WHERE firebase_uid = %s",
            (firebase_uid,)
        )
        user_row = cur.fetchone()
        if user_row is None:
            raise HTTPException(status_code=404, detail="User not found")
        user_id = user_row[0]
        
        # Get document metadata
        cur.execute(
            "SELECT storage_path FROM materials WHERE id = %s AND user_id = %s",
            (int(document_id), user_id)
        )
        doc_row = cur.fetchone()
        if doc_row is None:
            raise HTTPException(status_code=404, detail="Document not found")
        
        storage_path = doc_row[0]
        
        # Delete from storage
        storage_service.delete_file_from_storage(bucket, storage_path)
        
        # Delete from database
        cur.execute(
            "DELETE FROM materials WHERE id = %s",
            (int(document_id),)
        )
        
        logger.info(f"Document deleted: document_id={document_id} by firebase_uid={firebase_uid}")


def get_document_details(firebase_uid: str, document_id: str) -> dict:
    """
    Get document metadata.

    Args:
        firebase_uid: Firebase User ID
        document_id: Document ID (material ID)

    Returns:
        Document metadata
    """
    with get_db_connection() as conn:
        cur = conn.cursor()
        
        # Get user_id
        cur.execute(
            "SELECT id FROM users WHERE firebase_uid = %s",
            (firebase_uid,)
        )
        user_row = cur.fetchone()
        if user_row is None:
            raise HTTPException(status_code=404, detail="User not found")
        user_id = user_row[0]
        
        # Get document details
        cur.execute(
            """
            SELECT id, knowledge_id, original_filename, storage_path, storage_bucket,
                   file_size, mime_type, status, pdf_metadata, created_at
            FROM materials
            WHERE id = %s AND user_id = %s
            """,
            (int(document_id), user_id)
        )
        
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Parse metadata (psycopg2 automatically converts jsonb to dict)
        metadata = row[8] if row[8] else {}
        
        return {
            "id": str(row[0]),
            "knowledgeId": str(row[1]),
            "filename": row[2],
            "storagePath": row[3],
            "storageBucket": row[4],
            "fileSize": row[5],
            "mimeType": row[6],
            "status": row[7],
            "url": metadata.get('url', ''),
            "topicId": metadata.get('topicId'),
            "uploadedAt": row[9].isoformat() if row[9] else metadata.get('uploadedAt')
        }


def get_document_download_url(bucket, firebase_uid: str, document_id: str) -> str:
    """
    Generate a signed URL for downloading a document from Cloud Storage.

    Args:
        bucket: Cloud Storage bucket instance
        firebase_uid: Firebase User ID
        document_id: Document ID (material ID)

    Returns:
        Signed download URL
    """
    with get_db_connection() as conn:
        cur = conn.cursor()
        
        # Get user_id
        cur.execute(
            "SELECT id FROM users WHERE firebase_uid = %s",
            (firebase_uid,)
        )
        user_row = cur.fetchone()
        if user_row is None:
            raise HTTPException(status_code=404, detail="User not found")
        user_id = user_row[0]
        
        # Get storage path
        cur.execute(
            "SELECT storage_path FROM materials WHERE id = %s AND user_id = %s",
            (int(document_id), user_id)
        )
        
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Document not found")
        
        storage_path = row[0]
        
        # Generate signed URL (valid for 1 hour)
        blob = bucket.blob(storage_path)
        url = blob.generate_signed_url(
            version="v4",
            expiration=3600,  # 1 hour
            method="GET"
        )
        
        logger.info(f"Generated download URL for document_id={document_id}")
        return url
