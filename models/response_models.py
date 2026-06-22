from pydantic import BaseModel
from typing import List, Optional

class ChunkMetadata(BaseModel):
    file_path: str
    chunk_type: str
    function_name: Optional[str] = None
    line_start: int
    line_end: int

class ChatResponse(BaseModel):
    answer: str
    sources: List[ChunkMetadata]

class AnalysisResponse(BaseModel):
    findings: str
