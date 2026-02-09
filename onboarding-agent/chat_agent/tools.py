
import logging
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager

# Database Configuration
import os

# Database Configuration
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "db")
DB_USER = os.environ.get("DB_USER", "user")
DB_PASS = os.environ.get("DB_PASS", "password")
DB_PORT = os.environ.get("DB_PORT", "5432")

# Allowed Categories
ALLOWED_CATEGORIES = {
    "learning_style",
    "interest",
    "goal",
    "skill_level",
    "communication_style"
}

def get_db_connection():
    """Establish connection to PostgreSQL database."""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            port=DB_PORT
        )
        return conn
    except Exception as e:
        logging.error(f"Database connection failed: {e}")
        return None

@contextmanager
def db_cursor(cursor_factory=None):
    """Context manager that provides a cursor and handles connection lifecycle."""
    conn = get_db_connection()
    if not conn:
        raise Exception("Database connection failed")
    try:
        cur = conn.cursor(cursor_factory=cursor_factory) if cursor_factory else conn.cursor()
        yield cur, conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

def get_or_create_user(firebase_uid: str) -> int:
    """
    Get internal user_id by firebase_uid, or create new user if doesn't exist.

    Args:
        firebase_uid (str): The Firebase UID.

    Returns:
        int: The internal database user ID.
    """
    try:
        with db_cursor() as (cur, conn):
            cur.execute("SELECT id FROM users WHERE firebase_uid = %s", (firebase_uid,))
            result = cur.fetchone()

            if result:
                return result[0]
            else:
                cur.execute("INSERT INTO users (firebase_uid) VALUES (%s) RETURNING id", (firebase_uid,))
                user_id = cur.fetchone()[0]
                logging.info(f"Created new user with firebase_uid: {firebase_uid}")
                return user_id
    except Exception as e:
        logging.error(f"Error in get_or_create_user: {e}")
        raise

def save_preference(user_id: int, category: str, detail: str) -> str:
    """
    Saves a user's preference using Smart Upsert logic.
    - Validates category against ALLOWED_CATEGORIES.
    - If record exists, merges new detail into existing JSON details list.
    - If new, inserts new record.

    Args:
        user_id (int): The database integer ID of the user. You must get this ID before calling this tool.
        category (str): Must be one of: learning_style, interest, goal, skill_level, communication_style
        detail (str): The specific preference detail (e.g., "Visual learner", "Python")

    Returns:
        Confirmation message.
    """
    if category not in ALLOWED_CATEGORIES:
        return f"Error: Invalid category '{category}'. Allowed: {', '.join(ALLOWED_CATEGORIES)}"

    try:
        with db_cursor() as (cur, conn):
            # Check for existing active record for this category
            cur.execute(
                """
                SELECT id, preference_data FROM user_preferences
                WHERE user_id = %s AND category = %s AND is_active = TRUE
                """,
                (user_id, category)
            )
            row = cur.fetchone()

            if row:
                record_id, existing_data = row

                # Merge Logic: ensuring 'details' is a list of strings
                current_details = existing_data.get("details", [])
                if not isinstance(current_details, list):
                    current_details = [str(current_details)] if current_details else []

                # Add new detail if not present
                if detail not in current_details:
                    current_details.append(detail)

                new_data = {"details": current_details}

                cur.execute(
                    """
                    UPDATE user_preferences
                    SET preference_data = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (json.dumps(new_data), record_id)
                )
                action = "Updated"
            else:
                # Insert New
                new_data = {"details": [detail]}
                cur.execute(
                    """
                    INSERT INTO user_preferences (user_id, category, preference_data, source)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (user_id, category, json.dumps(new_data), 'onboarding_smart_upsert')
                )
                action = "Created"

        logging.info(f"{action} preference for User ID {user_id}: {category} -> {detail}")
        return f"Saved preference: {category} - {detail}"

    except Exception as e:
        logging.error(f"Failed to save preference: {e}")
        return f"Error: Could not save preference. {str(e)}"

def get_preferences(user_id: int, category: str = None) -> list[dict]:
    """
    Retrieves user preferences.

    Args:
        user_id (int): The database integer ID of the user. You must get this ID before calling this tool.
        category (str, optional): The category to filter by. Defaults to None.
    """
    try:
        with db_cursor(cursor_factory=RealDictCursor) as (cur, conn):
            if category:
                cur.execute(
                    """
                    SELECT category, preference_data, created_at
                    FROM user_preferences
                    WHERE user_id = %s AND category = %s AND is_active = TRUE
                    ORDER BY created_at DESC
                    """,
                    (user_id, category)
                )
            else:
                cur.execute(
                    """
                    SELECT category, preference_data, created_at
                    FROM user_preferences
                    WHERE user_id = %s AND is_active = TRUE
                    ORDER BY created_at DESC
                    """,
                    (user_id,)
                )

            rows = cur.fetchall()
            return [dict(row) for row in rows]

    except Exception as e:
        logging.error(f"Failed to retrieve preferences: {e}")
        return []
