"""
Post-Assessment Marker Tools

Tools for retrieving user answers, questions, saving assessment results,
and retrieving pre-assessment results for comparative feedback.
"""
import psycopg2
import json
from .config import DB_HOST, DB_NAME, DB_USER, DB_PASS, DB_PORT


def get_db_connection():
    """Creates PostgreSQL connection"""
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        port=DB_PORT
    )


def retrieve_previous_summary(assessment_id: int) -> str:
    """
    Retrieves the existing summary from the assessments table for the given assessment.
    Use this to check if there is a previous summary before generating a new one.
    If a previous summary exists, it should be used to enhance the new summary
    by comparing previous and current performance.

    Args:
        assessment_id: ID of the assessment

    Returns:
        JSON string with previous summary and score if exists, or indication that no previous summary exists

    Example output:
    {
        "assessment_id": 1,
        "has_previous_summary": true,
        "previous_score": 5,
        "previous_summary": "You scored 5/10 (50%)..."
    }
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT score, summary
            FROM assessments
            WHERE id = %s
            """,
            (assessment_id,)
        )
        row = cursor.fetchone()

        cursor.close()
        conn.close()

        if not row:
            return json.dumps({
                "assessment_id": assessment_id,
                "error": f"Assessment {assessment_id} not found"
            })

        score, summary = row

        if summary and summary.strip():
            return json.dumps({
                "assessment_id": assessment_id,
                "has_previous_summary": True,
                "previous_score": score,
                "previous_summary": summary
            }, indent=2)
        else:
            return json.dumps({
                "assessment_id": assessment_id,
                "has_previous_summary": False,
                "previous_score": score,
                "previous_summary": None
            }, indent=2)

    except Exception as e:
        return json.dumps({
            "error": f"Error retrieving previous summary: {str(e)}"
        })


def retrieve_user_answers(assessment_id: int) -> str:
    """
    Retrieves all user answers for an assessment with correctness status.

    Args:
        assessment_id: ID of the assessment

    Returns:
        JSON string with user answers and statistics

    Example output:
    {
        "assessment_id": 1,
        "total_answers": 10,
        "correct_count": 7,
        "incorrect_count": 3,
        "answers": [
            {
                "question_id": 1,
                "user_answer": "B",
                "is_correct": true,
                "answered_at": "2024-01-01T10:00:00"
            },
            ...
        ]
    }
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # First verify assessment exists
        cursor.execute("SELECT id FROM assessments WHERE id = %s", (assessment_id,))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return json.dumps({
                "error": f"Assessment {assessment_id} not found"
            })

        # Retrieve all user answers
        query = """
        SELECT
            question_id,
            user_answer,
            is_correct,
            answered_at
        FROM user_answers
        WHERE assessment_id = %s
        ORDER BY question_id;
        """

        cursor.execute(query, (assessment_id,))
        rows = cursor.fetchall()

        # Process results
        answers = []
        correct_count = 0
        incorrect_count = 0

        for row in rows:
            question_id, user_answer, is_correct, answered_at = row

            answers.append({
                "question_id": question_id,
                "user_answer": user_answer,
                "is_correct": is_correct,
                "answered_at": answered_at.isoformat() if answered_at else None
            })

            if is_correct:
                correct_count += 1
            else:
                incorrect_count += 1

        cursor.close()
        conn.close()

        result = {
            "assessment_id": assessment_id,
            "total_answers": len(answers),
            "correct_count": correct_count,
            "incorrect_count": incorrect_count,
            "answers": answers
        }

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({
            "error": f"Error retrieving user answers: {str(e)}"
        })


def retrieve_assessment_questions(assessment_id: int) -> str:
    """
    Retrieves all post-assessment questions for an assessment with metadata.

    Only returns questions with assessment_type = 'post'.

    Args:
        assessment_id: ID of the assessment

    Returns:
        JSON string with question details

    Example output:
    {
        "assessment_id": 1,
        "material_id": 5,
        "total_questions": 10,
        "difficulty_distribution": {"easy": 2, "medium": 3, "hard": 5},
        "questions": [
            {
                "question_id": 1,
                "question_text": "What is...",
                "correct_answer": "B",
                "difficulty": "hard",
                "explanation": "...",
                "order_number": 1
            },
            ...
        ]
    }
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get assessment details
        cursor.execute(
            "SELECT material_id, total_questions FROM assessments WHERE id = %s",
            (assessment_id,)
        )
        assessment_row = cursor.fetchone()

        if not assessment_row:
            cursor.close()
            conn.close()
            return json.dumps({
                "error": f"Assessment {assessment_id} not found"
            })

        material_id, total_questions = assessment_row

        # Retrieve post-assessment questions for this material
        query = """
        SELECT
            id,
            question_text,
            correct_answer,
            difficulty,
            explanation,
            order_number
        FROM questions
        WHERE material_id = %s AND assessment_type = 'post'
        ORDER BY order_number;
        """

        cursor.execute(query, (material_id,))
        rows = cursor.fetchall()

        # Process results
        questions = []
        difficulty_distribution = {}

        for row in rows:
            q_id, q_text, correct_ans, difficulty, explanation, order_num = row

            questions.append({
                "question_id": q_id,
                "question_text": q_text,
                "correct_answer": correct_ans,
                "difficulty": difficulty or "medium",
                "explanation": explanation,
                "order_number": order_num
            })

            # Count difficulty distribution
            diff = difficulty or "medium"
            difficulty_distribution[diff] = difficulty_distribution.get(diff, 0) + 1

        cursor.close()
        conn.close()

        result = {
            "assessment_id": assessment_id,
            "material_id": material_id,
            "total_questions": total_questions,
            "difficulty_distribution": difficulty_distribution,
            "questions": questions
        }

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({
            "error": f"Error retrieving assessment questions: {str(e)}"
        })


def save_assessment_results(assessment_id: int, score: int, summary: str) -> str:
    """
    Saves marking results to the assessments table.

    Args:
        assessment_id: ID of the assessment
        score: Total correct answers (0-10)
        summary: AI-generated assessment summary

    Returns:
        Success message with assessment details

    Example:
        >>> save_assessment_results(1, 7, "Good performance...")
        "Successfully marked assessment 1 with score 7/10. Status: completed"
    """
    try:
        # Validation
        if not isinstance(score, int) or score < 0 or score > 10:
            return json.dumps({
                "error": f"Validation error: score must be integer 0-10, got {score}"
            })

        if not summary or not summary.strip():
            return json.dumps({
                "error": "Validation error: summary cannot be empty"
            })

        conn = get_db_connection()
        cursor = conn.cursor()

        # Verify assessment exists
        cursor.execute("SELECT id FROM assessments WHERE id = %s", (assessment_id,))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return json.dumps({
                "error": f"Assessment {assessment_id} not found"
            })

        # Update assessment with results
        update_query = """
        UPDATE assessments
        SET
            score = %s,
            summary = %s,
            status = 'completed',
            completed_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s;
        """

        cursor.execute(update_query, (score, summary.strip(), assessment_id))
        conn.commit()

        cursor.close()
        conn.close()

        return f"Successfully marked assessment {assessment_id} with score {score}/10. Status: completed"

    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return json.dumps({
            "error": f"Error saving assessment results: {str(e)}"
        })


def retrieve_pre_assessment_results(assessment_id: int) -> str:
    """
    Retrieves pre-assessment results for comparison with post-assessment.

    Looks up the study session linked to the post-assessment's assessment_id,
    then fetches the pre-assessment score and summary for comparative analysis.

    Args:
        assessment_id: ID of the post-assessment

    Returns:
        JSON string with pre-assessment score, summary, and comparison data

    Example output:
    {
        "post_assessment_id": 5,
        "pre_assessment_id": 2,
        "pre_assessment_score": 6,
        "pre_assessment_total": 10,
        "pre_assessment_summary": "You scored 6/10...",
        "weak_concepts": [...],
        "study_session_id": 3
    }
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Find the study session that has this post_assessment_id
        cursor.execute(
            """
            SELECT id, pre_assessment_id, weak_concepts
            FROM study_sessions
            WHERE post_assessment_id = %s
            """,
            (assessment_id,)
        )
        session_row = cursor.fetchone()

        if not session_row:
            cursor.close()
            conn.close()
            return json.dumps({
                "error": f"No study session found with post_assessment_id = {assessment_id}"
            })

        study_session_id, pre_assessment_id, weak_concepts = session_row

        if not pre_assessment_id:
            cursor.close()
            conn.close()
            return json.dumps({
                "error": f"Study session {study_session_id} has no pre-assessment linked",
                "study_session_id": study_session_id,
                "weak_concepts": weak_concepts
            })

        # Fetch pre-assessment results
        cursor.execute(
            """
            SELECT score, total_questions, summary, status
            FROM assessments
            WHERE id = %s
            """,
            (pre_assessment_id,)
        )
        pre_row = cursor.fetchone()

        cursor.close()
        conn.close()

        if not pre_row:
            return json.dumps({
                "error": f"Pre-assessment {pre_assessment_id} not found in assessments table",
                "study_session_id": study_session_id,
                "pre_assessment_id": pre_assessment_id
            })

        pre_score, pre_total, pre_summary, pre_status = pre_row

        result = {
            "post_assessment_id": assessment_id,
            "pre_assessment_id": pre_assessment_id,
            "pre_assessment_score": pre_score,
            "pre_assessment_total": pre_total,
            "pre_assessment_summary": pre_summary,
            "pre_assessment_status": pre_status,
            "weak_concepts": weak_concepts if weak_concepts else [],
            "study_session_id": study_session_id
        }

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({
            "error": f"Error retrieving pre-assessment results: {str(e)}"
        })
