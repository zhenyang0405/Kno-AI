import uuid
import logging
from datetime import datetime, timezone
from fastapi import HTTPException
from utils.validators import validate_text_length
from dependencies import get_db_connection
import config


logger = logging.getLogger(__name__)


def create_knowledge(firebase_uid: str, name: str, description: str) -> str:
    """
    Create a new knowledge entry for a user.

    Args:
        firebase_uid: Firebase User ID
        name: Knowledge name
        description: Knowledge description

    Returns:
        knowledge_id: The generated ID for the knowledge entry
    """
    # Validate input lengths
    validate_text_length(name, config.MAX_KNOWLEDGE_NAME_LENGTH, "Knowledge name")
    validate_text_length(description, config.MAX_DESCRIPTION_LENGTH, "Description")

    with get_db_connection() as conn:
        cur = conn.cursor()
        
        # First, get or create user
        cur.execute(
            "SELECT id FROM users WHERE firebase_uid = %s",
            (firebase_uid,)
        )
        user_row = cur.fetchone()
        
        if user_row is None:
            # Create new user
            cur.execute(
                "INSERT INTO users (firebase_uid) VALUES (%s) RETURNING id",
                (firebase_uid,)
            )
            user_id = cur.fetchone()[0]
        else:
            user_id = user_row[0]
        
        # Create knowledge entry
        cur.execute(
            """
            INSERT INTO knowledge 
            (user_id, name, description)
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            (user_id, name, description)
        )
        knowledge_id = cur.fetchone()[0]
        
        logger.info(f"Knowledge created: knowledge_id={knowledge_id} by firebase_uid={firebase_uid}")
        return str(knowledge_id)


def get_knowledge_list(firebase_uid: str) -> list:
    """
    Get all knowledge entries for a user.

    Args:
        firebase_uid: Firebase User ID

    Returns:
        List of knowledge entries
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
            return []
        
        user_id = user_row[0]
        
        # Get all knowledge entries for this user
        cur.execute(
            """
            SELECT id, name, description, created_at, updated_at
            FROM knowledge
            WHERE user_id = %s
            ORDER BY created_at DESC
            """,
            (user_id,)
        )
        
        knowledge_list = []
        for row in cur.fetchall():
            knowledge_list.append({
                "id": str(row[0]),
                "name": row[1],
                "description": row[2],
                "createdAt": row[3].isoformat() if row[3] else None,
                "updatedAt": row[4].isoformat() if row[4] else None
            })
        
        return knowledge_list


def get_knowledge_details(firebase_uid: str, knowledge_id: str) -> dict:
    """
    Get details for a specific knowledge entry.

    Args:
        firebase_uid: Firebase User ID
        knowledge_id: Knowledge ID

    Returns:
        Knowledge details
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
        
        # Get knowledge details
        cur.execute(
            """
            SELECT id, name, description, created_at, updated_at
            FROM knowledge
            WHERE id = %s AND user_id = %s
            """,
            (int(knowledge_id), user_id)
        )
        
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Knowledge not found")
        
        return {
            "id": str(row[0]),
            "name": row[1],
            "description": row[2],
            "createdAt": row[3].isoformat() if row[3] else None,
           "updatedAt": row[4].isoformat() if row[4] else None
        }


def get_knowledge_documents(firebase_uid: str, knowledge_id: str) -> list:
    """
    Get all documents for a specific knowledge entry.

    Args:
        firebase_uid: Firebase User ID
        knowledge_id: Knowledge ID

    Returns:
        List of documents
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
        
        # Verify knowledge exists and belongs to user
        cur.execute(
            "SELECT id FROM knowledge WHERE id = %s AND user_id = %s",
            (int(knowledge_id), user_id)
        )
        if cur.fetchone() is None:
            raise HTTPException(status_code=404, detail="Knowledge not found")
        
        # Get all materials for this knowledge
        cur.execute(
            """
            SELECT id, original_filename, storage_path, storage_bucket, 
                   file_size, mime_type, status, pdf_metadata, created_at
            FROM materials
            WHERE knowledge_id = %s AND user_id = %s
            ORDER BY created_at DESC
            """,
            (int(knowledge_id), user_id)
        )
        
        documents = []
        for row in cur.fetchall():
            # Parse metadata if it exists (psycopg2 automatically converts jsonb to dict)
            metadata = row[7] if row[7] else {}
            
            documents.append({
                "id": str(row[0]),
                "filename": row[1],
                "storagePath": row[2],
                "storageBucket": row[3],
                "fileSize": row[4],
                "mimeType": row[5],
                "status": row[6],
                "url": metadata.get('url', ''),
                "topicId": metadata.get('topicId'),
                "uploadedAt": row[8].isoformat() if row[8] else metadata.get('uploadedAt')
            })
        
        return documents
