# Kubernetes CKAD Question Generator

## Overview

This project helps you create a script that finds valid Kubernetes commands and manifests to generate CKAD (Certified Kubernetes Application Developer) style questions. The approach combines free resources, web scraping, and AI-powered question generation.

## Free Resources Available

## Local Setup and Usage

Prerequisites:
  - Python 3.7 or newer
  - pip

1) (Optional) Create and activate a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
2) Install required dependencies:
   ```bash
   python3 -m pip install -r requirements.txt
   ```
3) Run the question generator script:
   ```bash
   python3 k8s_quesion_generator.py --mode both --count 50 --output questions.json
   ```

If you encounter `ModuleNotFoundError: No module named 'bs4'`, ensure that you installed `beautifulsoup4` into the same Python interpreter you are using to run the script (e.g. via `python3 -m pip install beautifulsoup4`).

### 1. Official Kubernetes Documentation
- **kubectl Cheat Sheet**: https://kubernetes.io/docs/reference/kubectl/cheatsheet/
- **Official Examples**: https://github.com/kubernetes/examples
- **API Reference**: https://kubernetes.io/docs/reference/

### 2. Community Repositories
- **Container Solutions Examples**: https://github.com/ContainerSolutions/kubernetes-examples
- **Denny Zhang Templates**: https://github.com/dennyzhang/kubernetes-yaml-templates
- **CKAD Exercises**: https://github.com/dgkanatsios/CKAD-exercises

### 3. Free Training Resources
- **CNCF Training**: Free Introduction to Kubernetes course
- **Linux Foundation**: LFD259 (often has free access periods)
- **Katacoda/Killercoda**: Interactive Kubernetes scenarios
- **Kubernetes Academy**: Free video tutorials

## Cost Analysis

### Free Options (No Cost)
1. **Web Scraping**: Use requests/BeautifulSoup to scrape public repos
2. **GitHub API**: Free tier allows 5,000 requests/hour
3. **Local Processing**: Parse YAML files locally
4. **Template-based Generation**: Use predefined question templates

### Low-Cost Options ($5-50/month)
1. **OpenAI API**: ~$0.002 per 1K tokens for GPT-3.5
2. **GitHub Copilot**: $10/month (includes API access)
3. **Anthropic Claude**: Similar pricing to OpenAI

### Expensive Options ($100+/month)
1. **Specialized AI Training Platforms**: Testkube Pro, etc.
2. **Enterprise LLM APIs**: GPT-4, Claude Pro
3. **Custom ML Model Training**: Significant compute costs

## Implementation Approaches

### Approach 1: Free Scraping + Template Generation
```python
# Scrape free resources
def scrape_k8s_resources():
    # Get kubectl commands from official docs
    # Parse YAML manifests from GitHub repos
    # Extract common patterns

# Generate questions using templates
def generate_questions():
    # Use predefined question templates
    # Fill in parameters from scraped resources
    # Create variations automatically
```

**Pros**: Completely free, no API costs, works offline
**Cons**: Limited question variety, requires manual template creation

### Approach 2: Hybrid (Free + Low-Cost AI)
```python
# Use free scraping + AI for question generation
def ai_enhanced_generation():
    # Scrape resources for free
    # Use AI API for creative question generation
    # Validate with free tools
```

**Pros**: Higher quality questions, more variety
**Cons**: Small API costs (~$5-20/month)

### Approach 3: Fully Automated AI Pipeline
```python
# Let AI handle everything
def full_ai_pipeline():
    # AI scrapes and analyzes resources
    # AI generates contextual questions
    # AI validates and ranks questions
```

**Pros**: Highest quality, minimal manual work
**Cons**: Higher costs ($50-200/month)

## Recommended Free Implementation

### Step 1: Resource Collection
```bash
# Clone key repositories
git clone https://github.com/kubernetes/examples.git
git clone https://github.com/ContainerSolutions/kubernetes-examples.git
git clone https://github.com/dgkanatsios/CKAD-exercises.git

# Scrape official documentation
curl -s https://kubernetes.io/docs/reference/kubectl/cheatsheet/ > kubectl_commands.html
```

### Step 2: Content Parsing
```python
import yaml
import os
import re

def parse_yaml_files(directory):
    manifests = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(('.yaml', '.yml')):
                with open(os.path.join(root, file), 'r') as f:
                    try:
                        content = yaml.safe_load(f)
                        manifests.append(content)
                    except yaml.YAMLError:
                        pass
    return manifests
```

### Step 3: Question Generation Templates
```python
QUESTION_TEMPLATES = {
    'pod': [
        "Create a pod named {name} using image {image}",
        "Create a pod that runs {image} and exposes port {port}",
        "Create a pod with resource limits: CPU {cpu}, Memory {memory}"
    ],
    'deployment': [
        "Create a deployment with {replicas} replicas using {image}",
        "Scale deployment {name} to {replicas} replicas",
        "Update deployment {name} to use image {new_image}"
    ],
    'service': [
        "Expose deployment {name} as a {type} service on port {port}",
        "Create a service that selects pods with label {label}={value}"
    ]
}
```

## Advanced Features (Optional Costs)

### AI-Powered Question Enhancement
If you want to use AI for better questions:

```python
import openai

def enhance_questions_with_ai(basic_questions, budget_limit=10):
    enhanced = []
    cost = 0

    for question in basic_questions:
        if cost > budget_limit:
            break

        response = openai.Completion.create(
            model="gpt-3.5-turbo",
            prompt=f"Improve this CKAD question: {question}",
            max_tokens=100
        )

        enhanced.append(response.choices[0].text.strip())
        cost += 0.002  # Approximate cost per request

    return enhanced, cost
```

### Validation Tools (Free)
```python
# Validate generated manifests
def validate_k8s_manifest(manifest):
    # Use kubectl dry-run
    import subprocess

    try:
        result = subprocess.run([
            'kubectl', 'apply', '--dry-run=client', 
            '--validate=true', '-f', '-'
        ], input=yaml.dump(manifest), text=True, 
           capture_output=True, check=True)
        return True, "Valid"
    except subprocess.CalledProcessError as e:
        return False, e.stderr
```

## Boundary Considerations

### What Overlaps Between Concepts

1. **Pod vs Deployment**: Pods are basic units, Deployments manage pods
2. **Service vs Ingress**: Services expose within cluster, Ingress handles external access
3. **ConfigMap vs Secret**: Both store configuration, Secrets are encoded
4. **Namespace vs Context**: Namespaces isolate resources, contexts switch clusters

### Question Categories to Generate

1. **Resource Creation** (kubectl create, apply)
2. **Resource Querying** (kubectl get, describe)
3. **Resource Modification** (kubectl edit, patch, scale)
4. **Troubleshooting** (kubectl logs, exec, debug)
5. **Configuration** (ConfigMaps, Secrets, environment variables)

## Usage Examples

### Basic Usage (Free)
```bash
# Install dependencies
pip install requests beautifulsoup4 pyyaml

# Run the generator
python k8s_question_generator.py --mode both --count 100 --output ckad_questions.json
```

### With AI Enhancement (Low Cost)
```bash
# Set API key
export OPENAI_API_KEY="your-key-here"

# Run with AI enhancement
python k8s_question_generator.py --mode both --ai-enhance --budget 5.00
```

### Validation Mode
```bash
# Validate all generated manifests
python k8s_question_generator.py --mode validate --input ckad_questions.json
```

## Expected Costs Summary

| Approach | Initial Setup | Monthly Cost | Quality Score |
|----------|--------------|--------------|---------------|
| Free Scraping | 0 | $0 | 7/10 |
| Hybrid (AI Enhanced) | 0 | $5-20 | 9/10 |
| Full AI Pipeline | 0 | $50-200 | 10/10 |

## Getting Started Recommendation

1. **Start Free**: Use the provided script to scrape and generate basic questions
2. **Test Quality**: See if the free approach meets your needs
3. **Enhance Gradually**: Add AI features if you need higher quality
4. **Monitor Costs**: Set budget limits for AI API usage

The free approach should give you hundreds of valid CKAD-style questions, which is often sufficient for practice and learning.
