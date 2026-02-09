"""
Study Session Service

Manages study session lifecycle including creation, retrieval, and updates.
Handles the connection between users, materials, and assessments.
"""
import logging
from typing import Optional, Dict, List
import json
from datetime import datetime
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


def create_study_session(
    user_id: int,
    material_id: int,
    pre_assessment_id: Optional[int] = None,
    weak_concepts: Optional[List[str]] = None
) -> Dict:
    """
    Create a new study session
    
    Args:
        user_id: ID of the user
        material_id: ID of the material to study
        pre_assessment_id: Optional ID of the pre-assessment
        weak_concepts: Optional list of weak concept IDs from pre-assessment
        
    Returns:
        Dict with study session information (existing or newly created)
        
    Raises:
        ValueError: If user or material not found
        Exception: For database errors
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if study session already exists for this user and material
        cursor.execute(
            """
            SELECT id, user_id, material_id, pre_assessment_id, weak_concepts, 
                   status, started_at, created_at
            FROM study_sessions
            WHERE user_id = %s AND material_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (user_id, material_id)
        )
        
        existing = cursor.fetchone()
        if existing:
            cursor.close()
            conn.close()
            session_data = dict(existing)
            logger.info(f"Study session already exists: {session_data['id']} for user {user_id} and material {material_id}")
            return session_data
        
        # Verify user exists
        cursor.execute("SELECT id FROM users WHERE id = %s", (user_id,))
        if not cursor.fetchone():
            raise ValueError(f"User {user_id} not found")
        
        # Verify material exists
        cursor.execute("SELECT id FROM materials WHERE id = %s", (material_id,))
        if not cursor.fetchone():
            raise ValueError(f"Material {material_id} not found")
        
        # Verify pre-assessment if provided
        if pre_assessment_id:
            cursor.execute("SELECT id FROM assessments WHERE id = %s", (pre_assessment_id,))
            if not cursor.fetchone():
                raise ValueError(f"Assessment {pre_assessment_id} not found")
        
        # Insert study session
        cursor.execute(
            """
            INSERT INTO study_sessions 
            (user_id, material_id, pre_assessment_id, weak_concepts, status, started_at)
            VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            RETURNING id, user_id, material_id, pre_assessment_id, weak_concepts, 
                      status, started_at, created_at
            """,
            (
                user_id,
                material_id,
                pre_assessment_id,
                json.dumps(weak_concepts) if weak_concepts else None,
                'in_progress'
            )
        )
        
        result = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()
        
        session_data = dict(result)
        logger.info(f"Created study session {session_data['id']} for user {user_id}")
        
        return session_data
        
    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Error creating study session: {e}")
        if conn:
            conn.rollback()
            conn.close()
        raise


def get_study_session(session_id: int) -> Optional[Dict]:
    """
    Get study session by ID
    
    Args:
        session_id: ID of the study session
        
    Returns:
        Dict with study session data, None if not found
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            """
            SELECT id, user_id, material_id, pre_assessment_id, post_assessment_id,
                   weak_concepts, status, started_at, completed_at, created_at, updated_at
            FROM study_sessions
            WHERE id = %s
            """,
            (session_id,)
        )
        
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if result:
            return dict(result)
        return None
        
    except Exception as e:
        logger.error(f"Error getting study session: {e}")
        if conn:
            conn.close()
        return None


def get_user_study_sessions(user_id: int, status: Optional[str] = None) -> List[Dict]:
    """
    Get all study sessions for a user
    
    Args:
        user_id: ID of the user
        status: Optional filter by status ('in_progress', 'completed', etc.)
        
    Returns:
        List of study session dicts
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT ss.id, ss.user_id, ss.material_id, ss.pre_assessment_id, 
                   ss.post_assessment_id, ss.weak_concepts, ss.status, 
                   ss.started_at, ss.completed_at, ss.created_at, ss.updated_at,
                   m.original_filename as material_name
            FROM study_sessions ss
            JOIN materials m ON ss.material_id = m.id
            WHERE ss.user_id = %s
        """
        
        params = [user_id]
        
        if status:
            query += " AND ss.status = %s"
            params.append(status)
        
        query += " ORDER BY ss.started_at DESC"
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return [dict(row) for row in results]
        
    except Exception as e:
        logger.error(f"Error getting user study sessions: {e}")
        if conn:
            conn.close()
        return []


def update_study_session(
    session_id: int,
    post_assessment_id: Optional[int] = None,
    weak_concepts: Optional[List[str]] = None,
    status: Optional[str] = None,
    completed_at: Optional[datetime] = None
) -> bool:
    """
    Update study session fields
    
    Args:
        session_id: ID of the study session
        post_assessment_id: Optional post-assessment ID
        weak_concepts: Optional updated weak concepts list
        status: Optional new status
        completed_at: Optional completion timestamp
        
    Returns:
        True if updated, False otherwise
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Build dynamic update query
        update_fields = []
        params = []
        
        if post_assessment_id is not None:
            update_fields.append("post_assessment_id = %s")
            params.append(post_assessment_id)
        
        if weak_concepts is not None:
            update_fields.append("weak_concepts = %s")
            params.append(json.dumps(weak_concepts))
        
        if status is not None:
            update_fields.append("status = %s")
            params.append(status)
        
        if completed_at is not None:
            update_fields.append("completed_at = %s")
            params.append(completed_at)
        
        if not update_fields:
            logger.warning("No fields to update")
            return False
        
        # Always update updated_at
        update_fields.append("updated_at = CURRENT_TIMESTAMP")
        
        query = f"""
            UPDATE study_sessions 
            SET {', '.join(update_fields)}
            WHERE id = %s
        """
        params.append(session_id)
        
        cursor.execute(query, params)
        updated = cursor.rowcount > 0
        
        conn.commit()
        cursor.close()
        conn.close()
        
        if updated:
            logger.info(f"Updated study session {session_id}")
        else:
            logger.warning(f"Study session {session_id} not found")
        
        return updated
        
    except Exception as e:
        logger.error(f"Error updating study session: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return False


def complete_study_session(session_id: int, post_assessment_id: Optional[int] = None) -> bool:
    """
    Mark a study session as completed
    
    Args:
        session_id: ID of the study session
        post_assessment_id: Optional post-assessment ID
        
    Returns:
        True if completed, False otherwise
    """
    return update_study_session(
        session_id=session_id,
        post_assessment_id=post_assessment_id,
        status='completed',
        completed_at=datetime.now()
    )


def get_study_session_with_details(session_id: int) -> Optional[Dict]:
    """
    Get study session with full details including material and assessment info
    
    Args:
        session_id: ID of the study session
        
    Returns:
        Dict with detailed study session information
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            """
            SELECT 
                ss.id, ss.user_id, ss.material_id, ss.pre_assessment_id, 
                ss.post_assessment_id, ss.weak_concepts, ss.status, 
                ss.started_at, ss.completed_at, ss.created_at, ss.updated_at,
                m.original_filename as material_name,
                m.storage_path as material_path,
                pre_a.score as pre_assessment_score,
                post_a.score as post_assessment_score
            FROM study_sessions ss
            JOIN materials m ON ss.material_id = m.id
            LEFT JOIN assessments pre_a ON ss.pre_assessment_id = pre_a.id
            LEFT JOIN assessments post_a ON ss.post_assessment_id = post_a.id
            WHERE ss.id = %s
            """,
            (session_id,)
        )
        
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if result:
            return dict(result)
        return None
        
    except Exception as e:
        logger.error(f"Error getting study session details: {e}")
        if conn:
            conn.close()
        return None


def delete_study_session(session_id: int) -> bool:
    """
    Delete a study session
    
    Args:
        session_id: ID of the study session
        
    Returns:
        True if deleted, False otherwise
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM study_sessions WHERE id = %s", (session_id,))
        deleted = cursor.rowcount > 0
        
        conn.commit()
        cursor.close()
        conn.close()
        
        if deleted:
            logger.info(f"Deleted study session {session_id}")
        else:
            logger.warning(f"Study session {session_id} not found")
        
        return deleted
        
    except Exception as e:
        logger.error(f"Error deleting study session: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return False
