import subprocess
import json
import os
from typing import List

from models.response_models import Finding, FindingSeverity
from utils.logger import get_logger

logger = get_logger(__name__)

class StaticAnalyzer:
    def __init__(self, repo_path: str):
        self.repo_path = repo_path

    def run_pylint(self) -> List[Finding]:
        findings = []
        try:
            result = subprocess.run(
                ["pylint", ".", "-f", "json", "--recursive=y", "--ignore=venv,node_modules,.git"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=60,
                stdin=subprocess.DEVNULL
            )
            # Pylint outputs JSON to stdout even when it returns non-zero
            if result.stdout:
                data = json.loads(result.stdout)
                for item in data:
                    sev_map = {
                        "fatal": FindingSeverity.ERROR,
                        "error": FindingSeverity.ERROR,
                        "warning": FindingSeverity.WARNING,
                        "refactor": FindingSeverity.LOW,
                        "convention": FindingSeverity.LOW
                    }
                    severity = sev_map.get(item.get("type", "warning"), FindingSeverity.WARNING)
                    if severity in [FindingSeverity.WARNING, FindingSeverity.ERROR]:
                        findings.append(Finding(
                            tool="pylint",
                            file=item.get("path", ""),
                            line=item.get("line", 0),
                            severity=severity,
                            message=f"{item.get('symbol', '')}: {item.get('message', '')}"
                        ))
        except Exception as e:
            logger.error(f"Error running pylint: {e}")
        return findings

    def run_flake8(self) -> List[Finding]:
        findings = []
        try:
            result = subprocess.run(
                ["flake8", ".", "--exclude=venv,node_modules,.git"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=60,
                stdin=subprocess.DEVNULL
            )
            if result.stdout:
                for line in result.stdout.splitlines():
                    parts = line.split(":")
                    if len(parts) >= 4:
                        f_path = parts[0]
                        line_num = int(parts[1]) if parts[1].isdigit() else 0
                        message = ":".join(parts[3:]).strip()
                        findings.append(Finding(
                            tool="flake8",
                            file=f_path,
                            line=line_num,
                            severity=FindingSeverity.WARNING,
                            message=message
                        ))
        except Exception as e:
            logger.error(f"Error running flake8: {e}")
        return findings

    def run_mypy(self) -> List[Finding]:
        findings = []
        try:
            result = subprocess.run(
                ["mypy", ".", "--show-error-codes", "--no-error-summary", "--exclude", "venv|node_modules|\\.git"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=60,
                stdin=subprocess.DEVNULL
            )
            if result.stdout:
                for line in result.stdout.splitlines():
                    parts = line.split(":")
                    if len(parts) >= 3 and ("error" in parts[2] or "note" in parts[2]):
                        f_path = parts[0].strip()
                        line_num = int(parts[1].strip()) if parts[1].strip().isdigit() else 0
                        msg_type = parts[2].strip()
                        message = ":".join(parts[3:]).strip()
                        
                        if msg_type == "error":
                            findings.append(Finding(
                                tool="mypy",
                                file=f_path,
                                line=line_num,
                                severity=FindingSeverity.ERROR,
                                message=message
                            ))
        except Exception as e:
            logger.error(f"Error running mypy: {e}")
        return findings

    def analyze_repo(self, session_id: str) -> List[Finding]:
        all_findings = []
        all_findings.extend(self.run_pylint())
        all_findings.extend(self.run_flake8())
        all_findings.extend(self.run_mypy())
        return all_findings
