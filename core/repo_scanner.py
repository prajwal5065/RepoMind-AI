import os
from typing import List, Set
from models.response_models import RepoMap
from utils.logger import get_logger

logger = get_logger(__name__)

LANGUAGE_EXTENSIONS = {
    '.py': 'Python',
    '.js': 'JavaScript',
    '.ts': 'TypeScript',
    '.java': 'Java',
    '.go': 'Go',
    '.rb': 'Ruby',
    '.php': 'PHP',
    '.cs': 'C#',
    '.cpp': 'C++',
    '.c': 'C',
    '.rs': 'Rust',
    '.html': 'HTML',
    '.css': 'CSS'
}

FRAMEWORK_INDICATORS = {
    'requirements.txt': {
        'fastapi': 'FastAPI',
        'django': 'Django',
        'flask': 'Flask',
    },
    'package.json': {
        'react': 'React',
        'next': 'Next.js',
        'vue': 'Vue.js',
        'express': 'Express',
        'angular': 'Angular'
    },
    'pom.xml': {
        'spring-boot': 'Spring Boot'
    }
}

ENTRY_POINTS = {'main.py', 'app.py', 'index.js', 'manage.py', 'server.js'}

class RepoScanner:
    def __init__(self, root_dir: str):
        self.root_dir = root_dir
        self.modules: Set[str] = set()
        self.files: List[str] = []
        self.detected_languages: Set[str] = set()
        self.detected_frameworks: Set[str] = set()
        self.entry_points: List[str] = []

    def scan(self) -> RepoMap:
        logger.info(f"Starting scan of repository at {self.root_dir}")
        for root, dirs, files in os.walk(self.root_dir):
            rel_root = os.path.relpath(root, self.root_dir)
            if rel_root != '.':
                self.modules.add(rel_root)

            for file in files:
                rel_path = os.path.relpath(os.path.join(root, file), self.root_dir)
                self.files.append(rel_path)
                
                # Check for entry points
                if file in ENTRY_POINTS:
                    self.entry_points.append(rel_path)

                # Detect Languages
                _, ext = os.path.splitext(file)
                if ext in LANGUAGE_EXTENSIONS:
                    self.detected_languages.add(LANGUAGE_EXTENSIONS[ext])

                # Detect Frameworks
                if file in FRAMEWORK_INDICATORS:
                    self._check_framework_file(os.path.join(root, file), file)

        return RepoMap(
            root=self.root_dir,
            modules=sorted(list(self.modules)),
            files=sorted(self.files),
            detected_languages=sorted(list(self.detected_languages)),
            detected_frameworks=sorted(list(self.detected_frameworks))
        )

    def _check_framework_file(self, filepath: str, filename: str):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read().lower()
                indicators = FRAMEWORK_INDICATORS[filename]
                for key, framework in indicators.items():
                    if key in content:
                        self.detected_frameworks.add(framework)
        except Exception as e:
            logger.warning(f"Could not read {filepath} for framework detection: {e}")
