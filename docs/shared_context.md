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