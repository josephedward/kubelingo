# Application Design Specification

## 1. Guiding Principles
- **Question Organization**: The system must support easy organization of questions.
- **Difficulty**: Initial focus is on capturing questions, not fine-grained difficulty levels. Questions are questions, and the goal is to be able to answer all of them.
- **Architecture**: Maintain a simple and understandable command-line interface (CLI) architecture.
- **Context**: Leverage documentation in the `/docs` directory to provide context for development.

## 2. Startup and Configuration
The application startup sequence will prioritize user configuration.

### 2.1. AI Provider Setup
1.  On first run, or when configuration is missing, the app will prompt the user to select an AI provider:
    ```
    --- AI Provider ---
    ○ OpenAI
    ○ Gemini
    ```
2.  After selection, it will prompt for an API key, unless one is already stored for that provider.
3.  Provided API keys will be tested for validity (e.g., ability to bill for tokens) and the user will be notified of the status.
4.  API keys will be stored securely and permanently after validation.
5.  The architecture should be modular to facilitate adding new AI providers in the future.
6.  **Implementation**: Utilize Simon Willison's `llm` and `llm-gemini` packages for AI interaction.

## 3. User Interface
The application will feature a clear, menu-driven interface.

### 3.1. Primary Menu
The main menu will be structured as follows:
```
   --- Learn ---
   ○ Study Mode (Socratic Tutor)
   ○ Missed Questions (2)
   --- Drill ---
   ○ Open Ended Questions (6)
   ○ Basic Terminology (205)
   ○ Command Syntax (105)
   ○ YAML Manifest (44)
   --- Settings ---
   ○ AI
   ○ Clusters
   ○ Question Management
   ○ Help
   ○ Report Bug
   ○ Exit App
```

### 3.2. AI Settings Menu
Selecting "AI" from the Settings menu will open a dedicated sub-menu for managing AI providers and API keys:
```
What would you like to do? (Use arrow keys)
» ○ Set active AI Provider (current: Gemini)
  --- API Keys ---
  ○ View Gemini API Key (Set (from file))
  ○ Set/Update Gemini API Key
  ○ View Openai API Key (Set (from env))
  ○ Set/Update Openai API Key
```

### 3.3. Study Mode Menu
Selecting "Study Mode" from the Learn menu will first prompt for the exercise type:
```
--- Exercise Type ---
   ○ Open-Ended
   ○ Basic Terminology
   ○ Command Syntax
   ○ YAML Manifests
```
After selecting an exercise type, the user will be shown the subject matter menu to begin the session.

### 3.4. Drill Down Menu
Selecting a "Drill" category will lead to a sub-menu of subject matter categories:
```
   ○ Linux Syntax (Commands from Bash, Vim, Kubectl, Docker, Helm)
   ○ Core workloads (Pods, ReplicaSets, Deployments; rollouts/rollbacks)
   ○ Pod design patterns (initContainers, sidecars, lifecycle hooks)
   ○ Commands, args, and env (ENTRYPOINT/CMD overrides, env/envFrom)
   ○ App configuration (ConfigMaps, Secrets, projected & downwardAPI volumes)
   ○ Probes & health (liveness, readiness, startup; graceful shutdown)
   ○ Resource management (requests/limits, QoS classes, HPA basics)
   ○ Jobs & CronJobs (completions, parallelism, backoff, schedules)
   ○ Services (ClusterIP/NodePort/LoadBalancer, selectors, headless)
   ○ Ingress/Egress & HTTP routing (basic rules, paths, service backends)
   ○ Networking utilities (DNS in-cluster, port-forward, exec, curl)
   ○ Persistence (PVCs, using existing StorageClasses, common volume types)
   ○ Observability & troubleshooting (logs, describe/events, kubectl debug/ephemeral containers)
   ○ Metadata Labels, annotations & selectors (label ops, field selectors, jsonpath)
   ○ Imperative vs declarative (—dry-run, create/apply/edit/replace/patch)
   ○ Container Image & registry use (imagePullPolicy, imagePullSecrets, private registries)
   ○ Security basics (securityContext, runAsUser/fsGroup, capabilities, readOnlyRootFilesystem)
   ○ ServiceAccounts in apps (mounting SA, minimal RBAC needed for app access)
   ○ Scheduling hints (nodeSelector, affinity/anti-affinity, tolerations)
   ○ Namespaces & contexts (scoping resources, default namespace, context switching)
   ○ API discovery & docs (kubectl explain, api-resources, api-versions)
```

### 3.5. Question Interaction Menu
When answering a question, the user will have these options:
```
○ Answer Question
○ Visit Source
○ Next Question
○ Previous Question
○ Triage
○ Back (returns to previous menu)
```

### 3.6. Question Management Menu
The "Question Management" option in Settings provides tools for content curation. This menu will be orchestrated by `scripts/kubelingo_tools.py` and consolidated management scripts.
```
○ Generate Questions
○ Add Questions
○ Remove Questions
○ Triaged Questions
```
This interface replaces the direct-script-execution model with a more user-friendly, function-oriented approach. The underlying scripts should be refactored to support these actions.

## 4. Data Architecture
The application will follow a "YAML as source of truth" model.

- **Question Content**: All questions are defined in YAML files located in the `/yaml` directory.
- **Metadata Database**: A SQLite database will be used *only* to store metadata about the questions (e.g., file path, question ID, review status, triage status, user stats). It will not store the question content itself.
- **Backups**: Regular backups of the `/yaml` directory will be maintained, with consolidated lists of all questions stored in `/yaml/backups`.

## 5. Question Schema
The schema will not include a `difficulty` field. Difficulty is subjective and can be inferred later from user performance data, rather than being a static attribute.

### 5.1. Question Types
1.  **Open-Ended**: Requires AI to do fuzzy matching on an explanation. These are generated during "Study Mode". The CLI must handle multiline input gracefully, allowing for arrow key navigation without creating special character artifacts. Graded on `Enter`.
2.  **Basic Terminology**: Single-word/command answers. Can be evaluated without AI but are generated with AI. Can be easily added via AI parsing. Graded on `Enter`.
3.  **Command Syntax**: Evaluated by executing the command (e.g., with `kubectl --dry-run=client`). Requires AI to validate alternative correct answers (e.g., aliases, different flags). Graded on `Enter`.
4.  **YAML Manifest**: Requires the user to create or edit a YAML file. The app will launch Vim with the prompt context. Upon quitting Vim, the resulting file will be graded.

### 5.2. Subject Matter Categories
Categories are subordinate to Question Types. Simplified short names should be used in the YAML/DB schema (e.g., `linux-syntax`, `core-workloads`).

- Linux Syntax (Commands from Bash, Vim, Kubectl, Docker, Helm)
- Core workloads (Pods, ReplicaSets, Deployments; rollouts/rollbacks)
- Pod design patterns (initContainers, sidecars, lifecycle hooks)
- Commands, args, and env (ENTRYPOINT/CMD overrides, env/envFrom)
- App configuration (ConfigMaps, Secrets, projected & downwardAPI volumes)
- Probes & health (liveness, readiness, startup; graceful shutdown)
- Resource management (requests/limits, QoS classes, HPA basics)
- Jobs & CronJobs (completions, parallelism, backoff, schedules)
- Services (ClusterIP/NodePort/LoadBalancer, selectors, headless)
- Ingress/Egress & HTTP routing (basic rules, paths, service backends)
- Networking utilities (DNS in-cluster, port-forward, exec, curl)
- Persistence (PVCs, using existing StorageClasses, common volume types)
- Observability & troubleshooting (logs, describe/events, kubectl debug/ephemeral containers)
- Metadata Labels, annotations & selectors (label ops, field selectors, jsonpath)
- Imperative vs declarative (—dry-run, create/apply/edit/replace/patch)
- Container Image & registry use (imagePullPolicy, imagePullSecrets, private registries)
- Security basics (securityContext, runAsUser/fsGroup, capabilities, readOnlyRootFilesystem)
- ServiceAccounts in apps (mounting SA, minimal RBAC needed for app access)
- Scheduling hints (nodeSelector, affinity/anti-affinity, tolerations)
- Namespaces & contexts (scoping resources, default namespace, context switching)
- API discovery & docs (kubectl explain, api-resources, api-versions)


## 6. Core Application Rules & Logic
- **Single CLI Interface**: All functionality must be coordinated from a single, cohesive command-line application.
- **Adding Questions**: Must be easy via a well-defined schema or through AI parsing.
- **AI Feedback**: AI-driven feedback or explanation should be provided for every answer, explaining the correct response or the subject matter for simpler questions.
- **Study Mode**: Questions generated in Study Mode must adhere to the schema and be saved to a YAML file, with metadata updated in the database.
- **Review System**: Questions answered incorrectly are automatically flagged for review. Answering correctly removes the flag. This is not user-configurable.
- **Triage System**: Users can flag problematic questions for maintainer review via the "Triage" option.
- **No Automatic Deletion**: The application must never automatically delete questions. Deletion is a manual, explicit action available to maintainers through the Question Management tools. Problematic questions should generally be triaged rather than deleted.
- **Execution Environment**: No live cluster integration is required initially. Command and manifest evaluation will use dry-run capabilities.
- **Database Integrity**: The database is for metadata only and should never be cleared automatically.
- **Enrichment**: AI-based content enrichment should only occur during question generation or triage, not on application startup.
- **AI Provider Management**: The user can change providers and manage API keys via the "AI Provider" setting. The application will indicate the active provider and recognize keys set in the environment.
- **Offline Mode**: Only "Basic Terminology" questions are available offline, as they can be evaluated without AI.
- **Duplicate Check**: The application should check for and avoid generating duplicate or overly similar questions.
