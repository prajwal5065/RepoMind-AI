from pydantic import BaseModel

class ChatRequest(BaseModel):
    session_id: str
    question: str

class AnalysisRequest(BaseModel):
    session_id: str
