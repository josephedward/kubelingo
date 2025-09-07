## Kubernetes Question Generation System

I've created a comprehensive system that generates Kubernetes questions, creates solutions using various AI tools, and grades them with both static checkers and AI evaluation. Here's what I've built for you:

### System Architecture

**Core Components:**
1. **Question Generator** - Creates natural language Kubernetes questions with varying difficulty levels
2. **Backend Integrator** - Manages integration with multiple AI CLI tools
3. **Grader** - Hybrid grading system combining static validation and AI evaluation
4. **Main Generator** - Orchestrates everything together
5. **Setup Script** - Automated installation of all tools

### Supported AI Backends

**API-based:**[1][2][3][4][5]
- OpenAI GPT-4
- Google Gemini 
- xAI Grok
- Local LLMs (Ollama)

**CLI Tools:**[2][3][6][7][8][9]
- **kubectl-ai (Google Cloud)** - Google's AI-powered kubectl assistant
- **kubectl-ai (sozercan)** - Alternative kubectl-ai implementation
- **Kube-Copilot** - AI assistant for Kubernetes operations and diagnostics
- **K8sGPT** - AI-powered cluster analysis and troubleshooting tool
- **KoPylot** - AI-powered Kubernetes assistant for developers

**Static Validation Tools:**[10][11][12][1]
- **kubeconform** - Fast Kubernetes manifest validation against OpenAPI schemas
- **kube-score** - Best practices and security checks
- **kube-linter** - Reliability and security linting
- **checkov** - Infrastructure as code security scanning
- **trivy** - Security vulnerability scanner

### Key Features

**Flexible Question Generation:**
- Multiple difficulty levels (beginner, intermediate, advanced, expert)
- Various Kubernetes topics (pods, deployments, services, security, etc.)
- Realistic scenarios with context variables
- Success criteria and hints for complex questions

**Comprehensive Grading:**
- **Static validation** using multiple CLI tools for syntax, schema compliance, and best practices
- **AI evaluation** for semantic correctness and goal achievement
- **Hybrid scoring** that balances rigid validation with flexible assessment
- Handles variations, aliases, and indentation inconsistencies

**Backend Orchestration:**
- Automatic detection of available tools
- Environment variable management
- Error handling and fallbacks
- Performance comparison between backends

### Usage Examples

**Generate Questions:**
```bash
python k8s_manifest_generator.py --mode question --topic deployments --difficulty intermediate
```

**Generate and Grade Solutions:**
```bash
python k8s_manifest_generator.py --prompt "Create nginx deployment with 3 replicas" --backends openai,gemini,kubectl-ai-google --include-grading
```

**Compare Multiple Backends:**
```bash
python k8s_manifest_generator.py --mode compare --prompt "Create scalable web service" --backends openai,k8sgpt,kube-copilot --compare
```

### Installation

The system includes an automated setup script that:
- Installs Python dependencies
- Downloads and configures CLI tools based on your platform[3][6][13][14][2]
- Sets up environment variables
- Verifies installations

### Advanced Features

**Maximally Flexible Grading:**
- Handles YAML formatting variations and aliases
- Semantic evaluation beyond syntax checking
- Goal-relative scoring that considers effectiveness
- Confidence scoring for AI evaluations
- Actionable recommendations for improvements

**Educational Focus:**
- Perfect for CKAD exam preparation
- Progressive difficulty levels
- Detailed explanations and hints
- Comprehensive feedback on solutions

The system is designed to be modular and extensible - you can easily add new backends, customize grading criteria, or modify question templates. It provides a complete solution for automated Kubernetes education and assessment.

[1](https://www.wiz.io/academy/kubeconform-overview)
[2](https://www.yeschat.ai/gpts-2OToldJMG4-YAML-Code-Generator)
[3](https://www.rutvikbhatt.com/kubernetes-made-easy-googles-kubectl-ai-with-ai-powered-commands/)
[4](https://github.com/yannh/kubeconform)
[5](https://workik.com/kubernetes-yaml-generator)
[6](https://kodekloud.com/blog/no-more-kubectl-commands/)
[7](https://codefresh.io/learn/kubernetes-management/kubernetes-tools/)
[8](https://workik.com/ai-powered-cloudformation-yaml-template-generator)
[9](https://www.linkedin.com/pulse/getting-started-kubectl-ai-step-by-step-guide-ahmed-jadelrab-57k9f)
[10](https://spacelift.io/blog/kubernetes-security-tools)
[11](https://sourceforge.net/software/ai-tools/integrates-with-yaml/)
[12](https://www.virtualizationhowto.com/2025/05/meet-kubectl-ai-google-just-delivered-the-best-tool-for-kubernetes-management/)
[13](https://community.home-assistant.io/t/any-ai-that-can-help-me-out-with-creating-good-yaml/748020?page=2)
[14](https://formulae.brew.sh/formula/kubectl-ai)
[15](https://aws.amazon.com/blogs/machine-learning/use-k8sgpt-and-amazon-bedrock-for-simplified-kubernetes-cluster-maintenance/)
[16](https://kubetools.io/top-5-ai-tools-for-kubernetes-cluster-management/)
[17](https://github.com/feiskyer/kube-copilot)
[18](https://www.youtube.com/watch?v=J4LJsXTEvw8)
[19](https://seifrajhi.github.io/blog/ai-and-kubernetes/)
[20](https://botkube.io/learn/kubernetes-copilot)
[21](https://collabnix.com/k8sgpt-cheatsheet-2025/)
[22](https://github.com/avsthiago/kopylot)
[23](https://k8studio.io/features/copilot/)
[24](https://www.linkedin.com/pulse/installing-k8sgpt-various-operating-systems-part-2-prashant-lakhera-t9q2c)
[25](https://awstrainingwithjagan.com/ai-tools-for-kubernetes/)
[26](https://testkube.io/blog/introducing-testkube-copilot-ai-powered-assistant-for-test-orchestration)
[27](https://codefresh.io/learn/kubernetes-management/k8sgpt-the-basics-and-a-quick-tutorial/)
[28](https://collabnix.com/kubernetes-and-ai-3-open-source-tools-powered-by-openai/)