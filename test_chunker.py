import os
from core.chunker import chunk_file

def test_chunker():
    print("--- Testing Chunker ---")
    files_to_test = [
        "main.py", # Should be < 50 lines -> 1 chunk
        "core/repo_scanner.py", # > 50 lines, has class
        "api/upload.py", # > 50 lines, has functions/routes
    ]
    
    for file_path in files_to_test:
        if not os.path.exists(file_path):
            print(f"Skipping {file_path}, not found.")
            continue
            
        print(f"\nChunking: {file_path}")
        chunks = chunk_file(file_path)
        
        print(f"Found {len(chunks)} chunks.")
        for idx, chunk in enumerate(chunks):
            print(f"  Chunk {idx+1}: {chunk.metadata.chunk_type} '{chunk.metadata.function_name}' Lines: {chunk.metadata.line_start}-{chunk.metadata.line_end}")
            
            # Print first 2 lines of the content to verify header
            lines = chunk.content.split('\n')
            if len(lines) > 0:
                print(f"    Header: {lines[0]}")
                print(f"    Code preview: {lines[2].strip() if len(lines) > 2 else ''}")

if __name__ == "__main__":
    test_chunker()
