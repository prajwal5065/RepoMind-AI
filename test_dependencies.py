import os
import shutil
from core.repo_scanner import RepoScanner
from config import settings

def teardown_test_repo(session_id: str):
    dir_path = os.path.join(settings.UPLOAD_DIR, session_id)
    if os.path.exists(dir_path):
        shutil.rmtree(dir_path)

def test_dependencies_and_parents():
    session_id = "test_deps_session"
    base_dir = os.path.join(settings.UPLOAD_DIR, session_id, "extracted")
    os.makedirs(base_dir, exist_ok=True)
    
    files = {
        "models/base.py": "class BaseModel:\n    pass\n",
        "models/user.py": "from models.base import BaseModel\nclass User(BaseModel):\n    def login(self):\n        pass\n",
        "api/auth.py": "import os\nfrom models.user import User\n\n@app.get('/login')\ndef login():\n    pass\n"
    }
    
    for filepath, content in files.items():
        full_path = os.path.join(base_dir, filepath)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)

    try:
        scanner = RepoScanner(base_dir)
        repo_map = scanner.scan()
        
        print(f"Dependencies Map: {repo_map.dependencies}")
        
        assert "api/auth.py" in repo_map.dependencies
        assert "models/user.py" in repo_map.dependencies["api/auth.py"]
        
        assert "models/user.py" in repo_map.dependencies
        assert "models/base.py" in repo_map.dependencies["models/user.py"]
        
        from core.code_parser import parse_python_file
        user_parsed = parse_python_file(os.path.join(base_dir, "models/user.py"), repo_root=base_dir)
        assert "BaseModel" in user_parsed.classes[0].parent_classes
        
        print("\nAll dependency and parent class tests passed successfully!")
    finally:
        teardown_test_repo(session_id)

if __name__ == "__main__":
    test_dependencies_and_parents()
