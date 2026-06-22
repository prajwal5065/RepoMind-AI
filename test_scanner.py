import os
import shutil
from core.repo_scanner import RepoScanner
from config import settings

def setup_test_repo(session_id: str):
    base_dir = os.path.join(settings.UPLOAD_DIR, session_id, "extracted")
    os.makedirs(base_dir, exist_ok=True)
    
    # Create some mock files
    files = {
        "main.py": "print('hello')",
        "utils/helpers.js": "console.log('test')",
        "requirements.txt": "fastapi\nrequests\n",
        "package.json": '{"dependencies": {"react": "^18.0"}}'
    }
    
    for filepath, content in files.items():
        full_path = os.path.join(base_dir, filepath)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)

    return base_dir

def teardown_test_repo(session_id: str):
    dir_path = os.path.join(settings.UPLOAD_DIR, session_id)
    if os.path.exists(dir_path):
        shutil.rmtree(dir_path)

def test_repo_scanner():
    session_id = "test_scanner_session"
    base_dir = setup_test_repo(session_id)
    
    try:
        scanner = RepoScanner(base_dir)
        repo_map = scanner.scan()
        
        print(f"RepoMap Root: {repo_map.root}")
        print(f"Modules: {repo_map.modules}")
        print(f"Files: {repo_map.files}")
        print(f"Languages: {repo_map.detected_languages}")
        print(f"Frameworks: {repo_map.detected_frameworks}")
        
        assert "Python" in repo_map.detected_languages
        assert "JavaScript" in repo_map.detected_languages
        assert "FastAPI" in repo_map.detected_frameworks
        assert "React" in repo_map.detected_frameworks
        assert "main.py" in repo_map.files
        print("\nAll scanner tests passed successfully!")
    finally:
        teardown_test_repo(session_id)

if __name__ == "__main__":
    test_repo_scanner()
