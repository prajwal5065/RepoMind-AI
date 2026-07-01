import asyncio
import hashlib
import json
from typing import List, AsyncGenerator, Optional
from google import genai
from google.genai import types
import openai as openai_lib
from models.response_models import CodeChunk, RepoMap, Finding, FindingSeverity
from config import settings
from utils.logger import get_logger
from utils.cache import cache

logger = get_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────
GROQ_MODEL   = "llama3-70b-8192"
GEMINI_MODEL = "gemini-2.5-flash"


# ─────────────────────────────────────────────────────────────────────────────
# Helper — detect quota / rate-limit errors across both APIs
# ─────────────────────────────────────────────────────────────────────────────
def _is_retriable_error(e: Exception) -> bool:
    """Returns True for errors where we should try the next provider."""
    msg = str(e).lower()
    # Rate limit / quota (429)
    if any(k in msg for k in ("429", "quota", "exhausted", "rate_limit", "rate limit", "too many requests")):
        return True
    # Permission denied / no credits / billing (403)
    if any(k in msg for k in ("403", "permission", "permission-denied", "credits", "billing", "license", "unauthorized", "401")):
        return True
    # Connection / timeout errors
    if any(k in msg for k in ("connection", "timeout", "unreachable", "service unavailable", "503", "502")):
        return True
    return False


def _is_quota_error(e: Exception) -> bool:
    """Kept for backwards compat — delegates to _is_retriable_error."""
    return _is_retriable_error(e)


def _error_label(e: Exception) -> str:
    """Human-readable label for what went wrong."""
    msg = str(e).lower()
    if any(k in msg for k in ("403", "permission", "credits", "billing", "license")):
        return "no credits / permission denied"
    if any(k in msg for k in ("429", "quota", "exhausted", "rate limit")):
        return "quota exceeded"
    if any(k in msg for k in ("401", "unauthorized")):
        return "invalid API key"
    return "API error"


# ─────────────────────────────────────────────────────────────────────────────
# GroqClient  (Groq — OpenAI-compatible)
# ─────────────────────────────────────────────────────────────────────────────
class GroqClient:
    def __init__(self):
        if not settings.GROQ_API_KEY or settings.GROQ_API_KEY.startswith("xai-") or settings.GROQ_API_KEY.startswith("gsk_your"):
            raise ValueError("GROQ_API_KEY is not configured.")
        self.client = openai_lib.AsyncOpenAI(
            api_key=settings.GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1",
        )
        self.model = GROQ_MODEL

    async def stream(self, system: str, user: str, max_tokens: int = 1500):
        """Yields text chunks from a streaming Groq response."""
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
            max_tokens=max_tokens,
            stream=True,
            temperature=0.2,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta

    async def complete(self, system: str, user: str, max_tokens: int = 1500,
                       response_format: Optional[dict] = None) -> str:
        """Returns the full text of a non-streaming Groq response."""
        kwargs = dict(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
            max_tokens=max_tokens,
            temperature=0.2,
        )
        if response_format:
            kwargs["response_format"] = response_format
        resp = await self.client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""


# ─────────────────────────────────────────────────────────────────────────────
# GeminiClient  (Google Gemini)
# ─────────────────────────────────────────────────────────────────────────────
class GeminiClient:
    def __init__(self):
        if not settings.GEMINI_API_KEY or settings.GEMINI_API_KEY == "your_gemini_api_key_here":
            raise ValueError("GEMINI_API_KEY is not configured. Add it to your .env file.")
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model = GEMINI_MODEL

    async def stream(self, system: str, user: str, max_tokens: int = 1500):
        """Yields text chunks from a streaming Gemini response."""
        response_stream = await self.client.aio.models.generate_content_stream(
            model=self.model,
            contents=user,
            config=types.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=max_tokens,
                temperature=0.2,
            ),
        )
        async for chunk in response_stream:
            if chunk.text:
                yield chunk.text

    async def complete(self, system: str, user: str, max_tokens: int = 1500,
                       response_format: Optional[dict] = None) -> str:
        """Returns the full text of a non-streaming Gemini response."""
        config_kwargs: dict = dict(max_output_tokens=max_tokens)
        if response_format and response_format.get("type") == "json_object":
            config_kwargs["response_mime_type"] = "application/json"
        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=user,
            config=types.GenerateContentConfig(
                system_instruction=system,
                **config_kwargs,
            ),
        )
        return response.text or ""


# ─────────────────────────────────────────────────────────────────────────────
# LLMClient  (Router with automatic fallback)
# ─────────────────────────────────────────────────────────────────────────────
QUOTA_MSG = (
    "\n\n*Error: API quota limit has been exceeded. "
    "Please check your API plan or wait for the quota to reset.*"
)
UNAVAILABLE_MSG = "\n\n*Error: Could not reach the LLM API after multiple attempts. Please try again later.*"


class LLMClient:
    """
    Routes requests to either Groq or Gemini based on `provider`.
    Automatically falls back to the other provider on quota/rate-limit errors.
    """

    def __init__(self, provider: str | None = None):
        self.requested_provider = provider or settings.DEFAULT_LLM_PROVIDER

        # Try to initialise both clients — log warnings if keys are missing
        self._groq: Optional[GroqClient] = None
        self._gemini: Optional[GeminiClient] = None

        try:
            self._groq = GroqClient()
        except ValueError as e:
            logger.warning(f"Groq client unavailable: {e}")

        try:
            self._gemini = GeminiClient()
        except ValueError as e:
            logger.warning(f"Gemini client unavailable: {e}")

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _primary_and_fallback(self):
        """Returns (primary, fallback) client tuple based on requested provider."""
        if self.requested_provider == "grok" or self.requested_provider == "groq":
            return self._groq, self._gemini
        return self._gemini, self._groq

    def _get_client(self):
        """Returns the client for the currently requested provider."""
        if self.requested_provider == "grok" or self.requested_provider == "groq":
            return self._groq, "groq"
        return self._gemini, "gemini"

    def _is_report_query(self, question: str) -> bool:
        REPORT_KEYWORDS = ["report", "full report", "repo report",
                           "summarize repo", "project report", "generate report"]
        return any(kw in question.lower() for kw in REPORT_KEYWORDS)

    def _build_system_prompt(self, repo_map: RepoMap, is_report: bool = False,
                              session_id: str = None) -> str:
        languages  = ", ".join(repo_map.detected_languages) if repo_map.detected_languages else "Unknown"
        frameworks = ", ".join(repo_map.detected_frameworks) if repo_map.detected_frameworks else "Unknown"
        entry_pts  = (", ".join(repo_map.entry_points)
                      if hasattr(repo_map, "entry_points") and repo_map.entry_points else "None detected")
        modules    = ", ".join(repo_map.modules[:20]) if repo_map.modules else "None"

        arch_summary = ""
        if session_id:
            arch = cache.get(f"{session_id}:arch_summary")
            if arch:
                arch_summary = f"\nArchitecture Summary:\n{arch}\n"

        priority  = [f for f in repo_map.files if any(s in f for s in ["main.py", "api/", "core/", "rag/", "analysis/"])]
        key_files = ", ".join(priority[:30]) if priority else ", ".join(repo_map.files[:30])
        tree_str  = self._build_repo_tree(repo_map.files)

        if is_report:
            return (
                f"You are RepoMind AI generating a COMPLETE repository report.\n"
                f"Structure your report with these sections:\n"
                f"1. Project Overview 2. Architecture 3. Key Modules\n"
                f"4. Data Flow 5. Entry Points 6. Tech Stack 7. Recommendations\n"
                f"Be thorough. Do not stop early. Write all sections.\n\n"
                f"Languages: {languages}\nFrameworks: {frameworks}\n"
                f"Entry Points: {entry_pts}\nModules: {modules}\nKey Files: {key_files}{arch_summary}\n\n"
                f"Project Tree:\n{tree_str}\n\n"
                f"Use ONLY provided context and Project Tree to generate the report.\n"
                f"CRITICAL: Cite file paths as [file_path]."
            )

        return (
            f"You are RepoMind AI, an expert software engineer and repository assistant.\n"
            f"Languages: {languages}\nFrameworks: {frameworks}\n"
            f"Entry Points: {entry_pts}\nModules: {modules}\nKey Files: {key_files}{arch_summary}\n\n"
            f"Project Tree:\n{tree_str}\n\n"
            f"Use ONLY the provided context to answer. "
            f"If the answer isn't in the context, say so.\n"
            f"CRITICAL: Cite file paths as [file_path]."
        )

    def _build_context_string(self, context_chunks: List[CodeChunk]) -> str:
        safe = context_chunks[:7]
        return "\n\n".join(
            f"--- Chunk from {c.metadata.file_path} ({c.metadata.chunk_type}) ---\n{c.content}"
            for c in safe
        )

    def _build_repo_tree(self, files: List[str]) -> str:
        tree: dict = {}
        for f in files:
            parts = f.replace("\\", "/").split("/")
            cur = tree
            for p in parts:
                if p:
                    cur = cur.setdefault(p, {})

        def render(d, indent=""):
            lines = []
            keys = sorted(d.keys())
            for i, k in enumerate(keys):
                is_last = i == len(keys) - 1
                lines.append(indent + ("└── " if is_last else "├── ") + k)
                lines.extend(render(d[k], indent + ("    " if is_last else "│   ")))
            return lines

        return "\n".join(render(tree))

    # ── Streaming answer (chat) ──────────────────────────────────────────────

    async def answer_stream(
        self,
        question: str,
        context_chunks: List[CodeChunk],
        repo_map: RepoMap,
        session_id: str = None,
    ) -> AsyncGenerator[str, None]:
        is_report   = self._is_report_query(question)
        system      = self._build_system_prompt(repo_map, is_report=is_report, session_id=session_id)
        context_str = self._build_context_string(context_chunks)
        max_tokens  = 6000 if is_report else 1500
        user_msg    = f"Context from repository:\n{context_str}\n\nUser Question: {question}"

        primary, fallback = self._primary_and_fallback()
        clients = [(primary, self.requested_provider)]
        if fallback:
            fb_name = "gemini" if self.requested_provider in ("grok", "groq") else "groq"
            clients.append((fallback, fb_name))

        for idx, (client, prov) in enumerate(clients):
            if not client:
                continue
            try:
                logger.info(f"[answer_stream] Using provider: {prov}")
                async for token in client.stream(system, user_msg, max_tokens):
                    yield token

                # Citations footer
                safe = context_chunks[:7]
                if safe:
                    yield "\n\n**Sources Cited:**\n"
                    seen = set()
                    for c in safe:
                        key = f"- `{c.metadata.file_path}` ({c.metadata.chunk_type})"
                        if key not in seen:
                            yield f"{key}\n"
                            seen.add(key)
                return  # success

            except Exception as e:
                label = _error_label(e)
                logger.warning(f"[answer_stream] {prov} failed ({label}): {e}")
                has_next = any(c is not None for c, _ in clients[idx + 1:])
                if has_next:
                    yield f"\n\n*⚠ {prov.upper()} unavailable ({label}) — automatically switching to fallback provider…*\n\n"
                    continue
                # No providers left
                if _is_retriable_error(e):
                    yield f"\n\n*Error: {prov.upper()} API quota/credits limit exceeded. Please check your plan or switch providers.*"
                else:
                    yield UNAVAILABLE_MSG
                return

        # If we exit the loop and client was None, it means it wasn't configured
        yield "\n\n*Error: The selected LLM provider is not configured properly. Please check your API keys in the .env file.*"

    # ── Overview stream ──────────────────────────────────────────────────────

    async def answer_overview_stream(
        self,
        question: str,
        repo_map: RepoMap,
        readme_chunk: CodeChunk = None,
    ) -> AsyncGenerator[str, None]:
        tree      = self._build_repo_tree(repo_map.files)
        entry_pts = (", ".join(repo_map.entry_points)
                     if hasattr(repo_map, "entry_points") and repo_map.entry_points else "None")
        modules   = ", ".join(repo_map.modules[:20]) if repo_map.modules else "None"
        readme    = readme_chunk.content if readme_chunk else "Not available"

        system  = "You are RepoMind AI. Answer overview/architecture questions comprehensively."
        user    = (f"Entry Points: {entry_pts}\nModules: {modules}\n"
                   f"File Tree:\n{tree}\nREADME:\n{readme}\n\nQ: {question}")

        primary, fallback = self._primary_and_fallback()
        clients = [(primary, self.requested_provider)]
        if fallback:
            fb_name = "gemini" if self.requested_provider in ("grok", "groq") else "groq"
            clients.append((fallback, fb_name))

        for idx, (client, prov) in enumerate(clients):
            if not client:
                continue
            try:
                logger.info(f"[answer_overview_stream] Using provider: {prov}")
                async for token in client.stream(system, user, 2000):
                    yield token
                return
            except Exception as e:
                label = _error_label(e)
                logger.warning(f"[answer_overview_stream] {prov} failed ({label}): {e}")
                has_next = any(c is not None for c, _ in clients[idx + 1:])
                if has_next:
                    yield f"\n\n*⚠ {prov.upper()} unavailable ({label}) — automatically switching to fallback provider…*\n\n"
                    continue
                if _is_retriable_error(e):
                    yield f"\n\n*Error: {prov.upper()} API quota limit exceeded. Please switch providers.*"
                else:
                    yield UNAVAILABLE_MSG
                return

        # If we exit the loop and client was None, it means it wasn't configured
        yield "\n\n*Error: The selected LLM provider is not configured properly. Please check your API keys in the .env file.*"

    # ── Architecture summary (non-streaming) ─────────────────────────────────

    async def build_architecture_summary(self, repo_map: RepoMap) -> str:
        tree = self._build_repo_tree(repo_map.files)
        deps = json.dumps(repo_map.dependencies, indent=2)[:3000]
        system = "You are a software architect. Analyse repository structure and dependencies."
        user   = (f"Describe: (1) overall purpose (2) main modules and their roles "
                  f"(3) data flow (4) key relationships.\nTree:\n{tree}\nDependencies:\n{deps}")

        primary, fallback = self._primary_and_fallback()
        clients = [(primary, self.requested_provider)]
        if fallback:
            fb_name = "gemini" if self.requested_provider in ("grok", "groq") else "groq"
            clients.append((fallback, fb_name))

        for idx, (client, prov) in enumerate(clients):
            if not client:
                continue
            try:
                return await client.complete(system, user, 2000)
            except Exception as e:
                label = _error_label(e)
                logger.warning(f"[build_arch] {prov} failed ({label}): {e}")
                has_next = any(c is not None for c, _ in clients[idx + 1:])
                if has_next:
                    continue
                return "Architecture summary unavailable."

        return "Architecture summary unavailable — API error."
    # ── Explain findings (analysis tab) ─────────────────────────────────────

    async def explain_findings(self, findings: List[Finding], repo_map: RepoMap) -> List[Finding]:
        sem = asyncio.Semaphore(5)

        async def explain_one(finding: Finding):
            async with sem:
                hash_key = (
                    f"explanation:{hashlib.md5(f'{finding.tool}:{finding.file}:{finding.line}:{finding.message}'.encode()).hexdigest()}"
                )
                cached = cache.get(hash_key)
                if cached:
                    finding.explanation  = cached.get("explanation")
                    finding.fix_suggestion = cached.get("fix_suggestion")
                    return

                primary, fallback = self._primary_and_fallback()
                clients = [(primary, self.requested_provider)]
                if fallback:
                    fb_name = "gemini" if self.requested_provider in ("grok", "groq") else "groq"
                    clients.append((fallback, fb_name))

                if finding.severity == FindingSeverity.HIGH:
                    system = "You are a security and static analysis expert."
                    user   = (
                        f"Explain the following HIGH severity finding in plain English, "
                        f"show what bad input could exploit it, and suggest a specific fix with a code example.\n"
                        f"File: {finding.file} (Line {finding.line})\nTool: {finding.tool}\nMessage: {finding.message}\n\n"
                        f"Return VALID JSON ONLY:\n"
                        f'{{ "explanation": "...", "fix_suggestion": "..." }}'
                    )
                    for idx, (client, prov) in enumerate(clients):
                        if not client:
                            continue
                        try:
                            raw = await asyncio.wait_for(
                                client.complete(system, user, 600,
                                                response_format={"type": "json_object"}),
                                timeout=20.0,
                            )
                            result = json.loads(raw)
                            finding.explanation   = result.get("explanation")
                            finding.fix_suggestion = result.get("fix_suggestion")
                            cache.set(hash_key, {"explanation": finding.explanation,
                                                  "fix_suggestion": finding.fix_suggestion})
                            return
                        except Exception as e:
                            label = _error_label(e)
                            logger.warning(f"[explain_findings HIGH] {prov} failed ({label}): {e}")
                            has_next = any(c is not None for c, _ in clients[idx + 1:])
                            if has_next:
                                continue
                            if _is_retriable_error(e):
                                finding.explanation = "API unavailable (quota/credits exceeded)."
                            else:
                                finding.explanation = "Explanation unavailable due to API error."
                            return

                elif finding.severity in (FindingSeverity.MEDIUM, FindingSeverity.LOW):
                    system = "You are a security and static analysis expert."
                    user   = (
                        f"Explain this finding in exactly 1 brief sentence (no code example).\n"
                        f"File: {finding.file} (Line {finding.line})\nTool: {finding.tool}\nMessage: {finding.message}"
                    )
                    for idx, (client, prov) in enumerate(clients):
                        if not client:
                            continue
                        try:
                            raw = await asyncio.wait_for(
                                client.complete(system, user, 200), timeout=15.0
                            )
                            finding.explanation = raw.strip()
                            cache.set(hash_key, {"explanation": finding.explanation})
                            return
                        except Exception as e:
                            label = _error_label(e)
                            logger.warning(f"[explain_findings MED/LOW] {prov} failed ({label}): {e}")
                            has_next = any(c is not None for c, _ in clients[idx + 1:])
                            if has_next:
                                continue
                            if _is_retriable_error(e):
                                finding.explanation = "API unavailable (quota/credits exceeded)."
                            else:
                                finding.explanation = "Explanation unavailable."
                            return

        await asyncio.gather(*(explain_one(f) for f in findings))
        return findings
