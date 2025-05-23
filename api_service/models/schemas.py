from typing import List, Optional
from pydantic import BaseModel, Field

class Query(BaseModel):
    query: str
    max_results: int = 5
    use_memory: bool = True

class ChunkResponse(BaseModel):
    id: int
    text: str
    source: str
    similarity: float

class EntityResponse(BaseModel):
    entity: str
    entity_type: str
    relevance: float

class CommunityResponse(BaseModel):
    community_id: int
    summary: str
    entities: List[str]
    relevance: float

class FullResponse(BaseModel):
    query: str
    answer: str
    chunks: List[ChunkResponse]
    entities: List[EntityResponse]
    communities: List[CommunityResponse]
    references: List[str]
    from_memory: bool = False
    memory_id: Optional[int] = None

class FeedbackRequest(BaseModel):
    memory_id: int
    feedback_text: Optional[str] = None
    rating: Optional[int] = Field(None, ge=1, le=5)
    is_favorite: Optional[bool] = None

class ThreadCreateRequest(BaseModel):
    memory_id: int
    thread_title: str

class ThreadMessageRequest(BaseModel):
    feedback_id: int
    message: str
    enhance_with_retrieval: bool = False
    max_results: int = 3

class ThreadMessageResponse(BaseModel):
    id: int
    message: str
    is_user: bool
    references: List[str]
    chunks: Optional[List[ChunkResponse]] = None
    created_at: str

class ThreadResponse(BaseModel):
    id: int
    title: str
    memory_id: int
    original_query: str
    original_answer: str
    messages: List[ThreadMessageResponse]
    created_at: str