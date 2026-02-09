"""
ADK Tools for Question Generator Agent

Provides two tools:
1. download_pdf_from_gcs - Downloads PDF from GCS and extracts text content
2. save_mcq_question - Saves generated MCQ questions to PostgreSQL
"""
import tempfile
import os
import psycopg2
from psycopg2.extras import Json
from typing import Dict
import logging
import traceback
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


def download_pdf_from_gcs(storage_bucket: str, storage_path: str) -> str:
    """
    Downloads a PDF from Google Cloud Storage and extracts its text content.

    This tool:
    1. Downloads the PDF from GCS to a temporary file
    2. Extracts text from all pages
    3. Returns the full text content

    Args:
        storage_bucket: GCS bucket name (e.g., "ai-educate-materials")
        storage_path: Path to the PDF in the bucket (e.g., "materials/user123/python.pdf")

    Returns:
        Extracted text content from the PDF

    Example:
        >>> download_pdf_from_gcs("ai-educate-materials", "materials/user123/sample.pdf")
        "Chapter 1: Introduction\\n\\nThis chapter covers..."
    """
    logger.info(f"[TOOL] download_pdf_from_gcs called: bucket={storage_bucket}, path={storage_path}")

    try:
        if not storage_path or not storage_bucket:
            return "Error: storage_path and storage_bucket are required"

        storage_path = storage_path.lstrip('/')

        # Download from GCS
        storage_client = storage.Client()
        bucket = storage_client.bucket(storage_bucket)
        blob = bucket.blob(storage_path)

        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            temp_path = temp_file.name
            blob.download_to_filename(temp_path)
            logger.info(f"[TOOL] PDF downloaded to: {temp_path}")

        # Extract text
        reader = PdfReader(temp_path)
        text_content = []

        for i, page in enumerate(reader.pages):
            page_text = page.extract_text()
            text_content.append(f"\n--- Page {i+1} ---\n{page_text}")

        full_text = "\n".join(text_content)
        logger.info(f"[TOOL] Extracted {len(full_text)} characters from {len(reader.pages)} pages")

        # Clean up
        os.unlink(temp_path)

        return f"""Successfully loaded PDF from gs://{storage_bucket}/{storage_path}
Pages: {len(reader.pages)}
Characters: {len(full_text)}

PDF CONTENT:
{full_text}

---END OF PDF CONTENT---"""

    except Exception as e:
        logger.error(f"[TOOL] download_pdf_from_gcs error: {str(e)}")
        logger.error(f"[TOOL] Traceback:\n{traceback.format_exc()}")
        return f"Error downloading PDF: {str(e)}"


def save_mcq_question(
    material_id: int,
    question_text: str,
    options: Dict[str, str],
    correct_answer: str,
    explanation: str,
    difficulty: str,
    order_number: int
) -> str:
    """
    Saves an MCQ question to PostgreSQL database.

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
        ...     order_number=1
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

    assessment_type = "pre"

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
