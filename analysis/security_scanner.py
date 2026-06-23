import subprocess
import json
import os
from typing import List

from models.response_models import Finding, FindingSeverity
from utils.logger import get_logger

logger = get_logger(__name__)

class SecurityScanner:
    def __init__(self, repo_path: str):
        self.repo_path = repo_path

    def run_bandit(self) -> List[Finding]:
        findings = []
        try:
            result = subprocess.run(
                ["bandit", "-r", ".", "-f", "json"],
                cwd=self.repo_path,
                capture_output=True,
                text=True
            )
            if result.stdout:
                try:
                    data = json.loads(result.stdout)
                    for issue in data.get("results", []):
                        sev_str = issue.get("issue_severity", "LOW").upper()
                        sev_map = {
                            "LOW": FindingSeverity.LOW,
                            "MEDIUM": FindingSeverity.MEDIUM,
                            "HIGH": FindingSeverity.HIGH
                        }
                        severity = sev_map.get(sev_str, FindingSeverity.LOW)
                        
                        if severity in [FindingSeverity.MEDIUM, FindingSeverity.HIGH]:
                            cwe_id = issue.get("issue_cwe", {}).get("id", 0)
                            score = min(10, (int(cwe_id) % 10) + 5) if cwe_id else 5
                            
                            findings.append(Finding(
                                tool="bandit",
                                file=issue.get("filename", ""),
                                line=issue.get("line_number", 0),
                                severity=severity,
                                message=issue.get("issue_text", ""),
                                severity_score=score
                            ))
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            logger.error(f"Error running bandit: {e}")
        return findings

    def run_semgrep(self) -> List[Finding]:
        findings = []
        try:
            result = subprocess.run(
                ["semgrep", "scan", "--config=auto", "--json"],
                cwd=self.repo_path,
                capture_output=True,
                text=True
            )
            if result.stdout:
                try:
                    data = json.loads(result.stdout)
                    for error in data.get("results", []):
                        sev_str = error.get("extra", {}).get("severity", "INFO").upper()
                        sev_map = {
                            "INFO": FindingSeverity.LOW,
                            "WARNING": FindingSeverity.MEDIUM,
                            "ERROR": FindingSeverity.HIGH
                        }
                        severity = sev_map.get(sev_str, FindingSeverity.LOW)
                        
                        if severity in [FindingSeverity.MEDIUM, FindingSeverity.HIGH]:
                            findings.append(Finding(
                                tool="semgrep",
                                file=error.get("path", ""),
                                line=error.get("start", {}).get("line", 0),
                                severity=severity,
                                message=error.get("extra", {}).get("message", ""),
                                severity_score=8 if severity == FindingSeverity.HIGH else 5
                            ))
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            logger.error(f"Error running semgrep: {e}")
        return findings

    def analyze_repo(self) -> List[Finding]:
        all_findings = []
        all_findings.extend(self.run_bandit())
        all_findings.extend(self.run_semgrep())
        return all_findings
