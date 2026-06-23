import os
from typing import List
from models.response_models import CodeChunk, ChunkMetadata
from core.code_parser import parse_python_file
from core.repo_scanner import BINARY_EXTENSIONS
from utils.logger import get_logger

logger = get_logger(__name__)

class Chunker:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.chunks: List[CodeChunk] = []

    def chunk(self) -> List[CodeChunk]:
        if not os.path.exists(self.file_path):
            return []

        # Skip binary file types entirely
        _, ext = os.path.splitext(self.file_path)
        if ext.lower() in BINARY_EXTENSIONS:
            return []

        # Safe read: try UTF-8 first, then latin-1 as a lossless fallback,
        # so we never crash on files with non-UTF-8 bytes.
        lines = None
        for encoding in ('utf-8', 'latin-1'):
            try:
                with open(self.file_path, 'r', encoding=encoding) as f:
                    lines = f.readlines()
                break
            except (UnicodeDecodeError, OSError) as e:
                logger.debug(f"Could not read {self.file_path} with {encoding}: {e}")

        if lines is None:
            logger.warning(f"Skipping unreadable file: {self.file_path}")
            return []

        total_lines = len(lines)
        
        # Rule: for small files (<50 lines) keep entire file as one chunk
        if total_lines < 50:
            content = "".join(lines)
            metadata = ChunkMetadata(
                file_path=self.file_path,
                chunk_type="module",
                function_name=None,
                line_start=1,
                line_end=total_lines
            )
            # Prepend context header
            # Example target: # File: auth/routes.py | Function: login | Lines: 45-67
            context_header = f"# File: {self.file_path} | Module: whole_file | Lines: 1-{total_lines}\n\n"
            self.chunks.append(CodeChunk(metadata=metadata, content=context_header + content))
            return self.chunks

        parsed_file = parse_python_file(self.file_path)
        if not parsed_file:
            return []

        # Rule: chunk by CLASS (class + all its methods = one chunk)
        # We track lines that are chunked so we don't extract methods as standalone chunks
        chunked_lines = set()

        for cls in parsed_file.classes:
            start = cls.line_number
            end = cls.line_end
            
            # Simple heuristic to split large classes (if they exceed 400 tokens / ~100 lines) 
            # would go here. However, strict rule says "chunk by CLASS (class + all its methods = one chunk)"
            # so we'll leave it as a single chunk unless requested otherwise.
            
            content = "".join(lines[start-1:end])
            metadata = ChunkMetadata(
                file_path=self.file_path,
                chunk_type="class",
                function_name=cls.name,
                line_start=start,
                line_end=end,
                parent_classes=cls.parent_classes
            )
            context_header = f"# File: {self.file_path} | Class: {cls.name} | Lines: {start}-{end}\n\n"
            self.chunks.append(CodeChunk(metadata=metadata, content=context_header + content))
            
            for i in range(start, end + 1):
                chunked_lines.add(i)

        # Rule: chunk by FUNCTION (one function = one chunk)
        for func in parsed_file.functions:
            if func.line_number in chunked_lines:
                continue # Skip methods inside a class that was already chunked
                
            start = func.line_number
            end = func.line_end
            content = "".join(lines[start-1:end])
            
            metadata = ChunkMetadata(
                file_path=self.file_path,
                chunk_type="function",
                function_name=func.name,
                line_start=start,
                line_end=end
            )
            context_header = f"# File: {self.file_path} | Function: {func.name} | Lines: {start}-{end}\n\n"
            self.chunks.append(CodeChunk(metadata=metadata, content=context_header + content))
            
            for i in range(start, end + 1):
                chunked_lines.add(i)

        return self.chunks

def chunk_file(file_path: str) -> List[CodeChunk]:
    chunker = Chunker(file_path)
    return chunker.chunk()
