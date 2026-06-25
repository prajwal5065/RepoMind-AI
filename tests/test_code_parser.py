import os
from core.code_parser import parse_python_file

def test_parser():
    # Test on 3 different real files in the repository
    files_to_test = [
        "main.py", 
        "core/repo_scanner.py", 
        "api/scanner.py"
    ]
    
    for file_path in files_to_test:
        print(f"\n--- Testing Parser on: {file_path} ---")
        if not os.path.exists(file_path):
            print(f"File {file_path} not found. Skipping.")
            continue
            
        parsed = parse_python_file(file_path)
        
        if parsed:
            print(f"File: {parsed.file_path}")
            print(f"Functions ({len(parsed.functions)}): {[f.name for f in parsed.functions]}")
            print(f"Classes ({len(parsed.classes)}): {[c.name for c in parsed.classes]}")
            print(f"Imports ({len(parsed.imports)}): {[i.module for i in parsed.imports]}")
            print(f"Routes ({len(parsed.routes)}): {[r.decorator + ' -> ' + r.function_name for r in parsed.routes]}")
        else:
            print(f"Parsing failed for {file_path}")
            
    # Test graceful syntax error handling
    print("\n--- Testing Parser on Bad File ---")
    bad_file = "bad_syntax.py"
    with open(bad_file, "w") as f:
        f.write("def bad_func(:\n    print('broken')\n")
    
    parsed_bad = parse_python_file(bad_file)
    if parsed_bad is None:
        print("Syntax error handled gracefully (returned None as expected).")
    
    if os.path.exists(bad_file):
        os.remove(bad_file)
        
if __name__ == "__main__":
    test_parser()
