#!/usr/bin/env python3
"""
Extended Kubernetes Manifest Generator with All AI Backends

This module orchestrates multiple AI backends including APIs and CLI tools
for comprehensive Kubernetes manifest generation and comparison.
"""

import os
import json
import requests
import subprocess
import yaml
import argparse
import time
from typing import Dict, List, Optional, Any
from difflib import unified_diff
# Import our custom modules
from kubelingo.backend_integrator import BackendIntegrator, BackendType
from kubelingo.grader import KubernetesGrader, AIEvaluator, GraderType
from kubelingo.question_generator import QuestionGenerator
try:
    from dotenv import load_dotenv
    # Load environment variables
    load_dotenv()
except ImportError:
    # dotenv not installed; skip loading .env file
    pass

class ManifestGenerator:
    def __init__(self, env_file_path: str = ".env"):
        self.env_vars = self._load_env_vars(env_file_path)
        self.backend_integrator = BackendIntegrator(env_file_path)
        self.question_generator = QuestionGenerator(manifest_generator=self)
        
        # Initialize AI evaluator for grading if keys available
        self.grader = None
        if self.env_vars.get("OPENAI_API_KEY"):
            ai_evaluator = AIEvaluator(self.env_vars["OPENAI_API_KEY"])
            self.grader = KubernetesGrader(ai_evaluator=ai_evaluator, grading_mode=GraderType.HYBRID)
        elif self.env_vars.get("GEMINI_API_KEY"):
            # Could also support Gemini for evaluation
            self.grader = KubernetesGrader(grading_mode=GraderType.STATIC_ONLY)
        else:
            self.grader = KubernetesGrader(grading_mode=GraderType.STATIC_ONLY)
    
    def _load_env_vars(self, env_file_path: str) -> Dict[str, str]:
        """Load environment variables"""
        env_vars = dict(os.environ)
        
        if os.path.exists(env_file_path):
            with open(env_file_path, 'r') as f:
                for line in f:
                    if '=' in line and not line.strip().startswith('#'):
                        key, value = line.strip().split('=', 1)
                        env_vars[key] = value.strip('"').strip("'")
        
        return env_vars
    
    # API-based generators
    def generate_with_openai(self, prompt: str) -> str:
        """Generate using OpenAI API"""
        if not self.env_vars.get("OPENAI_API_KEY"):
            return "Error: OPENAI_API_KEY not found"
        
        headers = {
            "Authorization": f"Bearer {self.env_vars['OPENAI_API_KEY']}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "gpt-4",
            "messages": [
                {"role": "system", "content": "You are a Kubernetes expert. Generate valid YAML manifests based on user prompts. Only respond with YAML code, no explanations."},
                {"role": "user", "content": f"Generate Kubernetes YAML for: {prompt}"}
            ],
            "temperature": 0.3
        }
        
        try:
            response = requests.post("https://api.openai.com/v1/chat/completions", 
                                   headers=headers, json=data, timeout=30)
            response.raise_for_status()
            
            content = response.json()["choices"][0]["message"]["content"]
            if return_raw_text:
                return content
            return self._extract_yaml_from_content(content)
            
        except Exception as e:
            return f"Error: {str(e)}"
    
    def generate_with_gemini(self, prompt: str) -> str:
        """Generate using Google Gemini API"""
        if not self.env_vars.get("GEMINI_API_KEY"):
            return "Error: GEMINI_API_KEY not found"
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={self.env_vars['GEMINI_API_KEY']}"
        
        headers = {"Content-Type": "application/json"}
        
        data = {
            "contents": [{
                "parts": [{
                    "text": f"Generate Kubernetes YAML for: {prompt}. Respond only with valid YAML, no explanations."
                }]
            }],
            "generationConfig": {
                "temperature": 0.3,
                "topK": 40,
                "topP": 0.95,
                "maxOutputTokens": 2048
            }
        }
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            
            content = response.json()["candidates"][0]["content"]["parts"][0]["text"]
            return self._extract_yaml_from_content(content)
            
        except Exception as e:
            return f"Error: {str(e)}"
    
    
    
    def generate_with_ollama(self, prompt: str, model: str = "llama3", return_raw_text: bool = False) -> str:
        """Generate using local Ollama"""
        ollama_url = self.env_vars.get("OLLAMA_HOST", "http://localhost:11434")
        
        data = {
            "model": model,
            "prompt": f"Generate Kubernetes YAML for: {prompt}. Respond only with valid YAML code, no explanations.",
            "stream": False
        }
        
        try:
            response = requests.post(f"{ollama_url}/api/generate", 
                                   json=data, timeout=60)
            response.raise_for_status()
            
            content = response.json()["response"]
            if return_raw_text:
                return content
            return self._extract_yaml_from_content(content)
            
        except Exception as e:
            return f"Error: {str(e)}"
    
    def _extract_yaml_from_content(self, content: str) -> str:
        """Extract YAML from response content"""
        lines = content.split('\n')
        yaml_lines = []
        in_yaml_block = False
        
        for line in lines:
            if '```yaml' in line.lower() or '```yml' in line.lower():
                in_yaml_block = True
                continue
            elif '```' in line and in_yaml_block:
                break
            elif in_yaml_block:
                yaml_lines.append(line)
            elif line.strip().startswith(('apiVersion:', 'kind:', 'metadata:')):
                in_yaml_block = True
                yaml_lines.append(line)
        
        yaml_content = '\n'.join(yaml_lines).strip()
        return yaml_content if yaml_content else content.strip()
    
    def introduce_flaw(self, yaml_content: str, flaw_type: str) -> str:
        """Introduce intentional flaws for testing"""
        if flaw_type == "none":
            return yaml_content
        
        try:
            data = yaml.safe_load(yaml_content)
            
            if flaw_type == "missing-replicas" and data.get("kind") == "Deployment":
                if "spec" in data and "replicas" in data["spec"]:
                    del data["spec"]["replicas"]
            
            elif flaw_type == "invalid-port":
                # Find and modify port to invalid value
                self._modify_ports_recursive(data, 99999)
            
            elif flaw_type == "missing-labels":
                if "metadata" in data and "labels" in data["metadata"]:
                    del data["metadata"]["labels"]
            
            elif flaw_type == "wrong-api-version":
                data["apiVersion"] = "v2"  # Usually invalid
            
            return yaml.dump(data, default_flow_style=False)
        
        except Exception:
            return yaml_content  # Return original if modification fails
    
    def _modify_ports_recursive(self, obj: Any, new_port: int):
        """Recursively find and modify ports"""
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key in ["port", "containerPort", "targetPort"] and isinstance(value, int):
                    obj[key] = new_port
                else:
                    self._modify_ports_recursive(value, new_port)
        elif isinstance(obj, list):
            for item in obj:
                self._modify_ports_recursive(item, new_port)
    
    def validate_yaml(self, yaml_content: str) -> Dict[str, Any]:
        """Basic YAML validation"""
        try:
            yaml.safe_load(yaml_content)
            return {"valid": True, "error": None}
        except yaml.YAMLError as e:
            return {"valid": False, "error": str(e)}
    
    def grade_manifest(self, yaml_content: str, prompt: str) -> Dict[str, Any]:
        """Grade a manifest using the comprehensive grader"""
        if not self.grader:
            return {"score": 0, "error": "Grader not available"}
        
        try:
            result = self.grader.grade(yaml_content, prompt, prompt)
            return {
                "score": result.overall_score,
                "grade": result.final_grade,
                "summary": result.summary,
                "recommendations": result.recommendations,
                "details": {
                    "static_results": [
                        {
                            "tool": r.tool,
                            "passed": r.passed,
                            "score": r.score,
                            "issues": r.issues[:3]  # Limit for display
                        } for r in result.static_results
                    ]
                }
            }
        except Exception as e:
            return {"score": 0, "error": f"Grading failed: {str(e)}"}
    
    def run_comprehensive_test(self, prompt: str, backends: List[str], include_grading: bool = True) -> Dict[str, Any]:
        """Run comprehensive test across multiple backends"""
        results = {}
        
        # API-based backends
        api_generators = {
            "openai": self.generate_with_openai,
            "gemini": self.generate_with_gemini,
            
            "ollama": self.generate_with_ollama
        }
        
        # CLI-based backends via integrator
        cli_backends = [b for b in backends if b in [bt.value for bt in BackendType]]
        
        # Run API backends
        for backend in backends:
            if backend in api_generators:
                start_time = time.time()
                yaml_content = api_generators[backend](prompt)
                execution_time = time.time() - start_time
                
                validation = self.validate_yaml(yaml_content)
                
                grading = {}
                if include_grading and validation["valid"]:
                    grading = self.grade_manifest(yaml_content, prompt)
                
                results[backend] = {
                    "yaml": yaml_content,
                    "validation": validation,
                    "grading": grading,
                    "execution_time": execution_time
                }
        
        # Run CLI backends
        if cli_backends:
            cli_results = self.backend_integrator.run_multiple_backends(cli_backends, prompt)
            
            for cli_result in cli_results:
                validation = {"valid": True, "error": None}
                if cli_result.yaml_content:
                    validation = self.validate_yaml(cli_result.yaml_content)
                
                grading = {}
                if include_grading and cli_result.yaml_content and validation["valid"]:
                    grading = self.grade_manifest(cli_result.yaml_content, prompt)
                
                results[cli_result.backend] = {
                    "yaml": cli_result.yaml_content or cli_result.output,
                    "validation": validation,
                    "grading": grading,
                    "execution_time": cli_result.execution_time,
                    "success": cli_result.success,
                    "error": cli_result.error if not cli_result.success else None
                }
        
        return results

def parse_args():
    parser = argparse.ArgumentParser(description="Kubernetes Manifest Generator and Grader")
    
    # Mode selection
    parser.add_argument("--mode", choices=["generate", "grade", "compare", "question"], 
                       default="generate", help="Operation mode")
    
    # Generation options
    parser.add_argument("--prompt", help="Natural language prompt for manifest generation")
    parser.add_argument("--backends", default="openai,gemini", 
                       help="Comma-separated list of backends to use")
    parser.add_argument("--flaw", default="none", 
                       help="Introduce flaw: none, missing-replicas, invalid-port, missing-labels, wrong-api-version")
    
    # Question generation options
    parser.add_argument("--topic", help="Kubernetes topic for question generation")
    
    parser.add_argument("--question-count", type=int, default=1, help="Number of questions to generate")
    
    # File options
    parser.add_argument("--input-file", help="Input YAML file for grading")
    parser.add_argument("--output-file", help="Output file for results")
    
    # Comparison options  
    parser.add_argument("--compare", action="store_true", help="Compare outputs between backends")
    parser.add_argument("--include-grading", action="store_true", default=True, help="Include grading in results")
    
    return parser.parse_args()

def main():
    args = parse_args()
    
    generator = ManifestGenerator()
    
    if args.mode == "question":
        # Generate questions
        print("=== Question Generation ===")
        
        filters = {}
        if args.topic:
            filters["topic"] = args.topic
        
        
        if args.question_count == 1:
            question = generator.question_generator.generate_question(**filters, use_ai=args.use_ai, ai_backend=args.ai_backend)
            print(f"Topic: {question['topic'].title()}")
            
            print(f"Question: {question['question']}")
            print(f"Success Criteria: {question['success_criteria']}")
            
            if args.prompt is None:
                args.prompt = question['question']
                print(f"\nUsing generated question as prompt for manifest generation...")
        else:
            questions = generator.question_generator.generate_question_set(args.question_count, **filters, use_ai=args.use_ai, ai_backend=args.ai_backend)
            
            for i, q in enumerate(questions, 1):
                print(f"\n{i}. [{q['topic'].title()}] {q['question']}")
            
            if args.output_file:
                generator.question_generator.save_questions_to_file(questions, args.output_file)
                print(f"\nSaved {len(questions)} questions to {args.output_file}")
            
            return
    
    if not args.prompt and not args.input_file:
        print("Error: Either --prompt or --input-file must be provided")
        return
    
    backends = args.backends.split(",")
    
    if args.mode == "generate":
        print("=== Manifest Generation ===")
        print(f"Prompt: {args.prompt}")
        print(f"Backends: {', '.join(backends)}")
        
        results = generator.run_comprehensive_test(args.prompt, backends, args.include_grading)
        
        for backend, result in results.items():
            print(f"\n--- {backend.upper()} ---")
            if result.get("error"):
                print(f"Error: {result['error']}")
                continue
            
            print(f"Validation: {'✓ Valid' if result['validation']['valid'] else '✗ Invalid'}")
            if not result['validation']['valid']:
                print(f"Error: {result['validation']['error']}")
            
            if result.get("grading") and result["grading"].get("score") is not None:
                print(f"Grade: {result['grading']['grade']} ({result['grading']['score']}/100)")
                if result['grading'].get('summary'):
                    print(f"Summary: {result['grading']['summary']}")
            
            if result.get("execution_time"):
                print(f"Time: {result['execution_time']:.2f}s")
            
            print(f"YAML Preview:")
            yaml_preview = result['yaml'][:300] + "..." if len(result['yaml']) > 300 else result['yaml']
            print(yaml_preview)
    
    elif args.mode == "grade":
        print("=== Manifest Grading ===")
        
        if args.input_file:
            with open(args.input_file, 'r') as f:
                yaml_content = f.read()
        else:
            # Generate first, then grade
            results = generator.run_comprehensive_test(args.prompt, backends[:1], False)
            yaml_content = list(results.values())[0]['yaml']
        
        grading = generator.grade_manifest(yaml_content, args.prompt or "Grade this manifest")
        
        print(f"Overall Score: {grading.get('score', 'N/A')}/100")
        print(f"Grade: {grading.get('grade', 'N/A')}")
        if grading.get('summary'):
            print(f"Summary: {grading['summary']}")
        
        if grading.get('recommendations'):
            print("\nRecommendations:")
            for rec in grading['recommendations']:
                print(f"  - {rec}")
    
    elif args.mode == "compare":
        print("=== Backend Comparison ===")
        
        results = generator.run_comprehensive_test(args.prompt, backends, args.include_grading)
        
        # Create comparison table
        print(f"\n{'Backend':<20} {'Valid':<8} {'Grade':<8} {'Score':<8} {'Time':<8}")
        print("-" * 60)
        
        for backend, result in results.items():
            valid = "✓" if result['validation']['valid'] else "✗"
            grade = result.get('grading', {}).get('grade', 'N/A')
            score = f"{result.get('grading', {}).get('score', 'N/A')}/100"
            time_str = f"{result.get('execution_time', 0):.2f}s"
            
            print(f"{backend:<20} {valid:<8} {grade:<8} {score:<8} {time_str:<8}")
        
        # Show differences if requested
        if args.compare and len(results) > 1:
            print("\n=== YAML Differences ===")
            backend_names = list(results.keys())
            
            for i in range(len(backend_names) - 1):
                backend1, backend2 = backend_names[i], backend_names[i + 1]
                yaml1 = results[backend1]['yaml'].splitlines()
                yaml2 = results[backend2]['yaml'].splitlines()
                
                diff = list(unified_diff(yaml1, yaml2, fromfile=backend1, tofile=backend2, lineterm=''))
                
                if diff:
                    print(f"\n--- Differences between {backend1} and {backend2} ---")
                    for line in diff[:20]:  # Show first 20 lines of diff
                        print(line)
    
    # Save results if requested
    if args.output_file:
        output_data = {
            "prompt": args.prompt,
            "backends": backends,
            "timestamp": time.time(),
            "results": results if args.mode != "question" else "questions generated separately"
        }
        
        with open(args.output_file, 'w') as f:
            json.dump(output_data, f, indent=2)
        
        print(f"\nResults saved to {args.output_file}")
