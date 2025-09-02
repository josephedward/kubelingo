# Kubernetes Question Generation System

A comprehensive system for generating natural language questions about Kubernetes, creating solutions using multiple AI backends, and grading solutions with hybrid static + AI evaluation.

## 🚀 Features

- **Question Generation**: Natural language questions with varying difficulty levels
- **Multiple AI Backends**: Support for OpenAI, Gemini, Grok, local LLMs, and CLI tools
- **CLI Tool Integration**: kubectl-ai, K8sGPT, KoPylot, Kube-Copilot
- **Comprehensive Grading**: Hybrid system combining static validation and AI evaluation
- **Flexible Architecture**: Modular design with pluggable components

## 📁 System Components

### Core Modules

- `question_generator.py` - Generates Kubernetes questions with varying difficulty
- `backend_integrator.py` - Manages CLI tool integrations 
- `grader.py` - Hybrid grading system (static + AI evaluation)
- `k8s_manifest_generator.py` - Main orchestrator for all backends
- `setup.py` - Installation script for all tools

### Supported Backends

**API-based:**
- OpenAI GPT-4
- Google Gemini
- xAI Grok  
- Local LLMs (Ollama)

**CLI Tools:**
- kubectl-ai (Google Cloud version)
- kubectl-ai (sozercan version)
- Kube-Copilot
- K8sGPT
- KoPylot

**Static Validation Tools:**
- kubeconform
- kube-score
- kube-linter
- checkov
- trivy

## 🛠️ Installation

### 1. Quick Setup

```bash
# Clone or download the system files
# Install Python dependencies and tools
python setup.py

# Edit .env file with your API keys
cp .env.example .env
# Edit .env and add your keys
```

### 2. Manual Installation

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install CLI tools (macOS example)
# kubectl-ai (Google)
curl -sSL https://raw.githubusercontent.com/GoogleCloudPlatform/kubectl-ai/main/install.sh | bash

# kubectl-ai (sozercan)  
brew tap sozercan/kubectl-ai https://github.com/sozercan/kubectl-ai
brew install kubectl-ai

# K8sGPT
brew tap k8sgpt-ai/tap && brew install k8sgpt

# KoPylot
pip install kopylot

# Kube-Copilot
go install github.com/feiskyer/kube-copilot/cmd/kube-copilot@latest

# Static validation tools
go install github.com/yannh/kubeconform/cmd/kubeconform@latest
brew install kube-score
go install golang.stackrox.io/kube-linter/cmd/kube-linter@latest
pip install checkov
brew install aquasecurity/trivy/trivy
```

### 3. Environment Configuration

Create `.env` file with your API keys:

```env
# AI API Keys
OPENAI_API_KEY=your_openai_key_here
GEMINI_API_KEY=your_gemini_key_here  
XAI_API_KEY=your_xai_key_here

# CLI Tool Configuration
KOPYLOT_AUTH_TOKEN=your_openai_key_here

# Local LLM Configuration
OLLAMA_HOST=http://localhost:11434
```

## 📝 Usage

### Generate Questions

```bash
# Generate single question
python k8s_manifest_generator.py --mode question --topic pods --difficulty beginner

# Generate multiple questions
python k8s_manifest_generator.py --mode question --question-count 5 --difficulty intermediate

# Save questions to file
python k8s_manifest_generator.py --mode question --question-count 10 --output-file questions.json
```

### Generate Manifests

```bash
# Single backend
python k8s_manifest_generator.py --prompt "Create nginx deployment with 3 replicas" --backends openai

# Multiple backends
python k8s_manifest_generator.py --prompt "Create nginx deployment" --backends openai,gemini,kubectl-ai-google

# Include grading
python k8s_manifest_generator.py --prompt "Create nginx pod" --backends openai,gemini --include-grading
```

### Grade Existing Manifests

```bash
# Grade YAML file
python k8s_manifest_generator.py --mode grade --input-file deployment.yaml --prompt "nginx deployment"

# Grade with specific tools
python k8s_manifest_generator.py --mode grade --input-file pod.yaml --prompt "simple pod"
```

### Compare Backends

```bash
# Compare multiple backends
python k8s_manifest_generator.py --mode compare --prompt "Create nginx service" --backends openai,gemini,kubectl-ai-google --compare
```

## 🎯 Example Workflows

### 1. CKAD Practice Session

```bash
# Generate practice questions
python k8s_manifest_generator.py --mode question --difficulty intermediate --question-count 5 --output-file ckad_practice.json

# For each question, generate solutions with multiple backends
python k8s_manifest_generator.py --prompt "Create a Pod with resource limits" --backends openai,gemini,kubectl-ai-google --mode compare --include-grading
```

### 2. Backend Evaluation

```bash
# Test all available backends
python k8s_manifest_generator.py --prompt "Deploy scalable web application" --backends openai,gemini,grok,kubectl-ai-google,k8sgpt --mode compare --include-grading --output-file backend_comparison.json
```

### 3. Solution Grading Pipeline

```python
from question_generator import QuestionGenerator
from k8s_manifest_generator import ManifestGenerator

# Generate question
generator = QuestionGenerator()
question = generator.generate_question(topic="deployments", difficulty="advanced")

# Generate solution
manifest_gen = ManifestGenerator()
results = manifest_gen.run_comprehensive_test(question['question'], ['openai'], include_grading=True)

# Review grading
grading = results['openai']['grading']
print(f"Grade: {grading['grade']} ({grading['score']}/100)")
print(f"Recommendations: {grading['recommendations']}")
```

## 🔧 Customization

### Adding New Backends

1. **API-based backend**: Add method to `ManifestGenerator` class
2. **CLI tool**: Add configuration to `BackendIntegrator` class
3. **Static validator**: Add tool config to `StaticValidator` class

### Custom Question Types

Edit `question_generator.py` to add:
- New topics in `KubernetesTopics` enum
- New templates in `_init_question_templates()`
- Custom context variables

### Grading Criteria

Modify `grader.py` to:
- Add custom static validation tools
- Customize AI evaluation prompts  
- Adjust scoring weights

## 🧪 Testing

```bash
# Verify installation
python setup.py --verify-only

# Test question generation
python question_generator.py

# Test backend integration
python backend_integrator.py

# Test grading system
python grader.py

# Full system test
python k8s_manifest_generator.py --mode question --question-count 1
```

## 📊 Output Examples

### Question Generation Output

```json
{
  "id": "a1b2c3d4",
  "topic": "deployments", 
  "difficulty": "intermediate",
  "question": "Create a Deployment named 'web-deployment' with 3 replicas running 'nginx:1.21' image",
  "success_criteria": [
    "YAML syntax is valid",
    "Deployment resource is properly defined", 
    "Replica count is set to 3"
  ],
  "expected_resources": ["Deployment"]
}
```

### Grading Output

```json
{
  "overall_score": 85,
  "final_grade": "B",
  "summary": "Static validation passed: kubeconform, kube-score. AI evaluation: 90/100 (confidence: high)",
  "recommendations": [
    "[kube-linter] Add resource requests and limits",
    "[AI] Consider adding readiness probes",
    "[AI] Use more specific image tags"
  ]
}
```

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Google Cloud kubectl-ai team
- sozercan kubectl-ai project
- K8sGPT community
- KoPylot developers
- Kube-Copilot maintainers
- All static validation tool maintainers