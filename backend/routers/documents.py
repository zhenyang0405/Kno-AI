from fastapi import APIRouter, Depends, UploadFile, File, Form
from typing import Optional
from dependencies import get_current_user, get_storage_bucket
from services import document_service
from models.document import DocumentUploadResponse, DocumentDeleteResponse


router = APIRouter()


@router.post("/upload-document", response_model=DocumentUploadResponse)
async def upload_document(
    knowledge_id: str = Form(...),
    topic_id: str = Form(None),
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user)
):
    """Upload a document to a knowledge entry."""
    firebase_uid = user['uid']
    bucket = get_storage_bucket()

    storage_path = document_service.upload_document(
        bucket, firebase_uid, knowledge_id, file, topic_id
    )

    return {"status": "success", "storage_path": storage_path}


@router.delete("/delete-document/{knowledge_id}/{document_id}", response_model=DocumentDeleteResponse)
async def delete_document(
    knowledge_id: str,
    document_id: str,
    user: dict = Depends(get_current_user)
):
    """Delete a document from a knowledge entry."""
    firebase_uid = user['uid']
    bucket = get_storage_bucket()

    document_service.delete_document(bucket, firebase_uid, knowledge_id, document_id)

    return {"status": "success"}


@router.get("/documents/{document_id}")
async def get_document_details(
    document_id: str,
    user: dict = Depends(get_current_user)
):
    """Get document metadata."""
    firebase_uid = user['uid']
    document = document_service.get_document_details(firebase_uid, document_id)
    return {"status": "success", "document": document}


@router.get("/documents/{document_id}/download-url")
async def get_document_download_url(
    document_id: str,
    user: dict = Depends(get_current_user)
):
    """Get signed URL for downloading document from Cloud Storage."""
    firebase_uid = user['uid']
    bucket = get_storage_bucket()
    url = document_service.get_document_download_url(bucket, firebase_uid, document_id)
    return {"status": "success", "url": url}

