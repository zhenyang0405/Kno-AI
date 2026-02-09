from fastapi import APIRouter, Depends, Form
from dependencies import get_current_user
from services import knowledge_service
from models.knowledge import KnowledgeCreateResponse
from typing import List


router = APIRouter()


@router.post("/save-knowledge", response_model=KnowledgeCreateResponse)
async def save_knowledge(
    name: str = Form(...),
    description: str = Form(...),
    user: dict = Depends(get_current_user)
):
    """Create a new knowledge entry for the authenticated user."""
    firebase_uid = user['uid']

    knowledge_id = knowledge_service.create_knowledge(firebase_uid, name, description)

    return {"status": "success", "knowledge_id": knowledge_id}


@router.get("/knowledge")
async def get_knowledge_list(
    user: dict = Depends(get_current_user)
):
    """Get all knowledge entries for the authenticated user."""
    firebase_uid = user['uid']
    knowledge_list = knowledge_service.get_knowledge_list(firebase_uid)
    return {"status": "success", "knowledge": knowledge_list}


@router.get("/knowledge/{knowledge_id}")
async def get_knowledge_details(
    knowledge_id: str,
    user: dict = Depends(get_current_user)
):
    """Get details for a specific knowledge entry."""
    firebase_uid = user['uid']
    knowledge = knowledge_service.get_knowledge_details(firebase_uid, knowledge_id)
    return {"status": "success", "knowledge": knowledge}


@router.get("/knowledge/{knowledge_id}/documents")
async def get_knowledge_documents(
    knowledge_id: str,
    user: dict = Depends(get_current_user)
):
    """Get all documents for a specific knowledge entry."""
    firebase_uid = user['uid']
    documents = knowledge_service.get_knowledge_documents(firebase_uid, knowledge_id)
    return {"status": "success", "documents": documents}

