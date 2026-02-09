"""
FastAPI Routes for Pre-Active-Learn API

Handles workspace preparation before active learning:
- User management and Firebase UID mapping
- Study session lifecycle
- Material context caching (Gemini)
- Concept extraction
- Workspace initialization
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List, Dict
import logging
import traceback

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pre-active-learn", tags=["pre-active-learn"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class InitializeWorkspaceRequest(BaseModel):
    """Request model for workspace initialization"""
    study_session_id: int
    user_id: int


class InitializeWorkspaceResponse(BaseModel):
    """Response model for workspace initialization"""
    success: bool
    study_session_id: int
    material_id: int
    cache_status: str
    message: str


class CreateStudySessionRequest(BaseModel):
    """Request model for creating a study session"""
    user_id: int
    material_id: int
    pre_assessment_id: Optional[int] = None
    weak_concepts: Optional[List[str]] = None


class UpdateStudySessionRequest(BaseModel):
    """Request model for updating a study session"""
    status: Optional[str] = None
    weak_concepts: Optional[List[str]] = None


class BatchUpdateRequest(BaseModel):
    """Request model for batch updating concept understanding"""
    updates: List[Dict]


class GetUserRequest(BaseModel):
    """Request model for getting user by Firebase UID"""
    firebase_uid: str
    email: Optional[str] = None
    name: Optional[str] = None


# ============================================================================
# BACKGROUND TASKS
# ============================================================================

def create_cache_background(study_session_id: int):
    """Background task to create material cache and extract concepts"""
    try:
        from material_cache_service import create_material_cache
        from concept_extraction_service import extract_material_concepts, check_concepts_exist
        
        logger.info(f"Background: Creating cache for study_session_id={study_session_id}")
        cache_result = create_material_cache(study_session_id)
        logger.info(f"Background: Cache created successfully - {cache_result['cache_name']}")
        
        # Extract concepts using the cache
        material_id = cache_result['material_id']
        
        # Check if concepts already exist
        if not check_concepts_exist(material_id):
            logger.info(f"Background: Extracting concepts for material_id={material_id}")
            concepts = extract_material_concepts(material_id, cache_result['cache_name'])
            logger.info(f"Background: Extracted {len(concepts)} concepts")
        else:
            logger.info(f"Background: Concepts already exist for material_id={material_id}, skipping extraction")
            
    except Exception as e:
        logger.error(f"Background: Failed to create cache or extract concepts - {e}")
        logger.error(traceback.format_exc())


# ============================================================================
# WORKSPACE INITIALIZATION
# ============================================================================

@router.post("/initialize-workspace", response_model=InitializeWorkspaceResponse)
async def initialize_workspace(request: InitializeWorkspaceRequest, background_tasks: BackgroundTasks):
    """
    Initialize active-learning workspace when user launches into it
    
    This endpoint:
    1. Gets material info from study session
    2. Checks if cache exists for the material
    3. If not, triggers cache creation in background
    4. Returns immediately without blocking
    
    The cache will be available shortly for use in subsequent requests.
    """
    try:
        from material_cache_service import get_active_cache, get_db_connection
        from concept_extraction_service import check_concepts_exist
        
        logger.info(f"Initializing workspace for study_session_id={request.study_session_id}")
        
        # Get material_id from study_session
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT material_id FROM study_sessions WHERE id = %s",
            (request.study_session_id,)
        )
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not result:
            raise HTTPException(status_code=404, detail=f"Study session {request.study_session_id} not found")
        
        material_id = result[0]
        logger.info(f"Found material_id={material_id}")
        
        # Check if cache exists
        cache_name = get_active_cache(material_id)

        # Check if concepts exist
        concepts_exist = check_concepts_exist(material_id)
        
        if cache_name and concepts_exist:
            logger.info(f"Cache and concepts already exist: {cache_name}")
            return InitializeWorkspaceResponse(
                success=True,
                study_session_id=request.study_session_id,
                material_id=material_id,
                cache_status="exists",
                message="Workspace initialized with existing cache"
            )
        else:
            logger.info("No cache found, creating in background")
            # Trigger cache creation in background
            background_tasks.add_task(create_cache_background, request.study_session_id)
            
            return InitializeWorkspaceResponse(
                success=True,
                study_session_id=request.study_session_id,
                material_id=material_id,
                cache_status="creating",
                message="Workspace initialized, cache creation started in background"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error initializing workspace: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to initialize workspace: {str(e)}")


# ============================================================================
# MATERIAL CACHE ENDPOINTS
# ============================================================================

@router.post("/study-sessions/{study_session_id}/cache")
async def create_session_cache(study_session_id: int):
    """
    Create or retrieve Gemini context cache for a study session's material
    
    This endpoint:
    1. Checks if an active cache exists for the material
    2. If not, creates a new cache by uploading PDF to Gemini
    3. Returns cache information
    """
    try:
        from material_cache_service import create_material_cache, get_active_cache
        
        logger.info(f"Cache creation requested for study_session_id={study_session_id}")
        
        # This will check for existing cache and create if needed
        result = create_material_cache(study_session_id)
        
        # Check if this was an existing cache or newly created
        material_id = result['material_id']
        existing = get_active_cache(material_id)
        is_new = existing == result['cache_name']
        
        return {
            **result,
            "message": "Cache retrieved" if not is_new else "Cache created successfully"
        }
        
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating cache: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to create cache: {str(e)}")


# ============================================================================
# CONCEPT EXTRACTION ENDPOINTS
# ============================================================================

@router.get("/materials/{material_id}/concepts")
async def get_material_concepts(material_id: int):
    """
    Get all extracted concepts for a material
    
    Returns list of concepts with their details
    """
    try:
        from concept_extraction_service import get_material_concepts
        
        concepts = get_material_concepts(material_id)
        
        return {
            "success": True,
            "material_id": material_id,
            "concepts": concepts,
            "count": len(concepts)
        }
        
    except Exception as e:
        logger.error(f"Error getting concepts: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get concepts: {str(e)}")


@router.post("/concepts/{concept_id}/understanding")
async def update_concept_understanding_endpoint(concept_id: int, user_understanding: str):
    """
    Update user's understanding level for a specific concept
    
    Args:
        concept_id: Database ID of the concept
        user_understanding: Understanding level (e.g., "struggling", "partial", "confident", "mastered")
    """
    try:
        from concept_extraction_service import update_concept_understanding
        
        success = update_concept_understanding(concept_id, user_understanding)
        
        if success:
            return {
                "success": True,
                "concept_id": concept_id,
                "user_understanding": user_understanding,
                "message": "Understanding level updated"
            }
        else:
            raise HTTPException(status_code=404, detail=f"Concept {concept_id} not found")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating understanding: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update understanding: {str(e)}")


@router.post("/concepts/batch-update-understanding")
async def batch_update_understanding(request: BatchUpdateRequest):
    """
    Update understanding levels for multiple concepts in one request
    
    Request body format:
    {
        "updates": [
            {"concept_id": 1, "user_understanding": "mastered"},
            {"concept_id": 2, "user_understanding": "struggling"}
        ]
    }
    """
    try:
        from concept_extraction_service import update_multiple_concepts_understanding
        
        result = update_multiple_concepts_understanding(request.updates)
        
        return {
            "success": True,
            "updated": result['updated'],
            "failed": result['failed'],
            "message": f"Updated {result['updated']} concepts, {result['failed']} failed"
        }
        
    except Exception as e:
        logger.error(f"Error in batch update: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to batch update: {str(e)}")


# ============================================================================
# STUDY SESSION ENDPOINTS
# ============================================================================

@router.post("/study-sessions")
async def create_study_session_endpoint(request: CreateStudySessionRequest):
    """Create a new study session or return existing one"""
    try:
        from study_session_service import create_study_session
        
        session = create_study_session(
            user_id=request.user_id,
            material_id=request.material_id,
            pre_assessment_id=request.pre_assessment_id,
            weak_concepts=request.weak_concepts
        )
        
        return {
            "success": True,
            "session": session,
            "message": "Study session created successfully"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating study session: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create study session: {str(e)}")


@router.get("/study-sessions/{session_id}")
async def get_study_session_endpoint(session_id: int):
    """Get study session by ID"""
    try:
        from study_session_service import get_study_session
        
        session = get_study_session(session_id)
        
        if not session:
            raise HTTPException(status_code=404, detail=f"Study session {session_id} not found")
        
        return {
            "success": True,
            "session": session
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting study session: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get study session: {str(e)}")


@router.get("/users/{user_id}/study-sessions")
async def get_user_study_sessions_endpoint(user_id: int, status: Optional[str] = None):
    """Get all study sessions for a user, optionally filtered by status"""
    try:
        from study_session_service import get_user_study_sessions
        
        sessions = get_user_study_sessions(user_id, status)
        
        return {
            "success": True,
            "user_id": user_id,
            "sessions": sessions,
            "count": len(sessions)
        }
        
    except Exception as e:
        logger.error(f"Error getting user study sessions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get user study sessions: {str(e)}")


@router.patch("/study-sessions/{session_id}")
async def update_study_session_endpoint(session_id: int, request: UpdateStudySessionRequest):
    """Update study session details"""
    try:
        from study_session_service import update_study_session
        
        # Build updates dict
        updates = {}
        if request.status is not None:
            updates['status'] = request.status
        if request.weak_concepts is not None:
            updates['weak_concepts'] = request.weak_concepts
        
        if not updates:
            raise HTTPException(status_code=400, detail="No updates provided")
        
        success = update_study_session(session_id, **updates)
        
        if success:
            return {
                "success": True,
                "session_id": session_id,
                "message": "Study session updated successfully"
            }
        else:
            raise HTTPException(status_code=404, detail=f"Study session {session_id} not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating study session: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update study session: {str(e)}")


@router.post("/study-sessions/{session_id}/complete")
async def complete_study_session_endpoint(session_id: int):
    """Mark study session as completed"""
    try:
        from study_session_service import complete_study_session
        
        success = complete_study_session(session_id)
        
        if success:
            return {
                "success": True,
                "session_id": session_id,
                "message": "Study session completed successfully"
            }
        else:
            raise HTTPException(status_code=404, detail=f"Study session {session_id} not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error completing study session: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to complete study session: {str(e)}")


@router.delete("/study-sessions/{session_id}")
async def delete_study_session_endpoint(session_id: int):
    """Delete a study session"""
    try:
        from study_session_service import delete_study_session
        
        success = delete_study_session(session_id)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Study session {session_id} not found")
        
        return {
            "success": True,
            "session_id": session_id,
            "message": "Study session deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting study session: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete study session: {str(e)}")


# ============================================================================
# USER MANAGEMENT ENDPOINTS
# ============================================================================

@router.post("/users/get-or-create")
async def get_or_create_user_endpoint(request: GetUserRequest):
    """
    Get user by Firebase UID, or create if doesn't exist
    
    This endpoint maps Firebase authentication UID to database user_id.
    Call this when a user logs in to get their database ID.
    """
    try:
        from user_service import get_or_create_user_by_firebase_uid
        
        user = get_or_create_user_by_firebase_uid(
            firebase_uid=request.firebase_uid
        )
        
        return {
            "success": True,
            "user": user
        }
        
    except Exception as e:
        logger.error(f"Error getting/creating user: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to get/create user: {str(e)}")


@router.get("/users/{user_id}")
async def get_user_endpoint(user_id: int):
    """Get user by database ID"""
    try:
        from user_service import get_user_by_id
        
        user = get_user_by_id(user_id)
        
        if not user:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        
        return {
            "success": True,
            "user": user
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get user: {str(e)}")


# ============================================================================
# HEALTH CHECK
# ============================================================================

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "pre-active-learn-api"}
