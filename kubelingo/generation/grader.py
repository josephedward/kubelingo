"""
Grading module for Kubelingo.
Implements static validation and AI-based evaluation.
"""
import os
import json
import yaml
import subprocess
import tempfile
import requests
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

class GraderType(Enum):
    STATIC_ONLY = "static_only"
    AI_ONLY = "ai_only"
    HYBRID = "hybrid"

@dataclass
class StaticValidationResult:
    tool: str
    passed: bool
    score: int
    issues: List[str]
    warnings: List[str]
    execution_time: float

@dataclass
class AIEvaluationResult:
    model: str
    score: int
    explanation: str
    issues: List[str]
    suggestions: List[str]
    rewritten_manifest: Optional[str]
    confidence: float

@dataclass
class GradingResult:
    overall_score: int
    static_results: List[StaticValidationResult]
    ai_result: Optional[AIEvaluationResult]
    final_grade: str
    summary: str
    recommendations: List[str]

class StaticValidator:
    """Performs static CLI-based manifest validation."""
    def __init__(self):
        self.tools = {
            "kubeconform": {
                "command": ["kubeconform", "-strict", "-summary"],
                "description": "Validates against Kubernetes OpenAPI schemas"
            },
            "kube-score": {
                "command": ["kube-score", "score", "--output-format", "json"],
                "description": "Checks best practices and security"
            },
            "kube-linter": {
                "command": ["kube-linter", "lint", "--format", "json"],
                "description": "Lints for reliability and security issues"
            },
            "checkov": {
                "command": ["checkov", "-f", "", "--framework", "kubernetes", "--output", "json"],
                "description": "Infrastructure as code security scanning"
            },
            "trivy": {
                "command": ["trivy", "config", "--format", "json"],
                "description": "Security vulnerability scanner"
            }
        }

    def validate_yaml_syntax(self, yaml_content: str) -> Tuple[bool, Optional[str]]:
        """Check basic YAML syntax."""
        try:
            yaml.safe_load(yaml_content)
            return True, None
        except yaml.YAMLError as e:
            return False, str(e)

    def normalize_yaml(self, yaml_content: str) -> str:
        """Normalize YAML formatting."""
        try:
            data = yaml.safe_load(yaml_content)
            return yaml.dump(data, sort_keys=False)
        except yaml.YAMLError:
            return yaml_content

    def run_tool(self, tool_name: str, yaml_content: str) -> StaticValidationResult:
        if tool_name not in self.tools:
            return StaticValidationResult(
                tool=tool_name,
                passed=False,
                score=0,
                issues=[f"Unknown tool: {tool_name}"],
                warnings=[],
                execution_time=0.0
            )
        config = self.tools[tool_name]
        import time
        start = time.time()
        # Write YAML to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_file = f.name
        try:
            cmd = config["command"].copy()
            if tool_name in ["kubeconform", "kube-score", "kube-linter", "trivy"]:
                cmd.append(temp_file)
            elif tool_name == "checkov":
                cmd = [c if c != "" else temp_file for c in cmd]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            elapsed = time.time() - start
            issues, warnings, score = self._parse_tool_output(
                tool_name, result.stdout, result.stderr, result.returncode
            )
            return StaticValidationResult(
                tool=tool_name,
                passed=(result.returncode == 0),
                score=score,
                issues=issues,
                warnings=warnings,
                execution_time=elapsed
            )
        except subprocess.TimeoutExpired:
            return StaticValidationResult(
                tool=tool_name,
                passed=False,
                score=0,
                issues=[f"Tool {tool_name} timed out"],
                warnings=[],
                execution_time=30.0
            )
        except FileNotFoundError:
            return StaticValidationResult(
                tool=tool_name,
                passed=False,
                score=0,
                issues=[f"Tool {tool_name} not found. Please install it."],
                warnings=[],
                execution_time=0.0
            )
        except Exception as e:
            return StaticValidationResult(
                tool=tool_name,
                passed=False,
                score=0,
                issues=[f"Error running {tool_name}: {e}"],
                warnings=[],
                execution_time=time.time() - start
            )
        finally:
            try:
                os.unlink(temp_file)
            except:
                pass

    def _parse_tool_output(self, tool_name: str, stdout: str, stderr: str, returncode: int) -> Tuple[List[str], List[str], int]:
        issues: List[str] = []
        warnings: List[str] = []
        score = 100
        # kubeconform
        if tool_name == "kubeconform":
            if returncode != 0:
                issues.append("Schema validation failed")
                issues.extend(stderr.split('\n') if stderr else [])
                score = 0
            elif "invalid" in stdout.lower():
                score = 50
                issues.append("Some validation issues found")
        # kube-score
        elif tool_name == "kube-score":
            try:
                data = json.loads(stdout) if stdout else []
                for item in data:
                    for check in item.get('checks', []):
                        severity = check.get('severity', '').upper()
                        if severity == 'ERROR':
                            issues.append(f"{check.get('checkName')}")
                            score -= 20
                        elif severity == 'WARNING':
                            warnings.append(f"{check.get('checkName')}")
                            score -= 10
            except json.JSONDecodeError:
                if returncode != 0:
                    issues.append("kube-score parse failed")
                    score = 50
        # kube-linter and other simple
        elif tool_name == "kube-linter":
            try:
                data = json.loads(stdout) if stdout else {}
                for report in data.get('Reports', []):
                    check = report.get('Check', '')
                    issues.append(check)
                    score -= 10
            except json.JSONDecodeError:
                if returncode != 0:
                    issues.append("kube-linter parse failed")
                    score = 50
        # checkov
        elif tool_name == "checkov":
            try:
                data = json.loads(stdout) if stdout else {}
                for report in data.get('results', {}).get('failed_checks', []):
                    issues.append(report.get('check_name', ''))
                    score -= 25
                for report in data.get('results', {}).get('skipped_checks', []):
                    warnings.append(report.get('check_name', ''))
                    score -= 10
            except json.JSONDecodeError:
                if returncode != 0:
                    issues.append("checkov security scan failed")
                    score = 50
        # trivy
        elif tool_name == "trivy":
            try:
                data = json.loads(stdout) if stdout else {}
                for result in data.get('Results', []):
                    for misconfig in result.get('Misconfigurations', []):
                        severity = misconfig.get('Severity', '').upper()
                        title = misconfig.get('Title', '')
                        if severity in ['CRITICAL', 'HIGH']:
                            issues.append(f"Config issue: {title}")
                            score -= 20
                        elif severity == 'MEDIUM':
                            warnings.append(f"Config warning: {title}")
                            score -= 8
            except json.JSONDecodeError:
                if returncode != 0:
                    issues.append("trivy scan failed")
                    score = 50
        return issues, warnings, max(score, 0)

class AIEvaluator:
    """Handles AI-based manifest evaluation."""
    def __init__(self, api_key: str, model: str = "gpt-4"):
        self.api_key = api_key
        self.model = model
        self.api_url = "https://api.openai.com/v1/chat/completions"

    def evaluate(
        self,
        yaml_content: str,
        question: str,
        goal: str = "",
        static_results: List[StaticValidationResult] = None
    ) -> AIEvaluationResult:
        """Perform AI-powered semantic evaluation"""
        static_summary = self._summarize_static_results(static_results or [])
        prompt = self._build_evaluation_prompt(yaml_content, question, goal, static_summary)
        try:
            response = self._call_ai_api(prompt)
            return self._parse_ai_response(response)
        except Exception as e:
            return AIEvaluationResult(
                model=self.model,
                score=0,
                explanation=f"AI evaluation failed: {e}",
                issues=["AI evaluation unavailable"],
                suggestions=["Check AI service configuration"],
                rewritten_manifest=None,
                confidence=0.0
            )

    def _summarize_static_results(self, static_results: List[StaticValidationResult]) -> str:
        parts: List[str] = []
        for result in static_results:
            if result.passed:
                parts.append(f"{result.tool}: PASSED (score: {result.score})")
            else:
                issues = ", ".join(result.issues[:3])
                parts.append(f"{result.tool}: FAILED (score: {result.score}) - {issues}")
        return "\n".join(parts)

    def _build_evaluation_prompt(self, yaml_content: str, question: str, goal: str, static_summary: str) -> str:
        return (
            f"Evaluate this Kubernetes manifest for the given question and goal."
            f"\nQUESTION: {question}\nGOAL: {goal}"
            f"\nMANIFEST:\n```yaml\n{yaml_content}\n```"
            f"\nSTATIC VALIDATION RESULTS:\n{static_summary}"
            "\nPlease provide a comprehensive evaluation considering semantic correctness, best practices, "
            "security, scalability, and maintainability. Respond in JSON format with keys: score, explanation, "
            "issues, suggestions, rewritten_manifest (optional), confidence."
        )

    def _call_ai_api(self, prompt: str) -> str:
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3
        }
        resp = requests.post(self.api_url, headers=headers, json=data, timeout=60)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def _parse_ai_response(self, response: str) -> AIEvaluationResult:
        try:
            if "```json" in response:
                start = response.find("```json") + len("```json")
                end = response.find("```", start)
                json_str = response[start:end].strip()
            else:
                json_str = response.strip()
            data = json.loads(json_str)
            return AIEvaluationResult(
                model=self.model,
                score=min(100, max(0, data.get("score", 0))),
                explanation=data.get("explanation", "No explanation provided"),
                issues=data.get("issues", []),
                suggestions=data.get("suggestions", []),
                rewritten_manifest=data.get("rewritten_manifest"),
                confidence=min(1.0, max(0.0, data.get("confidence", 0.5)))
            )
        except Exception as e:
            return AIEvaluationResult(
                model=self.model,
                score=50,
                explanation=f"Could not parse AI response: {e}. Raw response: {response[:200]}",
                issues=["AI response parsing failed"],
                suggestions=["Try with a different AI model or prompt"],
                rewritten_manifest=None,
                confidence=0.2
            )

class KubernetesGrader:
    """Orchestrates static and AI validation to produce a final grade."""
    def __init__(
        self,
        static_validator: Optional[StaticValidator] = None,
        ai_evaluator: Optional[AIEvaluator] = None,
        grading_mode: GraderType = GraderType.HYBRID
    ):
        self.static_validator = static_validator or StaticValidator()
        self.ai_evaluator = ai_evaluator
        self.grading_mode = grading_mode

    def grade(
        self,
        yaml_content: str,
        question: str,
        goal: str = "",
        static_tools: Optional[List[str]] = None
    ) -> GradingResult:
        """Grade a Kubernetes manifest comprehensively."""
        if static_tools is None:
            static_tools = ["kubeconform", "kube-score", "kube-linter"]
        # Step 1: YAML syntax validation
        is_valid, syntax_error = self.static_validator.validate_yaml_syntax(yaml_content)
        if not is_valid:
            return GradingResult(
                overall_score=0,
                static_results=[],
                ai_result=None,
                final_grade="F",
                summary=f"YAML syntax error: {syntax_error}",
                recommendations=["Fix YAML syntax errors before proceeding"]
            )
        # Step 2: Normalize YAML
        normalized_yaml = self.static_validator.normalize_yaml(yaml_content)
        # Step 3: Static validation
        static_results: List[StaticValidationResult] = []
        if self.grading_mode in (GraderType.STATIC_ONLY, GraderType.HYBRID):
            for tool in static_tools:
                result = self.static_validator.run_tool(tool, normalized_yaml)
                static_results.append(result)
        # Step 4: AI evaluation
        ai_result: Optional[AIEvaluationResult] = None
        if self.grading_mode in (GraderType.AI_ONLY, GraderType.HYBRID) and self.ai_evaluator:
            ai_result = self.ai_evaluator.evaluate(normalized_yaml, question, goal, static_results)
        # Step 5: Calculate overall score
        overall_score = self._calculate_overall_score(static_results, ai_result)
        # Step 6: Determine final grade, summary, and recommendations
        final_grade = self._score_to_grade(overall_score)
        summary = self._generate_summary(static_results, ai_result, overall_score)
        recommendations = self._generate_recommendations(static_results, ai_result)
        return GradingResult(
            overall_score=overall_score,
            static_results=static_results,
            ai_result=ai_result,
            final_grade=final_grade,
            summary=summary,
            recommendations=recommendations
        )
    
    def _calculate_overall_score(
        self,
        static_results: List[StaticValidationResult],
        ai_result: Optional[AIEvaluationResult]
    ) -> int:
        if self.grading_mode == GraderType.STATIC_ONLY:
            return int(sum(r.score for r in static_results) / len(static_results)) if static_results else 0
        if self.grading_mode == GraderType.AI_ONLY:
            return ai_result.score if ai_result else 0
        # HYBRID mode: 40% static, 60% AI
        static_score = int(sum(r.score for r in static_results) / len(static_results)) if static_results else 0
        ai_score = ai_result.score if ai_result else static_score
        return int(0.4 * static_score + 0.6 * ai_score)

    def _score_to_grade(self, score: int) -> str:
        if score >= 90:
            return "A"
        if score >= 80:
            return "B"
        if score >= 70:
            return "C"
        if score >= 60:
            return "D"
        return "F"

    def _generate_summary(
        self,
        static_results: List[StaticValidationResult],
        ai_result: Optional[AIEvaluationResult],
        overall_score: int
    ) -> str:
        parts = [f"Overall Score: {overall_score}/100"]
        if static_results:
            passed = [r.tool for r in static_results if r.passed]
            failed = [r.tool for r in static_results if not r.passed]
            if passed:
                parts.append(f"Static validation passed: {', '.join(passed)}")
            if failed:
                parts.append(f"Static validation failed: {', '.join(failed)}")
        if ai_result:
            level = "high" if ai_result.confidence > 0.8 else "medium" if ai_result.confidence > 0.5 else "low"
            parts.append(f"AI evaluation: {ai_result.score}/100 (confidence: {level})")
        return ". ".join(parts)

    def _generate_recommendations(
        self,
        static_results: List[StaticValidationResult],
        ai_result: Optional[AIEvaluationResult]
    ) -> List[str]:
        recs: List[str] = []
        for res in static_results:
            if res.issues:
                recs.extend([f"[{res.tool}] {issue}" for issue in res.issues[:2]])
        if ai_result and ai_result.suggestions:
            recs.extend([f"[AI] {s}" for s in ai_result.suggestions[:3]])
        return recs[:5]