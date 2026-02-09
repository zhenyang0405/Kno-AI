"""
User Service

Manages user records and Firebase UID to database user_id mapping.
"""
import logging
from typing import Optional, Dict
import psycopg2
from psycopg2.extras import RealDictCursor

from config import (
    DB_HOST,
    DB_NAME,
    DB_USER,
    DB_PASS,
    DB_PORT
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
        port=DB_PORT,
        cursor_factory=RealDictCursor
    )


def get_or_create_user_by_firebase_uid(firebase_uid: str) -> Dict:
    """
    Get user by Firebase UID, or create if doesn't exist
    
    Args:
        firebase_uid: Firebase authentication UID
        email: Optional user email
        name: Optional user display name
        
    Returns:
        Dict with user data including database user_id
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if user exists with this Firebase UID
        cursor.execute(
            """
            SELECT id, firebase_uid
            FROM users
            WHERE firebase_uid = %s
            """,
            (firebase_uid,)
        )
        
        existing_user = cursor.fetchone()
        
        if existing_user:
            cursor.close()
            conn.close()
            logger.info(f"Found existing user with Firebase UID: {firebase_uid}, database ID: {existing_user['id']}")
            return dict(existing_user)
        
        # Create new user if doesn't exist
        cursor.execute(
            """
            INSERT INTO users (firebase_uid)
            VALUES (%s)
            RETURNING id, firebase_uid
            """,
            (firebase_uid,)
        )
        
        new_user = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()
        
        user_data = dict(new_user)
        logger.info(f"Created new user with Firebase UID: {firebase_uid}, database ID: {user_data['id']}")
        
        return user_data
        
    except Exception as e:
        logger.error(f"Error getting/creating user: {e}")
        if conn:
            conn.rollback()
            conn.close()
        raise


def get_user_by_id(user_id: int) -> Optional[Dict]:
    """
    Get user by database ID
    
    Args:
        user_id: Database user ID
        
    Returns:
        Dict with user data or None if not found
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            """
            SELECT id, firebase_uid, email, name, created_at, updated_at
            FROM users
            WHERE id = %s
            """,
            (user_id,)
        )
        
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if user:
            return dict(user)
        return None
        
    except Exception as e:
        logger.error(f"Error getting user by ID: {e}")
        if conn:
            conn.close()
        return None


def update_user(user_id: int, email: Optional[str] = None, name: Optional[str] = None) -> bool:
    """
    Update user information
    
    Args:
        user_id: Database user ID
        email: Optional new email
        name: Optional new name
        
    Returns:
        True if updated, False otherwise
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        update_fields = []
        params = []
        
        if email is not None:
            update_fields.append("email = %s")
            params.append(email)
        
        if name is not None:
            update_fields.append("name = %s")
            params.append(name)
        
        if not update_fields:
            logger.warning("No fields to update")
            return False
        
        update_fields.append("updated_at = CURRENT_TIMESTAMP")
        
        query = f"""
            UPDATE users 
            SET {', '.join(update_fields)}
            WHERE id = %s
        """
        params.append(user_id)
        
        cursor.execute(query, params)
        updated = cursor.rowcount > 0
        
        conn.commit()
        cursor.close()
        conn.close()
        
        if updated:
            logger.info(f"Updated user {user_id}")
        else:
            logger.warning(f"User {user_id} not found")
        
        return updated
        
    except Exception as e:
        logger.error(f"Error updating user: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return False


def ensure_users_table():
    """
    Ensure users table exists with firebase_uid column
    This should be called during database setup
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Create users table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                firebase_uid VARCHAR(128) UNIQUE NOT NULL,
                email VARCHAR(255),
                name VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Create index on firebase_uid for fast lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_firebase_uid ON users(firebase_uid);
        """)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info("Users table ensured with firebase_uid column")
        
    except Exception as e:
        logger.error(f"Error ensuring users table: {e}")
        if conn:
            conn.rollback()
            conn.close()
        raise
