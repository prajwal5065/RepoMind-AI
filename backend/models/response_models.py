from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from enum import Enum

class ChunkMetadata(BaseModel):
    file_path: str
    chunk_type: str
    function_name: Optional[str] = None
    line_start: int
    line_end: int
    parent_classes: Optional[List[str]] = None

class ChatResponse(BaseModel):
    answer: str
    sources: List[ChunkMetadata]

class AnalysisResponse(BaseModel):
    findings: str

class RepoMap(BaseModel):
    root: str
    modules: List[str]
    files: List[str]
    detected_languages: List[str]
    detected_frameworks: List[str]
    dependencies: Dict[str, List[str]] = {}
    entry_points: List[str] = []

class ParseSummary(BaseModel):
    total_files: int
    total_chunks: int
    languages_detected: List[str]
    frameworks_detected: List[str]

class IndexSummary(BaseModel):
    indexed_chunks: int
    index_size_mb: float
    time_taken_seconds: float

class ParsedClass(BaseModel):
    name: str
    line_number: int
    line_end: int
    methods: List[str]
    parent_classes: List[str] = []

class ParsedFunction(BaseModel):
    name: str
    line_number: int
    line_end: int


class ParsedImport(BaseModel):
    module: str
    names: List[str]

class ParsedRoute(BaseModel):
    decorator: str
    function_name: str
    line_number: int
    line_end: int

class ParsedFile(BaseModel):
    file_path: str
    functions: List[ParsedFunction]
    classes: List[ParsedClass]
    imports: List[ParsedImport]
    routes: List[ParsedRoute]
    local_dependencies: List[str] = []

class CodeChunk(BaseModel):
    metadata: ChunkMetadata
    content: str


class FindingSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    WARNING = "WARNING"
    ERROR = "ERROR"

class Finding(BaseModel):
    tool: str
    file: str
    line: int
    severity: FindingSeverity
    message: str
    severity_score: Optional[int] = None
    explanation: Optional[str] = None
    fix_suggestion: Optional[str] = None

class ModuleDoc(BaseModel):
    module_path: str
    purpose: str
    public_functions: List[Dict[str, str]]
    dependencies: List[str]

class APIDoc(BaseModel):
    method: str
    path: str
    expected_input: str
    expected_output: str
    description: str

class ProjectDoc(BaseModel):
    tech_stack: str
    architecture_summary: str
    entry_points: List[str]
    modules: List[ModuleDoc]
    api_routes: List[APIDoc]
