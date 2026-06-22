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

class RepoMap(BaseModel):
    root: str
    modules: List[str]
    files: List[str]
    detected_languages: List[str]
    detected_frameworks: List[str]

class ParsedClass(BaseModel):
    name: str
    line_number: int
    line_end: int
    methods: List[str]

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

class CodeChunk(BaseModel):
    metadata: ChunkMetadata
    content: str



