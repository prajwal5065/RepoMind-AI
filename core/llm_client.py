import asyncio
from typing import List, AsyncGenerator
from openai import AsyncOpenAI
from models.response_models import CodeChunk, RepoMap
from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)

class LLMClient:
    def __init__(self):
        if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY == "your-openai-api-key-here":
            logger.warning("OPENAI_API_KEY is not set or is using the default placeholder.")
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = "gpt-4o-mini" # Using mini for speed and cost, suitable for code Q&A

    def _build_system_prompt(self, repo_map: RepoMap) -> str:
        languages = ", ".join(repo_map.detected_languages) if repo_map.detected_languages else "Unknown"
        frameworks = ", ".join(repo_map.detected_frameworks) if repo_map.detected_frameworks else "Unknown"
        
        return f"""You are RepoMind AI, an expert software engineer and repository assistant.
The user is asking questions about a codebase.
Languages detected: {languages}
Frameworks detected: {frameworks}

You will be provided with context chunks from the repository. Use ONLY this context to answer the question.
If the answer is not in the context, say "I don't have enough information from the repository to answer that."
CRITICAL INSTRUCTION: You MUST cite the file paths of any code you reference. Format citations as [file_path].
Example: "The authentication logic is handled in [auth/routes.py]."
Keep your answers accurate, concise, and focused on the code."""

    def _build_context_string(self, context_chunks: List[CodeChunk]) -> str:
        # Never send more than 7 chunks to the LLM
        safe_chunks = context_chunks[:7]
        context_parts = []
        for chunk in safe_chunks:
            # We already prepended header in chunker, but let's ensure file path is visible
            context_parts.append(f"--- Chunk from {chunk.metadata.file_path} ({chunk.metadata.chunk_type}) ---\n{chunk.content}")
        return "\n\n".join(context_parts)

    async def answer(self, question: str, context_chunks: List[CodeChunk], repo_map: RepoMap) -> str:
        """Returns the full string answer synchronously/awaited."""
        system_prompt = self._build_system_prompt(repo_map)
        context_str = self._build_context_string(context_chunks)
        
        user_message = f"Context from repository:\n{context_str}\n\nUser Question: {question}"
        
        for attempt in range(3):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    max_tokens=1000,
                    temperature=0.2
                )
                return response.choices[0].message.content
            except Exception as e:
                logger.warning(f"LLM API error (attempt {attempt + 1}/3): {e}")
                if attempt == 2:
                    logger.error("Max retries reached for LLM API.")
                    return "Error: Could not reach the LLM API after 3 attempts."
                await asyncio.sleep(2 ** attempt) # Exponential backoff: 1s, 2s

    async def answer_stream(self, question: str, context_chunks: List[CodeChunk], repo_map: RepoMap) -> AsyncGenerator[str, None]:
        """Yields the string chunks for streaming, followed by a citations footer."""
        system_prompt = self._build_system_prompt(repo_map)
        context_str = self._build_context_string(context_chunks)
        
        user_message = f"Context from repository:\n{context_str}\n\nUser Question: {question}"
        
        for attempt in range(3):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    max_tokens=1000,
                    temperature=0.2,
                    stream=True
                )
                
                async for chunk in response:
                    if chunk.choices and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
                        
                # Append citations at the end
                safe_chunks = context_chunks[:7]
                if safe_chunks:
                    yield "\n\n**Sources Cited:**\n"
                    seen = set()
                    for c in safe_chunks:
                        key = f"- `{c.metadata.file_path}` ({c.metadata.chunk_type})"
                        if key not in seen:
                            yield f"{key}\n"
                            seen.add(key)
                return
            except Exception as e:
                logger.warning(f"LLM API streaming error (attempt {attempt + 1}/3): {e}")
                if attempt == 2:
                    logger.error("Max retries reached for LLM streaming API.")
                    yield "\n\n*Error: Stream interrupted due to API connection issues.*"
                    return
                await asyncio.sleep(2 ** attempt)
