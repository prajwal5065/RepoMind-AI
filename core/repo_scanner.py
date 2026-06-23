import os
from typing import List, Set
from models.response_models import RepoMap
from core.code_parser import parse_python_file
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

# Directories to completely skip during scanning
SKIP_DIRS = {
    '.git', '.hg', '.svn',             # version control internals
    'node_modules', '.npm',             # JS deps
    '__pycache__', '.mypy_cache',       # Python bytecode / type-check caches
    'venv', '.venv', 'env', '.env',     # virtual envs
    '.tox', '.pytest_cache',            # test runners
    'dist', 'build', '.next', 'out',    # build artifacts
    '.idea', '.vscode', '.vs',          # IDE dirs
    'coverage', '.coverage',
}

# File extensions that are binary — skip entirely (no chunking, no parsing)
BINARY_EXTENSIONS = {
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.svg', '.webp',
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.zip', '.tar', '.gz', '.bz2', '.xz', '.7z', '.rar',
    '.exe', '.dll', '.so', '.dylib', '.bin', '.obj', '.o', '.a',
    '.pyc', '.pyo', '.pyd',
    '.lock',                  # package-lock.json is text, but lockfiles are noise
    '.woff', '.woff2', '.ttf', '.otf', '.eot',
    '.mp3', '.mp4', '.wav', '.avi', '.mov',
    '.db', '.sqlite', '.sqlite3',
    '.jar', '.class',
    '.pack', '.idx',          # git pack files
}

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
        dependencies = {}
        for root, dirs, files in os.walk(self.root_dir):
            # Prune skip dirs in-place so os.walk doesn't descend into them
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith('.')]

            rel_root = os.path.relpath(root, self.root_dir).replace('\\', '/')
            if rel_root != '.':
                self.modules.add(rel_root)

            for file in files:
                _, ext = os.path.splitext(file)
                # Skip binary files entirely
                if ext.lower() in BINARY_EXTENSIONS:
                    continue

                rel_path = os.path.relpath(os.path.join(root, file), self.root_dir).replace('\\', '/')
                self.files.append(rel_path)

                # Check for entry points
                if file in ENTRY_POINTS:
                    self.entry_points.append(rel_path)

                # Detect Languages
                if ext in LANGUAGE_EXTENSIONS:
                    self.detected_languages.add(LANGUAGE_EXTENSIONS[ext])

                # Detect Frameworks
                if file in FRAMEWORK_INDICATORS:
                    self._check_framework_file(os.path.join(root, file), file)

                # Parse Dependencies (Python only)
                if ext == '.py':
                    try:
                        parsed = parse_python_file(os.path.join(root, file), repo_root=self.root_dir)
                        if parsed and parsed.local_dependencies:
                            dependencies[rel_path] = parsed.local_dependencies
                    except Exception as e:
                        logger.debug(f"Skipping dependency parse for {rel_path}: {e}")

        return RepoMap(
            root=self.root_dir,
            modules=sorted(list(self.modules)),
            files=sorted(self.files),
            detected_languages=sorted(list(self.detected_languages)),
            detected_frameworks=sorted(list(self.detected_frameworks)),
            dependencies=dependencies
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
