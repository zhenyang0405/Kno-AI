"""
FastAPI routes for post-assessment question generation and marking

Endpoints:
- POST /generate-questions: Generate 10 MCQ questions targeting weak concepts
- POST /mark-assessment: Mark a completed post-assessment with comparative feedback
- POST /start-assessment: Start a new post-assessment attempt
- POST /save-answer: Save a user answer
- POST /update-assessment-status: Update assessment status
- GET /questions/{material_id}: Fetch post-assessment questions
- GET /health: Health check
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
import psycopg2
import logging
import json
import traceback


def parse_structured_summary(summary: Optional[str]) -> Optional[dict]:
    """Helper to parse JSON summary from string"""
    if not summary:
        return None
    try:
        # remove markdown code blocks if present
        clean_summary = summary.replace('```json', '').replace('```', '').strip()
        return json.loads(clean_summary)
    except Exception:
        return None

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from question_generator.agent import question_generator_agent
from assessment_marker.agent import assessment_marker_agent
from config import DB_HOST, DB_NAME, DB_USER, DB_PASS, DB_PORT, MaterialStatus, AssessmentStatus
from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types



router = APIRouter(prefix="/api/post-assessment", tags=["post-assessment"])


class GenerateQuestionsRequest(BaseModel):
    """Request model for question generation"""
    material_id: int = Field(..., description="Database ID of the material")
    storage_path: str = Field(..., description="GCS path (e.g., 'materials/user123/python.pdf')")
    storage_bucket: str = Field(..., description="GCS bucket name")
    session_id: str = Field(..., description="Session ID")
    user_id: int = Field(..., description="User ID")

    class Config:
        json_schema_extra = {
            "example": {
                "material_id": 1,
                "storage_path": "materials/user123/sample.pdf",
                "storage_bucket": "ai-educate-materials"
            }
        }


class GenerateQuestionsResponse(BaseModel):
    """Response model for question generation"""
    success: bool
    material_id: int
    questions_generated: int
    message: str
    assessment_type: str
    assessment_status: Optional[str] = None
    score: Optional[int] = None
    total_questions: Optional[int] = None
    percentage: Optional[float] = None
    summary: Optional[str] = None
    structured_summary: Optional[dict] = None


class MarkAssessmentRequest(BaseModel):
    """Request model for assessment marking"""
    assessment_id: int = Field(..., description="Database ID of the assessment to mark")
    session_id: str = Field(..., description="Session ID")
    user_id: int = Field(..., description="User ID")

    class Config:
        json_schema_extra = {
            "example": {
                "assessment_id": 1
            }
        }


class MarkAssessmentResponse(BaseModel):
    """Response model for assessment marking"""
    success: bool
    assessment_id: int
    score: int
    total_questions: int
    percentage: float
    summary: str
    structured_summary: Optional[dict] = None
    message: str


class StartAssessmentRequest(BaseModel):
    """Request model for starting a post-assessment"""
    user_id: int
    material_id: int
    study_session_id: int


class StartAssessmentResponse(BaseModel):
    """Response model for starting an assessment"""
    success: bool
    assessment_id: int
    message: str


class SaveAnswerRequest(BaseModel):
    """Request model for saving a user answer"""
    assessment_id: int
    question_id: int
    user_answer: str


class SaveAnswerResponse(BaseModel):
    """Response model for saving a user answer"""
    success: bool
    is_correct: bool
    message: str


class UpdateAssessmentStatusRequest(BaseModel):
    """Request model for updating assessment status"""
    assessment_id: int
    status: str



def get_db_connection():
    """Create database connection"""
    try:
        logger.debug(f"Attempting database connection: host={DB_HOST}, db={DB_NAME}, user={DB_USER}, port={DB_PORT}")
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            port=DB_PORT
        )
        logger.debug("Database connection successful")
        return conn
    except Exception as e:
        logger.error(f"Database connection failed: {str(e)}")
        logger.error(f"Connection details: host={DB_HOST}, db={DB_NAME}, user={DB_USER}, port={DB_PORT}")
        raise


def update_material_status(material_id: int, status: str) -> None:
    """
    Update material status in database

    Args:
        material_id: ID of the material
        status: New status value
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        update_query = """
        UPDATE materials
        SET status = %s, updated_at = CURRENT_TIMESTAMP
        WHERE id = %s;
        """

        cursor.execute(update_query, (status, material_id))
        conn.commit()

        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error updating material status: {e}")
        if conn:
            conn.rollback()
            conn.close()
        raise


def verify_questions_count(material_id: int, assessment_type: str) -> int:
    """
    Verify how many post-assessment questions were saved for a material, filtered by assessment_type

    Args:
        material_id: ID of the material
        assessment_type: Type of the assessment to filter by

    Returns:
        Number of post-assessment questions in database
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        count_query = """
        SELECT COUNT(*) FROM questions WHERE material_id = %s AND assessment_type = %s;
        """
        cursor.execute(count_query, (material_id, assessment_type))

        count = cursor.fetchone()[0]

        cursor.close()
        conn.close()

        return count
    except Exception as e:
        print(f"Error verifying questions count: {e}")
        return 0


@router.post("/generate-questions", response_model=GenerateQuestionsResponse)
async def generate_questions(request: GenerateQuestionsRequest):
    """
    Generate 10 post-assessment MCQ questions from a PDF material using ADK agent.

    This endpoint:
    1. Updates material status to 'processing'
    2. Invokes the question_generator agent with session_id
    3. Agent retrieves weak concepts and generates harder, targeted questions
    4. Questions are saved to PostgreSQL with assessment_type='post'
    5. Updates material status to 'completed' or 'failed'

    Args:
        request: GenerateQuestionsRequest with material_id, storage_path, storage_bucket

    Returns:
        GenerateQuestionsResponse with success status and questions count

    Raises:
        HTTPException: If generation fails
    """
    logger.info(f"=== GENERATE POST-ASSESSMENT QUESTIONS START ===")
    logger.info(f"Request: material_id={request.material_id}, storage_path={request.storage_path}, storage_bucket={request.storage_bucket}")

    try:
        # Check if a post-assessment already exists for this material
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, status, score, total_questions, summary
            FROM assessments WHERE material_id = %s AND user_id = %s AND assessment_type = 'post'
            ORDER BY created_at DESC LIMIT 1
            """,
            (request.material_id, request.user_id)
        )
        existing_assessment = cursor.fetchone()
        cursor.close()
        conn.close()

        if existing_assessment:
            assessment_id, assessment_status, score, total_questions, summary = existing_assessment
            logger.info(f"Found existing post-assessment {assessment_id} with status '{assessment_status}' for material {request.material_id}")

            if assessment_status == AssessmentStatus.COMPLETED:
                percentage = (score / total_questions) * 100 if score is not None and total_questions else 0
                logger.info(f"Post-assessment {assessment_id} is completed, returning results")
                return GenerateQuestionsResponse(
                    success=True,
                    material_id=request.material_id,
                    questions_generated=total_questions or 0,
                    message=f"Post-assessment already completed with score {score}/{total_questions}",
                    assessment_type="post",
                    assessment_status=assessment_status,
                    score=score,
                    total_questions=total_questions,
                    percentage=round(percentage, 2),
                    summary=summary,
                    structured_summary=parse_structured_summary(summary)
                )

        # Check if post-assessment questions already exist for this material filtered by assessment_type
        existing_count = verify_questions_count(request.material_id, "post")
        if existing_count > 0:
            logger.info(f"Found {existing_count} existing post-assessment questions for material {request.material_id}, skipping generation")
            return GenerateQuestionsResponse(
                success=True,
                material_id=request.material_id,
                questions_generated=existing_count,
                message=f"Post-assessment questions already exist ({existing_count} found), skipping generation",
                assessment_type="post",
                assessment_status=existing_assessment[1] if existing_assessment else None
            )

        # Step 1: Update material status to 'processing'
        logger.info(f"[1/4] Updating material {request.material_id} status to 'processing'")
        update_material_status(request.material_id, MaterialStatus.PROCESSING)
        logger.info(f"[1/4] Status updated successfully")

        # Step 2: Run agent
        logger.info(f"[2/4] Invoking question_generator_agent")
        user_message_text = f"material_id: {request.material_id}, storage_bucket: {request.storage_bucket}, storage_path: {request.storage_path}"
        logger.debug(f"Agent input: {user_message_text}")

        try:
            session_service = InMemorySessionService()
            runner = Runner(
                app_name="question_generator",
                agent=question_generator_agent,
                session_service=session_service
            )
            
            # Wrap message in Content object
            user_content = types.Content(
                role="user", 
                parts=[types.Part(text=user_message_text)]
            )
            
            # Ensure session exists in the fresh memory service
            await session_service.create_session(
                app_name="question_generator",
                user_id=str(request.user_id),
                session_id=str(request.session_id)
            )

            async for event in runner.run_async(
                user_id=str(request.user_id), 
                session_id=str(request.session_id), 
                new_message=user_content
            ):
                pass

            logger.info(f"[2/4] Agent completed")

        except Exception as agent_error:
            logger.error(f"[2/4] Agent execution failed: {str(agent_error)}")
            logger.error(f"Agent error traceback:\n{traceback.format_exc()}")
            raise

        # Step 3: Verify questions were saved
        logger.info(f"[3/4] Verifying questions were saved to database")
        questions_count = verify_questions_count(request.material_id, "post")
        logger.info(f"[3/4] Found {questions_count} post-assessment questions in database")

        # Step 4: Update status based on result
        if questions_count == 10:
            logger.info(f"[4/4] All 10 questions saved, updating status to 'completed'")
            update_material_status(request.material_id, MaterialStatus.COMPLETED)
            logger.info(f"[4/4] Status updated to 'completed'")
            logger.info(f"=== GENERATE POST-ASSESSMENT QUESTIONS SUCCESS ===")

            return GenerateQuestionsResponse(
                success=True,
                material_id=request.material_id,
                questions_generated=questions_count,
                message=f"Successfully generated {questions_count} post-assessment questions",
                assessment_type="post"
            )
        else:
            logger.warning(f"[4/4] Expected 10 questions but only {questions_count} were saved")
            logger.info(f"[4/4] Updating status to 'failed'")
            update_material_status(request.material_id, MaterialStatus.FAILED)
            logger.error(f"=== GENERATE POST-ASSESSMENT QUESTIONS FAILED (incomplete) ===")

            raise HTTPException(
                status_code=500,
                detail=f"Expected 10 questions but only {questions_count} were saved"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"=== GENERATE POST-ASSESSMENT QUESTIONS ERROR ===")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error message: {str(e)}")
        logger.error(f"Full traceback:\n{traceback.format_exc()}")

        # Update material status to 'failed'
        try:
            logger.info(f"Attempting to update material status to 'failed'")
            update_material_status(request.material_id, MaterialStatus.FAILED)
            logger.info(f"Status updated to 'failed'")
        except Exception as status_error:
            logger.error(f"Failed to update status: {str(status_error)}")

        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate questions: {type(e).__name__}: {str(e)}"
        )


@router.post("/start-assessment", response_model=StartAssessmentResponse)
async def start_assessment(request: StartAssessmentRequest):
    """Start a new post-assessment attempt and link it to the study session"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if a post-assessment already exists for this material and user
        cursor.execute(
            """
            SELECT id FROM assessments
            WHERE user_id = %s AND material_id = %s AND assessment_type = 'post'
            ORDER BY created_at DESC LIMIT 1
            """,
            (request.user_id, request.material_id)
        )
        existing = cursor.fetchone()

        if existing:
            assessment_id = existing[0]
            cursor.close()
            conn.close()
            return StartAssessmentResponse(
                success=True,
                assessment_id=assessment_id,
                message="Post-assessment already exists"
            )

        # Create assessment with assessment_type='post'
        cursor.execute(
            """
            INSERT INTO assessments (user_id, material_id, status, assessment_type, started_at)
            VALUES (%s, %s, %s, 'post', CURRENT_TIMESTAMP) RETURNING id
            """,
            (request.user_id, request.material_id, AssessmentStatus.IN_PROGRESS)
        )
        assessment_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()

        return StartAssessmentResponse(
            success=True,
            assessment_id=assessment_id,
            message="Post-assessment started successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start post-assessment: {str(e)}")


@router.get("/questions/{material_id}")
async def get_questions(material_id: int):
    """Fetch all post-assessment questions for a material"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, question_text, options, correct_answer, difficulty, order_number, explanation
            FROM questions WHERE material_id = %s AND assessment_type = 'post' ORDER BY order_number
            """,
            (material_id,)
        )
        rows = cursor.fetchall()

        questions = []
        for row in rows:
            questions.append({
                "id": row[0],
                "question_text": row[1],
                "options": row[2],
                "correct_answer": row[3],
                "difficulty": row[4],
                "order_number": row[5],
                "explanation": row[6]
            })

        cursor.close()
        conn.close()

        return {"success": True, "questions": questions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch questions: {str(e)}")


@router.post("/save-answer", response_model=SaveAnswerResponse)
async def save_answer(request: SaveAnswerRequest):
    """Save a user answer and check correctness"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get correct answer
        cursor.execute("SELECT correct_answer FROM questions WHERE id = %s", (request.question_id,))
        result = cursor.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="Question not found")

        correct_answer = result[0]
        is_correct = (request.user_answer == correct_answer)

        # Save answer (upsert based on unique constraint assessment_id, question_id)
        cursor.execute(
            """
            INSERT INTO user_answers (assessment_id, question_id, user_answer, is_correct)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (assessment_id, question_id)
            DO UPDATE SET user_answer = EXCLUDED.user_answer, is_correct = EXCLUDED.is_correct, answered_at = CURRENT_TIMESTAMP
            """,
            (request.assessment_id, request.question_id, request.user_answer, is_correct)
        )

        conn.commit()
        cursor.close()
        conn.close()

        return SaveAnswerResponse(
            success=True,
            is_correct=is_correct,
            message="Answer saved successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save answer: {str(e)}")



def update_assessment_status(assessment_id: int, status: str) -> None:
    """
    Update assessment status in database

    Args:
        assessment_id: ID of the assessment
        status: New status value
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        update_query = """
        UPDATE assessments
        SET status = %s, updated_at = CURRENT_TIMESTAMP
        WHERE id = %s;
        """

        cursor.execute(update_query, (status, assessment_id))
        conn.commit()

        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error updating assessment status: {e}")
        if conn:
            conn.rollback()
            conn.close()
        raise


@router.post("/update-assessment-status")
async def update_assessment_status_endpoint(request: UpdateAssessmentStatusRequest):
    """Endpoint to update assessment status"""
    try:
        update_assessment_status(request.assessment_id, request.status)
        return {"success": True, "message": f"Assessment status updated to {request.status}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def get_assessment_results(assessment_id: int) -> dict:
    """
    Retrieve saved assessment results

    Args:
        assessment_id: ID of the assessment

    Returns:
        Dictionary with score, total_questions, summary, status, and structured_summary
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        query = """
        SELECT score, total_questions, summary, status
        FROM assessments
        WHERE id = %s;
        """

        cursor.execute(query, (assessment_id,))
        result = cursor.fetchone()

        cursor.close()
        conn.close()

        if not result:
            return None

        score, total_questions, summary, status = result
        
        # specific logic to parse JSON summary if possible
        structured_summary = parse_structured_summary(summary)

        return {
            "score": score,
            "total_questions": total_questions,
            "summary": summary,
            "structured_summary": structured_summary,
            "status": status
        }
    except Exception as e:
        print(f"Error retrieving assessment results: {e}")
        return None


@router.post("/mark-assessment", response_model=MarkAssessmentResponse)
async def mark_assessment(request: MarkAssessmentRequest):
    """
    Mark a completed post-assessment using ADK agent with comparative feedback.

    This endpoint:
    1. Updates assessment status to 'processing'
    2. Invokes the assessment_marker agent
    3. Agent retrieves user answers, questions, and pre-assessment results
    4. Agent calculates score and generates comparative summary
    5. Agent saves results to database
    6. Returns final results with score and feedback

    Args:
        request: MarkAssessmentRequest with assessment_id

    Returns:
        MarkAssessmentResponse with score and AI-generated comparative summary

    Raises:
        HTTPException: If marking fails
    """
    try:
        # Update assessment status to 'processing'
        update_assessment_status(request.assessment_id, 'processing')


        # Use Runner to execute the marking agent with in-memory session service
        session_service = InMemorySessionService()
        runner = Runner(
            app_name="assessment_marker",
            agent=assessment_marker_agent,
            session_service=session_service
        )
        
        user_message_text = f"Mark post-assessment {request.assessment_id}."
        
        # Wrap message in Content object
        user_content = types.Content(
            role="user", 
            parts=[types.Part(text=user_message_text)]
        )
        
        # Ensure session exists in the fresh memory service
        await session_service.create_session(
            app_name="assessment_marker",
            user_id=str(request.user_id), 
            session_id=str(request.session_id)
        )

        async for event in runner.run_async(
            user_id=str(request.user_id), 
            session_id=str(request.session_id), 
            new_message=user_content
        ):
            pass

        # Retrieve saved results from database
        results = get_assessment_results(request.assessment_id)

        if not results:
            raise HTTPException(
                status_code=500,
                detail="Assessment results not found after marking"
            )

        if results['status'] != 'completed':
            raise HTTPException(
                status_code=500,
                detail=f"Assessment status is '{results['status']}', expected 'completed'"
            )

        # Calculate percentage
        percentage = (results['score'] / results['total_questions']) * 100

        return MarkAssessmentResponse(
            success=True,
            assessment_id=request.assessment_id,
            score=results['score'],
            total_questions=results['total_questions'],
            percentage=round(percentage, 2),
            summary=results['summary'],
            structured_summary=results.get('structured_summary'),
            message=f"Successfully marked post-assessment {request.assessment_id}"
        )

    except HTTPException:
        raise
    except Exception as e:
        # Update assessment status back to 'in_progress' on failure
        try:
            update_assessment_status(request.assessment_id, 'in_progress')
        except:
            pass

        raise HTTPException(
            status_code=500,
            detail=f"Failed to mark assessment: {str(e)}"
        )


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "post-assessment-api"}
