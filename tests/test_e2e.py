import os
import shutil
import requests
import time

def test_e2e():
    print("--- Testing End-to-End Parsing Workflow ---")
    
    # 1. Create a dummy zip file
    os.makedirs("test_repo/src", exist_ok=True)
    with open("test_repo/src/main.py", "w", encoding="utf-8") as f:
        f.write("def hello():\n    print('hello')\n\nclass User:\n    def get_user(self):\n        pass\n")
    with open("test_repo/requirements.txt", "w", encoding="utf-8") as f:
        f.write("fastapi\n")
        
    shutil.make_archive("test_repo", 'zip', "test_repo")
    
    session_id = "test_e2e_session"
    
    try:
        # Note: The FastAPI server must be running for this test to work.
        print("Uploading zip...")
        with open("test_repo.zip", "rb") as f:
            resp = requests.post("http://localhost:8000/api/upload", data={"session_id": session_id}, files={"file": f})
            
        print(f"Upload response: {resp.status_code} {resp.text}")
        assert resp.status_code == 200, "Upload failed"
        
        print("Parsing repo...")
        resp = requests.post(f"http://localhost:8000/api/parse/{session_id}")
        print(f"Parse response: {resp.status_code} {resp.json()}")
        assert resp.status_code == 200, "Parsing failed"
        
        summary = resp.json()
        assert summary["total_files"] == 2, f"Expected 2 files, got {summary['total_files']}"
        assert summary["total_chunks"] > 0, "Expected > 0 chunks"
        assert "FastAPI" in summary["frameworks_detected"], "FastAPI not detected"
        assert "Python" in summary["languages_detected"], "Python not detected"
        
        print("\nE2E Test passed successfully!")
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to localhost:8000. Is the server running?")
    finally:
        # Cleanup
        if os.path.exists("test_repo"):
            shutil.rmtree("test_repo")
        if os.path.exists("test_repo.zip"):
            os.remove("test_repo.zip")

if __name__ == "__main__":
    test_e2e()
