import asyncio
from core.llm_client import LLMClient
from models.response_models import RepoMap, CodeChunk, ChunkMetadata

async def test_llm_stream():
    from config import settings
    if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY == "your-openai-api-key-here":
        print("Skipping LLM test: No real OPENAI_API_KEY provided in .env.")
        return
        
    print("--- Testing LLM Streaming ---")
    
    llm = LLMClient()
    repo_map = RepoMap(
        root="/mock", 
        modules=[], 
        files=[], 
        detected_languages=["Python"], 
        detected_frameworks=["FastAPI"]
    )
    
    chunks = [
        CodeChunk(
            metadata=ChunkMetadata(file_path="auth.py", chunk_type="function", line_start=1, line_end=5),
            content="def get_secret():\n    return 'super_secret_42'"
        )
    ]
    
    print("\nQuestion: What is the secret?")
    print("Answer Stream:")
    
    stream = llm.answer_stream("What is the secret?", chunks, repo_map)
    async for chunk in stream:
        print(chunk, end="", flush=True)
        
    print("\n\nLLM Stream test passed!")

if __name__ == "__main__":
    asyncio.run(test_llm_stream())
