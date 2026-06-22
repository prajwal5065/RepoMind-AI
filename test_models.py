from models.request_models import ChatRequest, AnalysisRequest
from models.response_models import ChatResponse, AnalysisResponse, ChunkMetadata

def test_serialization():
    # Test Request Models
    chat_req = ChatRequest(session_id="123", question="How does this work?")
    print("ChatRequest serialized:", chat_req.model_dump_json())
    
    analysis_req = AnalysisRequest(session_id="456")
    print("AnalysisRequest serialized:", analysis_req.model_dump_json())
    
    # Test Response Models
    metadata = ChunkMetadata(
        file_path="main.py", 
        chunk_type="function", 
        function_name="health_check", 
        line_start=20, 
        line_end=25
    )
    
    chat_res = ChatResponse(answer="It works well.", sources=[metadata])
    print("ChatResponse serialized:", chat_res.model_dump_json())
    
    analysis_res = AnalysisResponse(findings="No issues found.")
    print("AnalysisResponse serialized:", analysis_res.model_dump_json())
    
    print("\nAll models serialized successfully!")

if __name__ == "__main__":
    test_serialization()
