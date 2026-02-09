from pydantic import BaseModel
from typing import Optional


class DocumentUploadResponse(BaseModel):
    status: str
    storage_path: str


class DocumentDeleteResponse(BaseModel):
    status: str
