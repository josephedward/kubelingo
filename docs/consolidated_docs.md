---
/Users/user/Documents/GitHub/kubelingo/docs/shared_context.md:
---

# Shared Context for Kubelingo CLI Agents

This document describes the current workflow and design constraints for all Kubelingo
CLI subcomponents (UI, generator, validation, tools integrations). It ensures a common
understanding for future changes.

1. Topics Selection
   - Menu shows topics with stats; prompt suffix allows:
     * i: study incomplete questions
     * g: generate a new question (requires 100% completion & API key)
     * s: search/generate a new question (alias of g when no mapping)
     * b: go back to topic selection
     * Enter: study all questions
   - Input handling:
     'i': set of incomplete questions
     'g' or 's': invoke question_generator.generate_more_questions(topic)
     <digit>: study specified number of questions
     default: study all questions

2. Manifest-only Generation
   - Scrape the first <pre> or <code> YAML block from documentation HTML
   - Construct a question dict:
     ```yaml
     question: "Provide the Kubernetes YAML manifest example from the documentation at <URL>"
     suggestion: |   # multi-line YAML snippet
       apiVersion: ...
       kind: ...
     source: "<URL>"
     rationale: "Example manifest for '<topic>' as shown in the official docs."
     ```
   - No LLM fallback: if no snippet found, generation returns `None`.

3. Study Session Flow (run_topic)
   - Display question text once and:
     * For manifest questions: auto-show the suggestion on first view, skip user input loop,
       update performance, then show post-answer menu: [n]ext, [b]ack, [i]ssue, [s]ource, [r]etry, [c]onfigure, [q]uit.
     * For command questions: prompt via `get_user_input()`, validate with kubectl dry-run or AI (if enabled).

4. Tools Integration
   - `kubectl create --dry-run=client -o yaml` for manifest stubs
   - `yq`, `jq` for YAML/JSON manipulation
   - `kube-score` or `kubeconform` for schema validation
   - `trivy` for security scans
   - `jsonnet` for advanced templating (docs/tools branch)

_End of shared context._

---
/Users/user/Documents/GitHub/kubelingo/docs/roadmap.md:
---

# Kubelingo ML Roadmap

This document outlines potential ideas for incorporating machine learning into Kubelingo to create a more personalized and effective learning experience. The ideas are organized by increasing complexity.

### Idea 1: Adaptive Question Selection with Topic Weighting (Low Complexity)

*   **Concept:** The system learns which CKAD topics (e.g., "Core Workloads," "Services," "Persistence") are the user's weakest and prioritizes questions from those areas. The goal is to ensure a user's knowledge is balanced and they don't just over-practice what they already know.
*   **How it could work:**
    1.  **Data Tracking:** The `user_data/performance.yaml` file would track correct/incorrect answers for each question, and each question is already categorized by its source file (e.g., `services.yaml`).
    2.  **ML Model (Simple Algorithm):** This isn't "deep learning" but a classic learning algorithm. Maintain a "mastery score" for each topic (e.g., `services: 0.9`, `persistence: 0.4`).
    3.  **Question Selection:** When selecting a new question, instead of picking a topic randomly, use the inverse of the mastery scores as weights. Topics with lower scores (e.g., `persistence` at 40%) have a much higher probability of being chosen.
    4.  **Decay/Diversity:** To prevent the system from getting stuck on one topic, a decay factor could be added. The weight of a topic is slightly reduced each time it's presented, ensuring other topics eventually surface.

### Idea 2: Dynamic Difficulty Scaling within Topics (Medium Complexity)

*   **Concept:** Within a single topic, questions have varying levels of difficulty. The system learns the user's proficiency and presents them with questions that are appropriately challenging, progressing from simple commands to complex multi-resource manifests.
*   **How it could work:**
    1.  **Data Annotation:** Each question in the YAML files would be manually annotated with a difficulty rating (e.g., `difficulty: easy` or `difficulty: 3`). `easy` could be a `kubectl run` command, while `hard` could be a `Deployment` with affinity rules and a `Service` manifest.
    2.  **User Skill Model:** The system maintains a "skill rating" for the user, possibly for each topic. This could be a simple numerical score.
    3.  **Progression Logic:** When a user correctly answers a question of a certain difficulty, their skill rating increases, and the system is more likely to serve a question of the same or next-highest difficulty. If they fail, the rating decreases, and they are presented with an easier question to reinforce fundamentals. This is a simplified application of concepts from Item Response Theory (IRT).

### Idea 3: Common Error Pattern Recognition and Hinting (Medium-High Complexity)

*   **Concept:** The system analyzes a user's incorrect answers (both commands and manifests) to identify common patterns of mistakes and provide specific, actionable hints.
*   **How it could work:**
    1.  **Data Collection:** Store incorrect user-submitted YAML or command strings.
    2.  **Pattern Analysis (Rule-Based to ML):**
        *   **Simple:** Use `diff` between the user's submission and the solution. If the diff is only in the `apiVersion` field, the hint could be: "Hint: Check the `apiVersion`. `apps/v1` is common for Deployments."
        *   **Advanced (ML):** Use techniques like clustering on embeddings of incorrect answers. For example, many users might incorrectly use `port` instead of `targetPort` in a Service manifest. These incorrect manifests would form a "cluster." When a new answer falls into this cluster, the system provides the targeted hint associated with it.

### Idea 4: Conceptual Gap Analysis via Embeddings (High Complexity)

*   **Concept:** This moves beyond topic labels and analyzes the underlying *Kubernetes concepts* a user struggles with. For example, a user might fail questions across "Core Workloads," "Scheduling," and "Security" that all involve `labels` and `selectors`. The system would identify "labeling and selection" as the core conceptual weakness.
*   **How it could work:**
    1.  **Embedding Generation:** Use a code-aware language model (e.g., a BERT variant) to generate a vector embedding for every question's solution manifest in your library. These embeddings represent the "meaning" of the manifest.
    2.  **User Profile:** When a user fails a question, add its embedding to a "failure profile" for that user.
    3.  **Analysis:** Periodically, run a clustering algorithm (e.g., UMAP for visualization, HDBSCAN for analysis) on the user's failure profile. The resulting clusters represent the conceptual areas of weakness.
    4.  **Targeted Learning:** The system can then report this to the user ("You seem to be struggling with resource attachment and selectors") and create a study session with questions pulled specifically from that conceptual cluster.

### Idea 5: Generative Question Augmentation (Very High Complexity)

*   **Concept:** The ultimate step in personalization. The system uses a generative AI model to create entirely new, unique questions that are precisely tailored to fill a user's identified knowledge gaps.
*   **How it could work:**
    1.  **Model Fine-Tuning:** Fine-tune a powerful Large Language Model (LLM) on your existing library of questions. The model learns the structure, style, and components of a good `kubelingo` question (scenario, task, solution manifest, validation commands).
    2.  **Targeted Prompting:** Using the output from Idea #4, the system would prompt the fine-tuned LLM. For example: "Generate a new, medium-difficulty question for Kubelingo. The scenario must involve a Deployment and a PersistentVolumeClaim. The core concept to test is mounting a volume into a specific `subPath` in the container."
    3.  **Generation and Validation:** The LLM would generate the full question YAML. A critical and difficult final step would be a robust validation pipeline to ensure the generated manifest is syntactically correct, deployable, and that the validation commands work as expected.

### How to Roll This Out

    1. **Sandbox & branch**
       – Create a feature branch `ai-integration`
    2. **Phase 0 → Phase 1**
       – Normalize static questions, write tests, merge once green.
    3. **Phase 2**
       – Build the converter, test it, merge behind a feature flag (`--enable-ai-bridge`).
    4. **Phase 3 → Phase 4**
       – Gradually add CLI flags `--source ai`, `ask-ai` commands, behind flags.
    5. **Phase 5**
       – Offer `solve --method ai` as experimental.
    6. **Phase 6**
       – Turn on E2E dashboards for instructors.

At each merge, your full test suite (static + AI mock tests) must pass.  AI calls are always shimmable via fixtures or fake scripts, so CI never depends on actual OpenAI—only your smoke tests will.

—
That roadmap will let you keep your static backbone intact, iteratively layer AI on top, allow full offline operation, and unlock the rich generative, grading & analytics capabilities of the new system.

---
/Users/user/Documents/GitHub/kubelingo/docs/question_generation_tools.md:
---

# Kubernetes Question Generation Tools Guide

## Core Validation Tools

### kube-score
```bash
# Basic usage for question validation
kube-score score question.yaml

# Example output for validation failures
kube-score score -o human question.yaml | grep FAIL
```

### yq/jq
```bash
# Extract metadata from question YAML
yq eval '.metadata' question.yaml

# Convert YAML to JSON for processing
yq eval -o json question.yaml | jq '.spec'

# Modify existing YAML
yq eval '.spec.replicas = 3' question.yaml -i
```

### Trivy
```bash 
# Security scan a question manifest
trivy config --severity HIGH,CRITICAL question.yaml

# Output JSON results for processing
trivy config -f json -o results.json question.yaml
```

## Advanced Templating

### Jsonnet Example
```jsonnet
// deployment.jsonnet
local kube = import 'kube.libsonnet';

{
  deployment: kube.Deployment('my-app') {
    spec: {
      replicas: 3,
      template: {
        spec: {
          containers: [
            kube.Container('app') {
              image: 'nginx:stable',
              ports: [{containerPort: 80}]
            }
          ]
        }
      }
    }
  }
}
```

```bash
# Generate YAML from Jsonnet
jsonnet -m outputs deployment.jsonnet
```

## Validation Workflow

1. Create initial question with kubectl:
```bash
kubectl create deployment my-app --image=nginx --dry-run=client -o yaml > question.yaml
```

2. Add complexity with yq:
```bash
yq eval '.spec.template.spec.containers[0].resources = {"limits": {"cpu": "100m"}}' -i question.yaml
```

3. Validate with kube-score:
```bash
kube-score score question.yaml
```

4. Security scan with Trivy:
```bash
trivy config --severity HIGH,CRITICAL question.yaml
```

5. Generate final output with Jsonnet:
```bash
jsonnet -y -m final_questions generated_question.jsonnet
```

---
/Users/user/Documents/GitHub/kubelingo/docs/search.md:
---

# Search-Based Options for Kubernetes Quiz Material

You're absolutely right to focus on search first - there are extensive repositories of already-vetted Kubernetes manifests and practice questions that would be much more reliable than generating synthetic content. Here are your comprehensive options:

## 1. Official Kubernetes Resources

### Official Kubernetes Examples Repository
The **kubernetes/examples** repository is the gold standard maintained by SIG Apps. It contains:[1]
- High-quality, educational examples for diverse use cases
- AI/ML workloads, general applications, and specialized configurations
- Each example includes detailed documentation with prerequisites and step-by-step instructions
- Organized by categories with proper README files
- **6.4k stars, actively maintained**

### Official Kubernetes Documentation
The **kubernetes.io/docs/tutorials** section provides:[2]
- Interactive tutorials with working examples
- Configuration examples for pods, services, deployments
- Stateful and stateless application examples
- Security and cluster management examples

## 2. Curated Manifest Collections

### Container Solutions Examples
The **kubernetes-examples** repository by Container Solutions offers:[3]
- Minimal, self-contained YAML demonstrations
- Searchable front-end at k8s-examples.container-solutions.com
- Organized by resource types (Pod, Service, Deployment, etc.)
- **kubectl plugin integration** for easy access
- Examples organized by YAML paths (e.g., `Pod/spec.initContainers/`)
- **1.4k stars, MIT licensed**

### Kubernetes Patterns Examples
The **k8spatterns/examples** repository provides:[4]
- Examples from the "Kubernetes Patterns" book
- Reusable elements for cloud-native applications
- Updated for Kubernetes 1.26
- Comprehensive patterns with detailed explanations

### DigitalOcean Sample Apps
The **kubernetes-sample-apps** repository contains:[5]
- Real-world application examples (bookinfo, emojivoto, 2048 game)
- Complete deployment configurations
- Load balancer and service exposure examples
- **296 stars, actively maintained**

## 3. Practice Question Repositories

### CKAD Exercises (Most Popular)
The **dgkanatsios/CKAD-exercises** repository is the gold standard:[6]
- **9.5k stars** - most popular CKAD practice repo
- Organized by curriculum domains (13% Core Concepts, 20% Pod Design, etc.)
- Real exam-style questions with solutions
- Continuously updated by community
- Covers all CKAD exam topics comprehensively

### CKA Practice Exercises
The **alijahnas/CKA-practice-exercises** repository provides:[7]
- 24 practical problems matching real CKA exam format
- Multi-cluster scenarios
- Troubleshooting exercises
- References to "Kubernetes the Hard Way"

### Kubernetes Security Mock Exam
The **kubernetes-security-kcsa-mock** repository offers:[8]
- **290+ questions** for KCSA certification
- Domain-specific categorization
- AI-powered question improvements
- Interactive web application format
- Community-driven error reporting system

## 4. Implementation Strategy for Search

### Repository Structure Analysis
You can systematically crawl these repositories using their predictable structures:

```python
# Target repositories with their organizational patterns
repos = {
    "kubernetes/examples": "examples/*",
    "ContainerSolutions/kubernetes-examples": "*/",
    "dgkanatsios/CKAD-exercises": "*/",
    "kubernetes/sample-controller": "artifacts/examples/",
    "digitalocean/kubernetes-sample-apps": "*/",
}

# Common patterns to search for
manifest_patterns = [
    "*.yaml", "*.yml",
    "deployment.yaml", "service.yaml", "pod.yaml",
    "configmap.yaml", "secret.yaml", "ingress.yaml"
]
```

### GitHub API Integration
Use GitHub's Tree API to systematically traverse repositories:[9]

```python
import requests

def get_repo_tree(owner, repo, branch="main"):
    url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
    response = requests.get(url)
    return response.json()

def filter_yaml_files(tree_data):
    yaml_files = []
    for item in tree_data.get("tree", []):
        if item["path"].endswith((".yaml", ".yml")) and item["type"] == "blob":
            yaml_files.append({
                "path": item["path"], 
                "url": item["url"],
                "raw_url": f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{item['path']}"
            })
    return yaml_files
```

### Content Validation Strategy
Implement validation to ensure quality manifests:

```python
import yaml

def validate_kubernetes_manifest(content):
    """Validate if content is a proper Kubernetes manifest"""
    try:
        manifest = yaml.safe_load(content)
        required_fields = ["apiVersion", "kind"]
        
        if not all(field in manifest for field in required_fields):
            return False
            
        # Check for common Kubernetes kinds
        valid_kinds = [
            "Pod", "Deployment", "Service", "ConfigMap", 
            "Secret", "Ingress", "Job", "CronJob", "DaemonSet"
        ]
        
        return manifest.get("kind") in valid_kinds
    except yaml.YAMLError:
        return False
```

## 5. Practice Question Extraction

### Question Format Recognition
Most practice repositories follow consistent patterns:

```python
def extract_questions(readme_content):
    """Extract questions from README files"""
    import re
    
    # Common question patterns
    patterns = [
        r"^\d+\.\s+(.+?)(?=\n\d+\.|\n##|\n\*\*|\Z)",  # Numbered questions
        r"^##\s+(.+?)(?=\n##|\Z)",  # Header-based questions
        r"^\*\*(.+?)\*\*",  # Bold questions
    ]
    
    questions = []
    for pattern in patterns:
        matches = re.findall(pattern, readme_content, re.MULTILINE | re.DOTALL)
        questions.extend(matches)
    
    return questions
```

### Metadata Extraction
Extract valuable metadata from repositories:

```python
def extract_manifest_metadata(manifest_content):
    """Extract metadata for quiz generation"""
    manifest = yaml.safe_load(manifest_content)
    
    return {
        "kind": manifest.get("kind"),
        "apiVersion": manifest.get("apiVersion"),
        "name": manifest.get("metadata", {}).get("name"),
        "namespace": manifest.get("metadata", {}).get("namespace"),
        "labels": manifest.get("metadata", {}).get("labels", {})
        "spec_keys": list(manifest.get("spec", {}).keys()) if manifest.get("spec") else [],
        "complexity": calculate_complexity(manifest)
    }

def calculate_complexity(manifest):
    """Simple complexity scoring based on manifest structure"""
    spec = manifest.get("spec", {})
    complexity_score = 0
    
    # Count nested levels, containers, volumes, etc.
    if "containers" in spec:
        complexity_score += len(spec["containers"])
    if "volumes" in spec:
        complexity_score += len(spec["volumes"])
    if "rules" in spec:  # NetworkPolicy, RBAC
        complexity_score += len(spec["rules"])
        
    return complexity_score
```

## 6. Recommended Implementation Priority

1. **Start with dgkanatsios/CKAD-exercises** - 9.5k stars, comprehensive coverage[6]
2. **Add ContainerSolutions/kubernetes-examples** - systematic YAML collection[3]
3. **Include kubernetes/examples** - official, high-quality examples[1]
4. **Extend to specialized repos** - security, CKA, etc.

This search-first approach gives you access to **thousands of vetted manifests and practice questions** without any AI dependencies, ensuring accuracy and real-world relevance for CKAD exam preparation.

[1](https://github.com/kubernetes/examples)
[2](https://kubernetes.io/docs/tutorials/)
[3](https://github.com/ContainerSolutions/kubernetes-examples)
[4](https://github.com/k8spatterns/examples)
[5](https://github.com/digitalocean/kubernetes-sample-apps)
[6](https://github.com/dgkanatsios/CKAD-exercises)
[7](https://github.com/alijahnas/CKA-practice-exercises)
[8](https://github.com/thiago4go/kubernetes-security-kcsa-mock)
[9](https://stackoverflow.com/questions/75522166/how-do-i-get-the-directory-tree-structure-from-a-github-repository-link)
[10](https://www.youtube.com/watch?v=p_g-zxZ0eL0)
[11](https://www.reddit.com/r/kubernetes/comments/1drv4l0/kubernetes_knowledge_check_test_me_with_your/)
[12](https://matthewpalmer.net/kubernetes-app-developer/articles/ckad-practice-exam.html)
[13](https://dev.to/coherentlogic/answers-to-five-kubernetes-ckad-practice-questions-2020-3h0p)
[14](https://sailor.sh)
[15](https://www.reddit.com/r/kubernetes/comments/12s5rxf/how_to_practice_real_exam_questions_for_ckad/)
[16](https://www.testdome.com/tests/kubernetes-online-test/176)
[17](https://github.com/Devinterview-io/kubernetes-interview-questions)
[18](https://www.reddit.com/r/kubernetes/comments/gldbkk/cka_exam_good_exercisemock_exam_resources/)
[19](https://github.com/topics/kubernetes-questions)
[20](https://monokle.io/learn/kubernetes-manifest-files-explained)
[21](https://www.reddit.com/r/kubernetes/comments/ss853z/fastkubernetes_kubernetes_tutorial_sample_usage/)
[22](https://github.com/observeinc/manifests)
[23](https://dev.to/francescoxx/kubernetes-quick-tutorial-2el7)
[24](https://github.com/kubernetes/sample-controller)
[25](https://www.reddit.com/r/kubernetes/comments/13zak98/easy_way_to_create_kubernetes_manifests_in_github/)
[26](https://spacelift.io/blog/kubernetes-manifest-file)
[27](https://kubernetes.io/docs/tutorials/kubernetes-basics/)
[28](https://github.com/maximemoreillon/kubernetes-manifests)
[29](https://fluxcd.io/flux/guides/repository-structure/)
[30](https://spacelift.io/blog/kubernetes-deployment-yaml)
[31](https://stackoverflow.com/questions/23989232/is-there-a-way-to-represent-a-directory-tree-in-a-github-readme-md)
[32](https://developers.redhat.com/articles/2022/09/07/how-set-your-gitops-directory-structure)
[33](https://www.pulumi.com/registry/packages/kubernetes/api-docs/kustomize/v2/directory/)
[34](https://www.mirantis.com/blog/gitops-repository-patterns-part-6-examples/)
[35](https://www.mirantis.com/blog/introduction-to-yaml-creating-a-kubernetes-deployment/)

---
/Users/user/Documents/GitHub/kubelingo/docs/ai-integration-roadmap.md:
---

Here’s a multi-phase roadmap for folding the AI question/manifest generator on top of your existing static engine, while preserving 100% offline/static capability and incrementally adding AI “power‐ups.”  At each phase you’ll get:

  • Objectives
  • Manual steps & example commands
  • What you can do / cannot do yet
  • Skeleton tests you’ll write to lock in correctness

—

## Phase 0: Define & Lock Down Your Canonical Question Schema

Before you touch code, make sure you have a single “question” schema (fields, names, types) that both static YAML and AI JSON will map to.  E.g.:

  • id
  • topic
  • difficulty
  • question
  • expected_resources
  • success_criteria
  • hints
  • scenario_context

Manual

    1. Inspect a few of your existing `/kubelingo/questions/*.yaml` files.  Pick a representative subset.
    2. Document their fields in `docs/question-schema.md`.
    3. Take one of the AI outputs you’ve already generated, dump it to JSON, compare.

Can / Cannot
  • CAN: Agree on canonical field names and types.
  • CANNOT: Import yet—this is purely a design doc exercise.

Tests
  Create tests/phase0/test_schema_consistency.py that

    import yaml, json, pytest

    def test_static_question_has_required_fields():
        q = yaml.safe_load(open("kubelingo/questions/example.yaml"))
        for fld in ("id","topic","difficulty","question","expected_resources","success_criteria"):
            assert fld in q

    def test_ai_question_has_same_fields():
        aiq = json.load(open("scripts/.../sample_questions.json"))[0]
        for fld in ("id","topic","difficulty","question","expected_resources","success_criteria"):
            assert fld in aiq

—

## Phase 1: Normalize All Static Questions to Canonical Schema

Objectives
  • Collapse every static question file into the same YAML structure.
  • Make sure loading/parsing in your static generator still works.

Manual

    1. Write a small script `scripts/normalize_static_questions.py` that reads each YAML in `kubelingo/questions/`, rewrites it with exactly the canonical fields (mapping legacy names if needed).
    2. Run it and commit the normalized output.

Can / Cannot
  • CAN: Continue to generate static quizzes with kubelingo question-manager.
  • CANNOT: Yet use AI to augment or produce questions.

Tests
  Add tests/phase1/test_normalize_static.py:

    from scripts.normalize_static_questions import normalize_all
    import os
    import yaml

    def test_normalize_creates_no_missing_fields(tmp_path):
        normalize_all(src="kubelingo/questions", dst=str(tmp_path))
        for f in os.listdir(tmp_path):
            q = yaml.safe_load(open(os.path.join(tmp_path, f)))
            for fld in ("id","topic","difficulty","question","expected_resources","success_criteria"):
                assert fld in q

—

## Phase 2: Build a “Static × AI” Import Bridge

Objectives
  • Have an independent converter that takes the AI JSON (question_generator.py output) and spits out canonical YAML files in kubelingo/questions/auto/.
  • Do not touch your static code.

Manual

    1. Create `scripts/ai2static.py`:


        * Reads `sample_questions.json`

        * Maps each entry to canonical YAML (you already defined schema)

        * Writes to `kubelingo/questions/auto/<id>.yaml`
    2. Run it on one JSON export:

         python scripts/ai2static.py \
       --input scripts/.../questions.json \
       --dest kubelingo/questions/auto
    3. Inspect a few of the autogenerated YAMLs.

Can / Cannot
  • CAN: Mix static+AI questions in your question‐bank directory.
  • CANNOT: Yet generate on the fly per‐session question (that’s Phase 4).

Tests
  Add tests/phase2/test_ai2static.py:

    import tempfile, os, yaml
    from scripts.ai2static import ai2static

    def test_ai2static_roundtrip(tmp_path):
        # prepare a small JSON with one question
        j = [{
          "id": "abcd1234",
          "topic": "pods",
          "difficulty": "beginner",
          "question": "Test?",
          "expected_resources": ["Pod"],
          "success_criteria": ["YAML syntax is valid"]
        }]
        f = tmp_path/"in.json"
        f.write_text(json.dumps(j))
        outdir = tmp_path/"out"
        ai2static(str(f), str(outdir))
        generated = yaml.safe_load(open(outdir/"abcd1234.yaml"))
        assert generated["id"] == "abcd1234"
        assert "question" in generated

—

## Phase 3: Wire the AI CLI In as an Optional “Question Source”

Objectives
  • Extend your Kubelingo CLI or question‐manager so that you can do kubelingo generate --source=ai --count=5 (in addition to --source=static).
  • Under the hood it shells out to scripts/k8s_manifest_generator.py --mode question ... --output-file tmp.json, then converts to YAML with ai2static.

Manual

    1. In `question_manager.py`, add a new option `--source ai`.
    2. If source==ai:      subprocess.run([
              "python", "../scripts/k8s_manifest_generator.py",
              "--mode", "question",
              "--question-count", str(count),
              "--output-file", tmp_json
           ])
           from scripts.ai2static import ai2static
           ai2static(tmp_json, question_bank_dir)
    3. Leave `--source static` untouched.

Can / Cannot
  • CAN: Run your normal flows offline (static only).
  • CAN: Also run source=ai to bulk-import AI questions.
  • CANNOT: Yet generate on-the-fly per‐session question (that’s Phase 4).

Tests
  Add tests/phase3/test_qmgr_ai_source.py:

    import subprocess, tempfile, os
    def test_qmgr_ai_import(tmp_path, monkeypatch):
        # stub the AI script to output deterministic JSON
        monkeypatch.setenv("K8S_QG_SCRIPT", "tests/fixtures/fake_qg.py")
        out = subprocess.check_output([
          "kubelingo", "generate",
          "--source", "ai",
          "--count", "2",
          "--output-dir", str(tmp_path)
        ]).decode()
        # should have written two YAML files
        assert len(list(tmp_path.glob("*.yaml"))) == 2

—

## Phase 4: On-Demand AI Question Generation (Interactive)

Objectives
  • Allow your CLI to ask the AI for single new questions on the fly:

      kubelingo ask-ai --topic services --difficulty advanced

  • Immediately present the question in your REPL or CLI.

Manual

    1. Add a new command/sub‐command `ask-ai` in `kubelingo.py`.
    2. Shell out similarly to Phase 3 but with `--output-file -` (stdout JSON).
    3. Parse JSON client‐side, pretty‐print in your CLI.

Can / Cannot
  • CAN: Try AI questions live in your CLI.
  • CANNOT: Yet seamlessly drop them into paper quizzes or DB without conversion.

Tests
  Write tests/phase4/test_ask_ai_cli.py that runs your CLI with a fake AI shim returning a known JSON and asserts that the output matches.

—

## Phase 5: AI-powered Manifest Generation & Grading Plugin

Objectives
  • In your “solve” or “verify” steps, allow an AI path:

      kubelingo solve --method ai --question-id Q123  

  • That shells out to k8s_manifest_generator.py --mode generate --prompt "<question>"
  • Collects the YAML, runs your existing validation, plus AI grading under the hood.
  • Falls back to purely static linters if no API key.

Manual

    1. In `solve` command, add `--method ai`.
    2. If method==ai, run the AI generator, capture its YAML.
    3. Pipe that YAML into your existing static validators (`validation.py`), then optionally into AI grader for feedback.

Can / Cannot
  • CAN: Provide students AI-draft solutions & grades.
  • CAN: Still allow `--method static` to run your current generator + validator.
  • CANNOT: Depend entirely on AI; static always remains available.

Tests

    * `tests/phase5/test_solve_ai_solution.py`
      • monkeypatch the AI script to emit a known pod YAML
      • run `kubelingo solve --method ai --question-id Q123`
      • assert your existing validator returns PASS, and AI grade is attached.

—

## Phase 6: End-to-End Verification & Performance Measurement

Objectives
  • Write E2E smoke tests that combine static and AI flows:
    1. Import 5 static questions + 5 AI questions
    2. Solve each with both static and AI methods
    3. Collect grades & timings
    4. Produce a small report CSV/JSON

Manual

    1. Create `scripts/e2e_report.sh` that orchestrates generating, solving, grading.
    2. Commit it as a demo in `misc/`.

Can / Cannot
  • CAN: Measure AI vs static throughput, average scores.
  • CANNOT: Yet guarantee AI never hallucinate beyond core CKAD scope—keep it “coached” with strong prompts.

Tests

    * `tests/phase6/test_e2e_report.py`: run the script, assert the output JSON has 10 entries with the right fields.
