from pydantic import BaseModel


class KnowledgeCreateResponse(BaseModel):
    status: str
    knowledge_id: str
