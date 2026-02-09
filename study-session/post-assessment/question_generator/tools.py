"""
ADK Tools for Post-Assessment Question Generator Agent

Provides four tools:
1. load_pdf - Loads PDF from Google Cloud Storage
2. save_mcq_question - Saves generated MCQ questions to PostgreSQL (with assessment_type)
3. get_weak_concepts - Retrieves weak concepts from study session
4. get_material_concepts - Retrieves all concepts with user understanding levels
"""
import psycopg2
from psycopg2.extras import Json
from typing import Dict
import json
import logging
import traceback
import tempfile
import os
from google.cloud import storage
from PyPDF2 import PdfReader
from .config import DB_HOST, DB_NAME, DB_USER, DB_PASS, DB_PORT

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def get_db_connection():
    """
    Creates and returns a PostgreSQL database connection.

    Returns:
        psycopg2 connection object
    """
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        port=DB_PORT
    )


def load_pdf(storage_path: str, storage_bucket: str) -> str:
    """
    Loads PDF from Google Cloud Storage and extracts text content.

    This tool:
    1. Downloads PDF from GCS to a temporary file
    2. Extracts text content from the PDF
    3. Returns the text content for analysis

    Args:
        storage_path: Path in GCS (e.g., "materials/user123/python.pdf")
        storage_bucket: GCS bucket name (e.g., "ai-educate-materials")

    Returns:
        Extracted text content from the PDF

    Example:
        >>> load_pdf("materials/user123/sample.pdf", "ai-educate-materials")
        "Chapter 1: Introduction\\n\\nThis chapter covers..."
    """
    logger.info(f"[TOOL] load_pdf called: bucket={storage_bucket}, path={storage_path}")

    try:
        # Validate inputs
        if not storage_path or not storage_bucket:
            error_msg = "Error: storage_path and storage_bucket are required"
            logger.error(f"[TOOL] load_pdf validation failed: {error_msg}")
            return error_msg

        # Remove leading slash if present
        storage_path = storage_path.lstrip('/')
        logger.debug(f"[TOOL] Cleaned path: {storage_path}")

        # Initialize GCS client
        logger.info(f"[TOOL] Downloading PDF from GCS...")
        storage_client = storage.Client()
        bucket = storage_client.bucket(storage_bucket)
        blob = bucket.blob(storage_path)

        # Download to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            temp_path = temp_file.name
            blob.download_to_filename(temp_path)
            logger.info(f"[TOOL] PDF downloaded to: {temp_path}")

        # Extract text from PDF
        logger.info(f"[TOOL] Extracting text from PDF...")
        reader = PdfReader(temp_path)
        text_content = []

        for i, page in enumerate(reader.pages):
            page_text = page.extract_text()
            text_content.append(f"\n--- Page {i+1} ---\n{page_text}")
            logger.debug(f"[TOOL] Extracted page {i+1}/{len(reader.pages)}")

        full_text = "\n".join(text_content)
        logger.info(f"[TOOL] Extracted {len(full_text)} characters from {len(reader.pages)} pages")

        # Clean up temp file
        os.unlink(temp_path)
        logger.debug(f"[TOOL] Cleaned up temporary file")

        # Return the text content with instructions
        return f"""Successfully loaded and extracted text from PDF.

Source: gs://{storage_bucket}/{storage_path}
Pages: {len(reader.pages)}
Characters extracted: {len(full_text)}

PDF CONTENT:
{full_text}

---END OF PDF CONTENT---

Now generate 10 high-quality post-assessment multiple-choice questions based on this material, targeting the weak concepts identified earlier. Focus on harder, more practical questions."""

    except Exception as e:
        logger.error(f"[TOOL] load_pdf error: {str(e)}")
        logger.error(f"[TOOL] Traceback:\n{traceback.format_exc()}")
        return f"Error loading PDF: {str(e)}"


def save_mcq_question(
    material_id: int,
    question_text: str,
    options: Dict[str, str],
    correct_answer: str,
    explanation: str,
    difficulty: str,
    order_number: int,
) -> str:
    """
    Saves an MCQ question to PostgreSQL database with assessment_type.

    Args:
        material_id: Database ID of the source material
        question_text: The question text
        options: Dictionary with keys A, B, C, D mapping to answer text
                 Example: {"A": "Option 1", "B": "Option 2", "C": "Option 3", "D": "Option 4"}
        correct_answer: Letter of correct option ("A", "B", "C", or "D")
        explanation: Explanation of why the answer is correct
        difficulty: Question difficulty ("easy", "medium", or "hard")
        order_number: Display order (1-10)

    Returns:
        Success message with question_id or error message

    Example:
        >>> save_mcq_question(
        ...     material_id=1,
        ...     question_text="What is Python?",
        ...     options={"A": "A snake", "B": "A programming language", "C": "A framework", "D": "A library"},
        ...     correct_answer="B",
        ...     explanation="Python is a high-level programming language",
        ...     difficulty="easy",
        ...     order_number=1,
        ... )
        "Successfully saved question 1 with ID: 123"
    """
    # Validate inputs
    errors = []

    # Validate options structure
    if not isinstance(options, dict):
        errors.append("options must be a dictionary")
    else:
        required_keys = {"A", "B", "C", "D"}
        if set(options.keys()) != required_keys:
            errors.append(f"options must have exactly keys A, B, C, D. Got: {list(options.keys())}")

    # Validate correct_answer
    if correct_answer not in ["A", "B", "C", "D"]:
        errors.append(f"correct_answer must be A, B, C, or D. Got: {correct_answer}")

    # Validate difficulty
    if difficulty not in ["easy", "medium", "hard"]:
        errors.append(f"difficulty must be easy, medium, or hard. Got: {difficulty}")

    # Validate order_number
    if not (1 <= order_number <= 10):
        errors.append(f"order_number must be between 1 and 10. Got: {order_number}")

    # Validate required text fields
    if not question_text or not question_text.strip():
        errors.append("question_text cannot be empty")

    if not explanation or not explanation.strip():
        errors.append("explanation cannot be empty")

    # Return validation errors if any
    if errors:
        return f"Validation errors: {'; '.join(errors)}"

    assessment_type = "post"

    # Insert into database
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        insert_query = """
        INSERT INTO questions (
            material_id, question_text, options, correct_answer,
            explanation, difficulty, order_number, assessment_type
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id;
        """

        cursor.execute(
            insert_query,
            (
                material_id,
                question_text.strip(),
                Json(options),  # Convert dict to JSONB
                correct_answer,
                explanation.strip(),
                difficulty,
                order_number,
                assessment_type
            )
        )

        question_id = cursor.fetchone()[0]
        conn.commit()

        cursor.close()
        conn.close()

        return f"Successfully saved question {order_number} with ID: {question_id}"

    except psycopg2.IntegrityError as e:
        if conn:
            conn.rollback()
            conn.close()
        return f"Database integrity error: {str(e)}. Question {order_number} may already exist for this material."

    except Exception as e:
        if conn:
            conn.rollback()
            conn.close()
        return f"Error saving question {order_number}: {str(e)}"


def get_weak_concepts(study_session_id: int) -> str:
    """
    Retrieves weak concepts and material_id from a study session.

    Queries the study_sessions table for the weak_concepts JSONB field,
    which contains concepts the student struggled with during the study session.

    Args:
        study_session_id: ID of the study session

    Returns:
        JSON string with weak_concepts and material_id

    Example output:
    {
        "study_session_id": 1,
        "material_id": 5,
        "weak_concepts": [
            {"concept_id": "c1", "concept_name": "Variables", "reason": "..."},
            ...
        ]
    }
    """
    logger.info(f"[TOOL] get_weak_concepts called: study_session_id={study_session_id}")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        query = """
        SELECT material_id, weak_concepts
        FROM study_sessions
        WHERE id = %s;
        """

        cursor.execute(query, (study_session_id,))
        row = cursor.fetchone()

        cursor.close()
        conn.close()

        if not row:
            return json.dumps({
                "error": f"Study session {study_session_id} not found"
            })

        material_id, weak_concepts = row

        result = {
            "study_session_id": study_session_id,
            "material_id": material_id,
            "weak_concepts": weak_concepts if weak_concepts else []
        }

        logger.info(f"[TOOL] Found {len(result['weak_concepts'])} weak concepts for study session {study_session_id}")

        return json.dumps(result, indent=2)

    except Exception as e:
        logger.error(f"[TOOL] get_weak_concepts error: {str(e)}")
        return json.dumps({
            "error": f"Error retrieving weak concepts: {str(e)}"
        })


def get_material_concepts(material_id: int) -> str:
    """
    Retrieves all concepts for a material with user understanding levels.

    Queries the material_concepts table for all concepts mapped to the material,
    including the user_understanding field that tracks how well the student
    understands each concept.

    Args:
        material_id: ID of the material

    Returns:
        JSON string with all concepts and their understanding levels

    Example output:
    {
        "material_id": 5,
        "total_concepts": 8,
        "concepts": [
            {
                "concept_id": "c1",
                "concept_name": "Variables",
                "description": "...",
                "user_understanding": "weak",
                "page_start": 1,
                "page_end": 5
            },
            ...
        ]
    }
    """
    logger.info(f"[TOOL] get_material_concepts called: material_id={material_id}")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        query = """
        SELECT concept_id, concept_name, description, user_understanding,
               page_start, page_end, prerequisite_concepts
        FROM material_concepts
        WHERE material_id = %s
        ORDER BY page_start;
        """

        cursor.execute(query, (material_id,))
        rows = cursor.fetchall()

        cursor.close()
        conn.close()

        concepts = []
        for row in rows:
            concepts.append({
                "concept_id": row[0],
                "concept_name": row[1],
                "description": row[2],
                "user_understanding": row[3],
                "page_start": row[4],
                "page_end": row[5],
                "prerequisite_concepts": row[6]
            })

        result = {
            "material_id": material_id,
            "total_concepts": len(concepts),
            "concepts": concepts
        }

        logger.info(f"[TOOL] Found {len(concepts)} concepts for material {material_id}")

        return json.dumps(result, indent=2)

    except Exception as e:
        logger.error(f"[TOOL] get_material_concepts error: {str(e)}")
        return json.dumps({
            "error": f"Error retrieving material concepts: {str(e)}"
        })
