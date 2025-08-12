<!-- Shared Context for Kubelingo agents -->
# Shared Context

This file defines the **fundamental** exercise categories that all Kubelingo agents should recognize:

- **basic**: Conceptual Q&A or Socratic-style quizzes focusing on core Kubernetes concepts.
- **command**: Command-line syntax quizzes (e.g., kubectl, helm, shell, vim commands).
- **manifest**: YAML/manifest authoring and editing exercises (e.g., creating and modifying Kubernetes resources).

Beyond these three categories, there will be many **subject matter** categories (for example, "Core Concepts", 
"Pod Management", or "Networking Utilities") that are meant to be more numerous and flexible to allow 
experimentation with different quiz groupings.

Agents and scripts can refer to this file to ensure they categorize or contextualize questions consistently.