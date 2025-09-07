#!/usr/bin/env python3
"""
Kubernetes Manifest Grader Module

This module provides a comprehensive grading system that combines static validation
with AI-powered semantic evaluation for maximum flexibility.
"""

import os
import json
import yaml
import subprocess
import tempfile
import requests
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import hashlib
import time

class GraderType(Enum):
    STATIC_ONLY = "static_only"
    AI_ONLY = "ai_only"  
    HYBRID = "hybrid"

@dataclass
class StaticValidationResult:
    tool: str
    passed: bool
    score: int  # 0-100
    issues: List[str]
    warnings: List[str]
    execution_time: float

@dataclass 
class AIEvaluationResult:
    model: str
    score: int  # 0-100
    explanation: str
    issues: List[str]
    suggestions: List[str]
    rewritten_manifest: Optional[str]
    confidence: float

@dataclass
class GradingResult:
    overall_score: int  # 0-100
    static_results: List[StaticValidationResult]
    ai_result: Optional[AIEvaluationResult]
    final_grade: str  # A, B, C, D, F
    summary: str
    recommendations: List[str]

class StaticValidator:
    """Handles static validation using various CLI tools"""
    
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
        """Basic YAML syntax validation"""
        try:
            yaml.safe_load(yaml_content)
            return True, None
        except yaml.YAMLError as e:
            return False, str(e)
    
    def normalize_yaml(self, yaml_content: str) -> str:
        """Normalize YAML formatting (fix indentation, etc.)"""
        try:
            data = yaml.safe_load(yaml_content)
            return yaml.dump(data, sort_keys=False, default_flow_style=False)
        except yaml.YAMLError:
            return yaml_content  # Return as-is if parsing fails
    
    def run_tool(self, tool_name: str, yaml_content: str) -> StaticValidationResult:
        """Run a specific static validation tool"""
        if tool_name not in self.tools:
            return StaticValidationResult(
                tool=tool_name,
                passed=False,
                score=0,
                issues=[f"Unknown tool: {tool_name}"],
                warnings=[],
                execution_time=0.0
            )
        
        tool_config = self.tools[tool_name]
        start_time = time.time()
        
        # Write YAML to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_file = f.name
        
        try:
            # Adjust command for file input
            cmd = tool_config["command"].copy()
            if tool_name in ["kubeconform", "kube-score", "kube-linter", "trivy"]:
                cmd.append(temp_file)
            elif tool_name == "checkov":
                # Replace empty string with actual file path
                cmd = [c if c != "" else temp_file for c in cmd]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            execution_time = time.time() - start_time
            
            # Parse output based on tool
            issues, warnings, score = self._parse_tool_output(tool_name, result.stdout, result.stderr, result.returncode)
            
            return StaticValidationResult(
                tool=tool_name,
                passed=result.returncode == 0,
                score=score,
                issues=issues,
                warnings=warnings,
                execution_time=execution_time
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
                issues=[f"Error running {tool_name}: {str(e)}"],
                warnings=[],
                execution_time=time.time() - start_time
            )
        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_file)
            except:
                pass
    
    def _parse_tool_output(self, tool_name: str, stdout: str, stderr: str, returncode: int) -> Tuple[List[str], List[str], int]:
        """Parse tool output to extract issues, warnings, and calculate score"""
        issues = []
        warnings = []
        score = 100  # Start with perfect score
        
        if tool_name == "kubeconform":
            if returncode != 0:
                issues.append("Schema validation failed")
                issues.extend(stderr.split('\n') if stderr else [])
                score = 0
            elif "invalid" in stdout.lower():
                score = 50
                issues.append("Some validation issues found")
        
        elif tool_name == "kube-score":
            try:
                if stdout:
                    data = json.loads(stdout)
                    for item in data:
                        if 'checks' in item:
                            for check in item['checks']:
                                if check.get('grade') == 'CRITICAL':
                                    issues.append(f"Critical: {check.get('comment', 'Unknown issue')}")
                                    score -= 20
                                elif check.get('grade') == 'WARNING':
                                    warnings.append(f"Warning: {check.get('comment', 'Unknown warning')}")
                                    score -= 5
            except json.JSONDecodeError:
                if returncode != 0:
                    issues.append("kube-score analysis failed")
                    score = 50
        
        elif tool_name == "kube-linter":
            try:
                if stdout:
                    data = json.loads(stdout)
                    if 'Reports' in data:
                        for report in data['Reports']:
                            if report.get('Severity') == 'error':
                                issues.append(f"Error: {report.get('Message', 'Unknown error')}")
                                score -= 15
                            elif report.get('Severity') == 'warning':
                                warnings.append(f"Warning: {report.get('Message', 'Unknown warning')}")
                                score -= 5
            except json.JSONDecodeError:
                if returncode != 0:
                    issues.append("kube-linter analysis failed")
                    score = 50
        
        elif tool_name == "checkov":
            try:
                if stdout:
                    data = json.loads(stdout)
                    if 'results' in data:
                        failed_checks = data['results'].get('failed_checks', [])
                        for check in failed_checks:
                            severity = check.get('severity', 'UNKNOWN')
                            if severity in ['CRITICAL', 'HIGH']:
                                issues.append(f"Security issue: {check.get('check_name', 'Unknown')}")
                                score -= 25
                            elif severity == 'MEDIUM':
                                warnings.append(f"Medium security issue: {check.get('check_name', 'Unknown')}")
                                score -= 10
            except json.JSONDecodeError:
                if returncode != 0:
                    issues.append("checkov security scan failed")
                    score = 50
        
        elif tool_name == "trivy":
            try:
                if stdout:
                    data = json.loads(stdout)
                    if 'Results' in data:
                        for result in data['Results']:
                            if 'Misconfigurations' in result:
                                for misconfig in result['Misconfigurations']:
                                    severity = misconfig.get('Severity', 'UNKNOWN')
                                    if severity in ['CRITICAL', 'HIGH']:
                                        issues.append(f"Config issue: {misconfig.get('Title', 'Unknown')}")
                                        score -= 20
                                    elif severity == 'MEDIUM':
                                        warnings.append(f"Config warning: {misconfig.get('Title', 'Unknown')}")
                                        score -= 8
            except json.JSONDecodeError:
                if returncode != 0:
                    issues.append("trivy scan failed")
                    score = 50
        
        return issues, warnings, max(0, score)  # Ensure score doesn't go below 0

class AIEvaluator:
    """Handles AI-powered semantic evaluation"""
    
    def __init__(self, api_key: str, model: str = "gpt-4", api_url: str = "https://api.openai.com/v1/chat/completions"):
        self.api_key = api_key
        self.model = model
        self.api_url = api_url
    
    def evaluate(self, yaml_content: str, question: str, goal: str, static_results: List[StaticValidationResult]) -> AIEvaluationResult:
        """Perform AI-powered semantic evaluation"""
        
        # Prepare static results summary
        static_summary = self._summarize_static_results(static_results)
        
        prompt = self._build_evaluation_prompt(yaml_content, question, goal, static_summary)
        
        try:
            response = self._call_ai_api(prompt)
            return self._parse_ai_response(response)
        except Exception as e:
            return AIEvaluationResult(
                model=self.model,
                score=0,
                explanation=f"AI evaluation failed: {str(e)}",
                issues=["AI evaluation unavailable"],
                suggestions=["Check AI service configuration"],
                rewritten_manifest=None,
                confidence=0.0
            )
    
    def _summarize_static_results(self, static_results: List[StaticValidationResult]) -> str:
        """Create summary of static validation results"""
        summary_parts = []
        
        for result in static_results:
            if result.passed:
                summary_parts.append(f"{result.tool}: PASSED (score: {result.score})")
            else:
                issues_str = ", ".join(result.issues[:3])  # First 3 issues
                summary_parts.append(f"{result.tool}: FAILED (score: {result.score}) - {issues_str}")
        
        return "\n".join(summary_parts)
    
    def _build_evaluation_prompt(self, yaml_content: str, question: str, goal: str, static_summary: str) -> str:
        """Build the evaluation prompt for the AI"""
        return f"""
Evaluate this Kubernetes manifest for the given question and goal.
Consider semantic correctness, best practices, and how well it achieves the objective.

QUESTION: {question}
GOAL: {goal}

MANIFEST:
```yaml
{yaml_content}
```

STATIC VALIDATION RESULTS:
{static_summary}

Please provide a comprehensive evaluation considering:
1. Semantic correctness relative to the goal
2. Best practices adherence 
3. Security considerations
4. Scalability and maintainability
5. Handling of variations/aliases
6. Overall effectiveness

Respond in JSON format:
{{
    "score": 0-100,
    "explanation": "Detailed reasoning for the score",
    "issues": ["list", "of", "problems"],
    "suggestions": ["list", "of", "improvements"],
    "rewritten_manifest": "optional improved YAML or null",
    "confidence": 0.0-1.0
}}
"""
    
    def _call_ai_api(self, prompt: str) -> str:
        """Call the AI API with the evaluation prompt"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3  # Lower temperature for more consistent evaluation
        }
        
        response = requests.post(self.api_url, headers=headers, json=data, timeout=60)
        response.raise_for_status()
        
        return response.json()["choices"][0]["message"]["content"]
    
    def _parse_ai_response(self, response: str) -> AIEvaluationResult:
        """Parse the AI response into structured result"""
        try:
            # Extract JSON from response (handle markdown code blocks)
            if "```json" in response:
                json_start = response.find("```json") + 7
                json_end = response.find("```", json_start)
                json_content = response[json_start:json_end].strip()
            else:
                json_content = response.strip()
            
            data = json.loads(json_content)
            
            return AIEvaluationResult(
                model=self.model,
                score=min(100, max(0, data.get("score", 0))),
                explanation=data.get("explanation", "No explanation provided"),
                issues=data.get("issues", []),
                suggestions=data.get("suggestions", []),
                rewritten_manifest=data.get("rewritten_manifest"),
                confidence=min(1.0, max(0.0, data.get("confidence", 0.5)))
            )
            
        except (json.JSONDecodeError, KeyError) as e:
            # Fallback parsing for non-JSON responses
            return AIEvaluationResult(
                model=self.model,
                score=50,  # Default score
                explanation=f"Could not parse AI response: {str(e)}. Raw response: {response[:200]}",
                issues=["AI response parsing failed"],
                suggestions=["Try with a different AI model or prompt"],
                rewritten_manifest=None,
                confidence=0.2
            )

def grade_simple_answer(user_answer: str, correct_answer: str) -> bool:
    """Grade a simple answer by case-insensitive comparison."""
    return user_answer.strip().lower() == correct_answer.strip().lower()


class KubernetesGrader:
    """Main grading orchestrator"""
    
    def __init__(self, 
                 static_validator: Optional[StaticValidator] = None,
                 ai_evaluator: Optional[AIEvaluator] = None,
                 grading_mode: GraderType = GraderType.HYBRID):
        
        self.static_validator = static_validator or StaticValidator()
        self.ai_evaluator = ai_evaluator
        self.grading_mode = grading_mode
    
    def grade(self, yaml_content: str, question: str, goal: str = "", 
              static_tools: List[str] = None) -> GradingResult:
        """Grade a Kubernetes manifest comprehensively"""
        
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
        static_results = []
        if self.grading_mode in [GraderType.STATIC_ONLY, GraderType.HYBRID]:
            for tool in static_tools:
                result = self.static_validator.run_tool(tool, normalized_yaml)
                static_results.append(result)
        
        # Step 4: AI evaluation
        ai_result = None
        if self.grading_mode in [GraderType.AI_ONLY, GraderType.HYBRID] and self.ai_evaluator:
            ai_result = self.ai_evaluator.evaluate(normalized_yaml, question, goal, static_results)
        
        # Step 5: Calculate overall score
        overall_score = self._calculate_overall_score(static_results, ai_result)
        
        # Step 6: Generate final grade and summary
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
    
    def _calculate_overall_score(self, static_results: List[StaticValidationResult], 
                                ai_result: Optional[AIEvaluationResult]) -> int:
        """Calculate weighted overall score"""
        
        if self.grading_mode == GraderType.STATIC_ONLY:
            if not static_results:
                return 0
            return int(sum(r.score for r in static_results) / len(static_results))
        
        elif self.grading_mode == GraderType.AI_ONLY:
            return ai_result.score if ai_result else 0
        
        else:  # HYBRID
            static_score = int(sum(r.score for r in static_results) / len(static_results)) if static_results else 0
            ai_score = ai_result.score if ai_result else static_score
            
            # Weight: 40% static, 60% AI (AI can handle nuances better)
            return int(0.4 * static_score + 0.6 * ai_score)
    
    def _score_to_grade(self, score: int) -> str:
        """Convert numeric score to letter grade"""
        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        else:
            return "F"
    
    def _generate_summary(self, static_results: List[StaticValidationResult], 
                         ai_result: Optional[AIEvaluationResult], 
                         overall_score: int) -> str:
        """Generate grading summary"""
        
        summary_parts = [f"Overall Score: {overall_score}/100"]
        
        if static_results:
            passed_tools = [r.tool for r in static_results if r.passed]
            failed_tools = [r.tool for r in static_results if not r.passed]
            
            if passed_tools:
                summary_parts.append(f"Static validation passed: {', '.join(passed_tools)}")
            if failed_tools:
                summary_parts.append(f"Static validation failed: {', '.join(failed_tools)}")
        
        if ai_result:
            confidence_level = "high" if ai_result.confidence > 0.8 else "medium" if ai_result.confidence > 0.5 else "low"
            summary_parts.append(f"AI evaluation: {ai_result.score}/100 (confidence: {confidence_level})")
        
        return ". ".join(summary_parts)
    
    def _generate_recommendations(self, static_results: List[StaticValidationResult], 
                                 ai_result: Optional[AIEvaluationResult]) -> List[str]:
        """Generate improvement recommendations"""
        recommendations = []
        
        # From static tools
        for result in static_results:
            if result.issues:
                recommendations.extend([f"[{result.tool}] {issue}" for issue in result.issues[:2]])
        
        # From AI
        if ai_result and ai_result.suggestions:
            recommendations.extend([f"[AI] {suggestion}" for suggestion in ai_result.suggestions[:3]])
        
        return recommendations[:5]  # Limit to top 5 recommendations

def main():
    """Demo usage of the grading system"""
    
    # Sample YAML for testing
    test_yaml = """
apiVersion: v1
kind: Pod
metadata:
  name: nginx-pod
spec:
  containers:
  - name: nginx
    image: nginx:1.21
    ports:
    - containerPort: 80
"""
    
    # Initialize grader (static only for demo)
    grader = KubernetesGrader(grading_mode=GraderType.STATIC_ONLY)
    
    # Grade the manifest
    result = grader.grade(
        yaml_content=test_yaml,
        question="Create a simple nginx pod",
        goal="Deploy a basic web server pod"
    )
    
    print("=== Grading Results ===")
    print(f"Overall Score: {result.overall_score}/100")
    print(f"Final Grade: {result.final_grade}")
    print(f"Summary: {result.summary}")
    
    print("\nStatic Validation Results:")
    for static_result in result.static_results:
        status = "PASS" if static_result.passed else "FAIL"
        print(f"  {static_result.tool}: {status} (Score: {static_result.score})")
        if static_result.issues:
            for issue in static_result.issues[:2]:
                print(f"    - {issue}")
    
    if result.recommendations:
        print(f"\nRecommendations:")
        for rec in result.recommendations:
            print(f"  - {rec}")

if __name__ == "__main__":
    main()