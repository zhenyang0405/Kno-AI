"""
Material Context Cache Service

Manages Gemini context caching for study materials to save tokens.
Uploads PDFs from Google Cloud Storage to Gemini File API and creates
cached contexts that can be reused across multiple requests.
"""
import io
import logging
from typing import Optional, Dict
from datetime import datetime, timezone
import psycopg2
from google import genai
from google.genai import types
from google.cloud import storage

from config import (
    GEMINI_API_KEY,
    GEMINI_THINKING_MODEL,
    CACHE_SYSTEM_INSTRUCTION,
    DB_HOST,
    DB_NAME,
    DB_USER,
    DB_PASS,
    DB_PORT,
    GCS_BUCKET_NAME
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_db_connection():
    """Create database connection"""
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        port=DB_PORT
    )


def download_pdf_from_gcs(storage_bucket: str, storage_path: str) -> bytes:
    """
    Download PDF from Google Cloud Storage
    
    Args:
        storage_bucket: GCS bucket name
        storage_path: Path to PDF in bucket
        
    Returns:
        PDF content as bytes
    """
    logger.info(f"Downloading PDF from gs://{storage_bucket}/{storage_path}")
    
    storage_client = storage.Client()
    bucket = storage_client.bucket(storage_bucket)
    blob = bucket.blob(storage_path)
    
    pdf_bytes = blob.download_as_bytes()
    logger.info(f"Downloaded {len(pdf_bytes)} bytes")
    
    return pdf_bytes


def create_material_cache(study_session_id: int) -> Dict:
    """
    Create Gemini context cache for a study session's material
    
    Args:
        study_session_id: ID of the study session
        
    Returns:
        Dict with cache information:
        {
            'cache_id': int,
            'material_id': int,
            'cache_name': str,
            'expires_at': datetime
        }
        
    Raises:
        ValueError: If study session or material not found
        Exception: For database or API errors
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Get material_id from study_session
        logger.info(f"Fetching study session {study_session_id}")
        cursor.execute(
            "SELECT material_id, user_id FROM study_sessions WHERE id = %s",
            (study_session_id,)
        )
        result = cursor.fetchone()
        
        if not result:
            raise ValueError(f"Study session {study_session_id} not found")
        
        material_id, user_id = result
        logger.info(f"Found material_id={material_id}, user_id={user_id}")
        
        # 2. Check if active cache already exists
        existing_cache = get_active_cache(material_id)
        if existing_cache:
            logger.info(f"Active cache already exists: {existing_cache}")
            cursor.execute(
                "SELECT id, cache_name, expires_at FROM material_context_caches WHERE cache_name = %s",
                (existing_cache,)
            )
            cache_row = cursor.fetchone()
            cursor.close()
            conn.close()
            return {
                'cache_id': cache_row[0],
                'material_id': material_id,
                'cache_name': cache_row[1],
                'expires_at': cache_row[2]
            }
        
        # 3. Get material storage info
        cursor.execute(
            "SELECT storage_bucket, storage_path FROM materials WHERE id = %s",
            (material_id,)
        )
        material_result = cursor.fetchone()
        
        if not material_result:
            raise ValueError(f"Material {material_id} not found")
        
        storage_bucket, storage_path = material_result
        logger.info(f"Material stored at gs://{storage_bucket}/{storage_path}")
        
        # 4. Download PDF from GCS
        pdf_bytes = download_pdf_from_gcs(storage_bucket, storage_path)
        doc_io = io.BytesIO(pdf_bytes)
        
        # 5. Upload to Gemini File API
        logger.info("Uploading PDF to Gemini File API")
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        document = client.files.upload(
            file=doc_io,
            config=dict(mime_type='application/pdf')
        )
        logger.info(f"Uploaded document: {document.name}")
        
        # 6. Create cache
        logger.info("Creating Gemini context cache")
        cache = client.caches.create(
            model=GEMINI_THINKING_MODEL,
            config=types.CreateCachedContentConfig(
                system_instruction=CACHE_SYSTEM_INSTRUCTION,
                contents=[document],
            )
        )
        
        logger.info(f"Cache created: {cache.name}")
        logger.info(f"Cache expires at: {cache.expire_time}")
        
        # 7. Save to database
        cursor.execute(
            """
            INSERT INTO material_context_caches 
            (material_id, cache_name, expires_at, status)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (material_id, cache.name, cache.expire_time, 'active')
        )
        cache_id = cursor.fetchone()[0]
        conn.commit()
        
        logger.info(f"Saved cache to database with id={cache_id}")
        
        cursor.close()
        conn.close()
        
        return {
            'cache_id': cache_id,
            'material_id': material_id,
            'cache_name': cache.name,
            'expires_at': cache.expire_time
        }
        
    except Exception as e:
        logger.error(f"Error creating material cache: {e}")
        if conn:
            conn.rollback()
            conn.close()
        raise


def update_expired_caches(material_id: int) -> int:
    """
    Update cache status to 'expired' for all caches with expires_at < NOW()
    
    Args:
        material_id: ID of the material
        
    Returns:
        Number of caches updated
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            """
            UPDATE material_context_caches 
            SET status = 'expired'
            WHERE material_id = %s 
              AND status = 'active' 
              AND expires_at < NOW()
            """,
            (material_id,)
        )
        
        updated_count = cursor.rowcount
        conn.commit()
        cursor.close()
        conn.close()
        
        if updated_count > 0:
            logger.info(f"Updated {updated_count} expired cache(s) for material {material_id}")
        
        return updated_count
        
    except Exception as e:
        logger.error(f"Error updating expired caches: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return 0


def get_active_cache(material_id: int) -> Optional[str]:
    """
    Get active cache name for a material if it exists and hasn't expired
    
    Args:
        material_id: ID of the material
        
    Returns:
        Cache name if active cache exists, None otherwise
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            """
            SELECT cache_name 
            FROM material_context_caches 
            WHERE material_id = %s 
              AND status = 'active' 
              AND expires_at > NOW()
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (material_id,)
        )
        
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if result:
            return result[0]
        
        # No active cache found, update any expired caches
        update_expired_caches(material_id)
        return None
        
    except Exception as e:
        logger.error(f"Error getting active cache: {e}")
        if conn:
            conn.close()
        return None

