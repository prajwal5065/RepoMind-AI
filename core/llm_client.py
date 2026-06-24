import asyncio
import hashlib
import json
from typing import List, AsyncGenerator
from google import genai
from google.genai import types
from models.response_models import CodeChunk, RepoMap, Finding, FindingSeverity
from config import settings
from utils.logger import get_logger
from utils.cache import cache

logger = get_logger(__name__)

class LLMClient:
    def __init__(self):
        if not settings.GEMINI_API_KEY or settings.GEMINI_API_KEY == "your_gemini_api_key_here":
            logger.warning("GEMINI_API_KEY is not set or is using the default placeholder.")
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        # Using gemini-2.5-flash as the fast/cheap model
        self.model = 'gemini-2.5-flash'

    def _is_report_query(self, question: str) -> bool:
        REPORT_KEYWORDS = ['report', 'full report', 'repo report', 'summarize repo', 'project report', 'generate report']
        return any(kw in question.lower() for kw in REPORT_KEYWORDS)

    def _build_system_prompt(self, repo_map: RepoMap, is_report: bool = False, session_id: str = None) -> str:
        languages = ", ".join(repo_map.detected_languages) if repo_map.detected_languages else "Unknown"
        frameworks = ", ".join(repo_map.detected_frameworks) if repo_map.detected_frameworks else "Unknown"
        entry_pts = ", ".join(repo_map.entry_points) if hasattr(repo_map, "entry_points") and repo_map.entry_points else "None detected"
        modules = ", ".join(repo_map.modules[:20]) if repo_map.modules else "None"
        
        arch_summary = ""
        if session_id:
            from utils.cache import cache
            arch = cache.get(f'{session_id}:arch_summary')
            if arch:
                arch_summary = f"\nArchitecture Summary:\n{arch}\n"
        
        # Top 30 most important files (core/, api/, main.py first)
        priority = [f for f in repo_map.files if any(s in f for s in ['main.py', 'api/', 'core/', 'rag/', 'analysis/'])]
        key_files = ", ".join(priority[:30]) if priority else ", ".join(repo_map.files[:30])
        tree_str = self._build_repo_tree(repo_map.files)
        
        if is_report:
            return f"""You are RepoMind AI generating a COMPLETE repository report.
Structure your report with these sections:
1. Project Overview 2. Architecture 3. Key Modules
4. Data Flow 5. Entry Points 6. Tech Stack 7. Recommendations
Be thorough. Do not stop early. Write all sections.

Languages detected: {languages}
Frameworks detected: {frameworks}
Entry Points: {entry_pts}
Modules: {modules}
Key Files: {key_files}{arch_summary}

Project Tree:
{tree_str}

You will be provided with context chunks from the repository. Use ONLY this context and the Project Tree to generate the report.
CRITICAL INSTRUCTION: You MUST cite the file paths of any code you reference. Format citations as [file_path]."""
        
        if is_overview:
            file_count = len(repo_map.files)
            
            return f"""You are RepoMind AI, an expert software engineer and repository assistant.
The user is asking for a project overview or repository summary.
Languages detected: {languages}
Frameworks detected: {frameworks}
Entry Points: {entry_pts}
Modules: {modules}
Key Files: {key_files}{arch_summary}
Total Files: {file_count}

Project Tree:
{tree_str}

You will be provided with context chunks from the repository, including README and major files.
Use this context and the Project Tree to provide a comprehensive project overview.
You MUST cover:
1. The purpose of the project.
2. Architecture and System Design.
3. Major modules and entry points.
4. Technologies used.
5. Overall workflow.
CRITICAL INSTRUCTION: You MUST cite the file paths of any code you reference. Format citations as [file_path].
Keep your answer accurate and focused on the provided codebase."""
        
        return f"""You are RepoMind AI, an expert software engineer and repository assistant.
The user is asking questions about a codebase.
Languages detected: {languages}
Frameworks detected: {frameworks}
Entry Points: {entry_pts}
Modules: {modules}
Key Files: {key_files}{arch_summary}

Project Tree:
{tree_str}

You will be provided with context chunks from the repository. Use ONLY this context and the Project Tree to answer the question.
If the answer is not in the context, say "I don't have enough information from the repository to answer that."
CRITICAL INSTRUCTION: You MUST cite the file paths of any code you reference. Format citations as [file_path].
Example: "The authentication logic is handled in [auth/routes.py]."
Keep your answers accurate, concise, and focused on the code."""

    def _build_context_string(self, context_chunks: List[CodeChunk]) -> str:
        # Never send more than 7 chunks to the LLM
        safe_chunks = context_chunks[:7]
        context_parts = []
        for chunk in safe_chunks:
            context_parts.append(f"--- Chunk from {chunk.metadata.file_path} ({chunk.metadata.chunk_type}) ---\n{chunk.content}")
        return "\n\n".join(context_parts)

    async def answer(self, question: str, context_chunks: List[CodeChunk], repo_map: RepoMap, session_id: str = None) -> str:
        """Returns the full string answer synchronously/awaited."""
        is_report = self._is_report_query(question)
        system_prompt = self._build_system_prompt(repo_map, is_report=is_report, session_id=session_id)
        context_str = self._build_context_string(context_chunks)
        max_tokens = 6000 if is_report else 1500
        
        user_message = f"Context from repository:\n{context_str}\n\nUser Question: {question}"
        
        for attempt in range(3):
            try:
                # In the new genai SDK, async methods are on client.aio
                response = await self.client.aio.models.generate_content(
                    model=self.model,
                    contents=user_message,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        max_output_tokens=max_tokens,
                        temperature=0.2,
                    )
                )
                return response.text
            except Exception as e:
                logger.warning(f"LLM API error (attempt {attempt + 1}/3): {e}")
                if attempt == 2:
                    logger.error("Max retries reached for LLM API.")
                    return "Error: Could not reach the LLM API after 3 attempts."
                await asyncio.sleep(2 ** attempt)

    async def answer_stream(self, question: str, context_chunks: List[CodeChunk], repo_map: RepoMap, session_id: str = None) -> AsyncGenerator[str, None]:
        """Yields the string chunks for streaming, followed by a citations footer."""
        is_report = self._is_report_query(question)
        system_prompt = self._build_system_prompt(repo_map, is_report=is_report, session_id=session_id)
        context_str = self._build_context_string(context_chunks)
        max_tokens = 6000 if is_report else 1500
        
        user_message = f"Context from repository:\n{context_str}\n\nUser Question: {question}"
        
        for attempt in range(3):
            try:
                response_stream = await self.client.aio.models.generate_content_stream(
                    model=self.model,
                    contents=user_message,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        max_output_tokens=max_tokens,
                        temperature=0.2,
                    )
                )
                
                async for chunk in response_stream:
                    if chunk.text:
                        yield chunk.text
                        
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

    def _build_repo_tree(self, files: List[str]) -> str:
        tree = {}
        for f in files:
            # handle both windows and unix slashes just in case
            parts = f.replace('\\', '/').split('/')
            current = tree
            for part in parts:
                if part:
                    current = current.setdefault(part, {})
                
        def render_tree(d, indent=""):
            lines = []
            keys = sorted(list(d.keys()))
            for i, k in enumerate(keys):
                is_last = (i == len(keys) - 1)
                prefix = "└── " if is_last else "├── "
                lines.append(indent + prefix + k)
                child_indent = indent + ("    " if is_last else "│   ")
                lines.extend(render_tree(d[k], child_indent))
            return lines
        
        return "\n".join(render_tree(tree))

    async def build_architecture_summary(self, repo_map: RepoMap) -> str:
        import json
        tree = self._build_repo_tree(repo_map.files)
        deps = json.dumps(repo_map.dependencies, indent=2)[:3000]
        prompt = f'''Analyse this repository structure and dependencies.
Describe: (1) overall purpose (2) main modules and their roles
(3) data flow (4) key relationships between modules.
Tree:\n{tree}\nDependencies:\n{deps}'''
        
        response = await self.client.aio.models.generate_content(
            model=self.model, contents=prompt,
            config=types.GenerateContentConfig(max_output_tokens=2000)
        )
        return response.text

    async def answer_overview_stream(self, question: str, repo_map: RepoMap, readme_chunk: CodeChunk = None) -> AsyncGenerator[str, None]:
        tree = self._build_repo_tree(repo_map.files)
        entry_pts = ', '.join(repo_map.entry_points) if hasattr(repo_map, "entry_points") and repo_map.entry_points else 'None'
        modules = ', '.join(repo_map.modules[:20]) if repo_map.modules else 'None'
        readme = readme_chunk.content if readme_chunk else 'Not available'
        
        system = 'You are RepoMind AI. Answer overview/architecture questions.'
        user = f'Entry Points: {entry_pts}\nModules: {modules}\n'
        user += f'File Tree:\n{tree}\nREADME:\n{readme}\n\nQ: {question}'
        
        for attempt in range(3):
            try:
                response_stream = await self.client.aio.models.generate_content_stream(
                    model=self.model,
                    contents=user,
                    config=types.GenerateContentConfig(
                        system_instruction=system,
                        max_output_tokens=2000,
                        temperature=0.2,
                    )
                )
                async for chunk in response_stream:
                    if chunk.text:
                        yield chunk.text
                return
            except Exception as e:
                logger.warning(f"LLM API overview streaming error (attempt {attempt + 1}/3): {e}")
                if attempt == 2:
                    logger.error("Max retries reached for LLM API.")
                    yield "Error: Could not reach the LLM API after 3 attempts."
                await asyncio.sleep(2 ** attempt)

    async def explain_findings(self, findings: List[Finding], repo_map: RepoMap) -> List[Finding]:
        sem = asyncio.Semaphore(10)
        
        async def explain_one(finding: Finding):
            async with sem:
                hash_key = f"explanation:{hashlib.md5(f'{finding.tool}:{finding.file}:{finding.line}:{finding.message}'.encode()).hexdigest()}"
                cached_explanation = cache.get(hash_key)
                if cached_explanation:
                    finding.explanation = cached_explanation.get("explanation")
                    finding.fix_suggestion = cached_explanation.get("fix_suggestion")
                    return

                if finding.severity == FindingSeverity.HIGH:
                    prompt = f"""You are a security and static analysis expert.
Explain the following high severity finding in plain English, show what bad input could exploit it, and suggest a specific fix with a code example.
File: {finding.file} (Line {finding.line})
Tool: {finding.tool}
Message: {finding.message}

Return the response in valid JSON format EXACTLY like this:
{{
    "explanation": "Brief explanation and exploit scenario",
    "fix_suggestion": "Code example of the fix"
}}"""
                    try:
                        response = await asyncio.wait_for(
                            self.client.aio.models.generate_content(
                                model=self.model,
                                contents=prompt,
                                config=types.GenerateContentConfig(
                                    response_mime_type="application/json",
                                )
                            ),
                            timeout=15.0
                        )
                        result = json.loads(response.text)
                        finding.explanation = result.get("explanation")
                        finding.fix_suggestion = result.get("fix_suggestion")
                        cache.set(hash_key, {"explanation": finding.explanation, "fix_suggestion": finding.fix_suggestion})
                    except Exception as e:
                        logger.error(f"Error explaining HIGH finding: {e}")
                        finding.explanation = "Explanation unavailable due to API timeout or error."

                elif finding.severity in [FindingSeverity.MEDIUM, FindingSeverity.LOW]:
                    prompt = f"""You are a security and static analysis expert.
Explain this finding in exactly 1 brief sentence (no code example).
File: {finding.file} (Line {finding.line})
Tool: {finding.tool}
Message: {finding.message}"""
                    try:
                        response = await asyncio.wait_for(
                            self.client.aio.models.generate_content(
                                model=self.model,
                                contents=prompt
                            ),
                            timeout=15.0
                        )
                        finding.explanation = response.text.strip()
                        cache.set(hash_key, {"explanation": finding.explanation})
                    except Exception as e:
                        logger.error(f"Error explaining MEDIUM/LOW finding: {e}")
                        finding.explanation = "Explanation unavailable."
                        
        await asyncio.gather(*(explain_one(f) for f in findings))
        return findings
