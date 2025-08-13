# Application Design Specification

## 1. Guiding Principles
- **Question Organization**: Use these guidelines to generate questions that are easy to organize.
- **Difficulty**: Do NOT worry about difficulty level for now. Questions are questions - ideally we will want to be able to answer all of them we come across.
- **Architecture**: Keep the CLI architecture simple.
- **Context**: Lean on `/docs` to help you provide context.

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
   ○ Socratic Mode
   ○ Missed Questions (2)
   --- Drill ---
   ○ Open Ended Questions (60)
   ○ Basic Terminology (700)
   ○ Command Syntax (244)
   ○ YAML Manifest (80)
   --- Settings ---
   ○ AI
   ○ Clusters
   ○ Question Management
   ○ Help
   ○ Report Bug (bug ticket script)
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

### 3.3. Socratic Mode Menu
Selecting "Socratic Mode" from the Learn menu will first prompt for the exercise type:
```
--- Exercise Type ---
   ○ Open-Ended
   ○ Basic Terminology
   ○ Command Syntax
   ○ YAML Manifests
```
After selecting an exercise type, the user will be shown the subject matter menu to begin the session.

### 3.4. Drill Down Menu
Selecting a "Drill" category will lead to a sub-menu of subject matter categories, with counts for each:
```
   ○ Linux Syntax(Commands from Vim, Kubectl, Docker ,Helm )  (12)
   ○ Core workloads (Pods, ReplicaSets, Deployments; rollouts/rollbacks) (30)
   ○ Pod design patterns (initContainers, sidecars, lifecycle hooks) (5)
   ○ Commands, args, and env (ENTRYPOINT/CMD overrides, env/envFrom) (17)
   ○ App configuration (ConfigMaps, Secrets, projected & downwardAPI volumes) (9)
   ○ Probes & health (liveness, readiness, startup; graceful shutdown)(22)
   ○ Resource management (requests/limits, QoS classes, HPA basics) (13)
   ○ Jobs & CronJobs (completions, parallelism, backoff, schedules) (40)
   ○ Services (ClusterIP/NodePort/LoadBalancer, selectors, headless) (19)
   ○ Ingress & HTTP routing (basic rules, paths, service backends) (53)
   ○ Networking utilities (DNS in-cluster, port-forward, exec, curl) (40)
   ○ Persistence (PVCs, using existing StorageClasses, common volume types) (8)
   ○ Observability & troubleshooting (logs, describe/events, kubectl debug/ephemeral containers)(18)
   ○ Labels, annotations & selectors (label ops, field selectors, jsonpath) (19)
   ○ Imperative vs declarative (—dry-run, create/apply/edit/replace/patch) (22)
   ○ Image & registry use (imagePullPolicy, imagePullSecrets, private registries)
   ○ Security basics (securityContext, runAsUser/fsGroup, capabilities, readOnlyRootFilesystem) (12)
   ○ ServiceAccounts in apps (mounting SA, minimal RBAC needed for app access) (15)
   ○ Scheduling hints (nodeSelector, affinity/anti-affinity, tolerations) (20)
   ○ Namespaces & contexts (scoping resources, default namespace, context switching) (23)
   ○ API discovery & docs (kubectl explain, api-resources, api-versions) (17)
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
The "Question Management" option in Settings provides tools for content curation. This menu is orchestrated by `scripts/kubelingo_tools.py`.
```
--- Manage Questions ---
○ Generate Questions
○ Add Questions
○ Remove Questions
○ Triaged Questions
```
This interface replaces the direct-script-execution model with a more user-friendly, function-oriented approach. The underlying scripts should be refactored to support these actions.

## 4. Data Architecture
The application will follow a "YAML as source of truth" model.

- **Question Content**: All questions are defined in YAML files located in the `/yaml` directory.
- **Metadata Database**: A SQLite database will be used to track metadata about the YAML files (e.g., file paths, question IDs, review/triage status, stats). It will not store the question content itself. The database should be treated as disposable and rebuildable from the YAML source. New databases should be written on updates rather than editing existing ones.
- **Backups**: Regular backups of the `/yaml` directory will be maintained, with consolidated lists of all questions stored in `/yaml/backups`.

## 5. Question Schema
The schema will not include a `difficulty` field.

### 5.1. Question Types
1.  **Open-Ended**: Requires AI to do fuzzy matching on an explanation.
    - Generated during "Socratic Mode".
    - Requires an active AI to evaluate if the answer is "more or less" correct.
    - CLI must handle multiline input gracefully, allowing for arrow key navigation without creating special character artifacts.
    - Graded on `Enter`.
2.  **Basic Terminology**: Single-word/command answers (e.g., resource type, short name, true/false).
    - Can be evaluated without AI, making them available offline.
    - Generated with AI, and can be easily added via AI parsing.
    - Graded on `Enter`.
3.  **Command Syntax**: Evaluated by executing the command (e.g., with `kubectl --dry-run=client`).
    - Requires AI to validate alternative correct answers (e.g., aliases, different flags).
    - Focused on commands from Linux, Vim, Kubectl, and Helm.
    - Graded on `Enter`.
4.  **YAML Manifest**: Requires the user to create or edit a YAML file.
    - The app will launch Vim with the prompt context and a file to edit.
    - Upon quitting Vim, the resulting file will be graded.

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
- **Adding Questions**: Must be easy via a well-defined schema or through AI parsing of various document types. It should be easy to copy and paste questions and have them formatted correctly.
- **AI Feedback**: AI-driven feedback or explanation should be provided for every answer.
- **Study Mode**: "Socratic Mode" generates new questions. Generated questions must adhere to the schema and be saved to a YAML file, with metadata updated in the database.
- **Review System**: Questions answered incorrectly are automatically flagged for review. Answering correctly removes the flag. This is not user-configurable.
- **Triage System**: Users can flag problematic questions for maintainer review via the "Triage" option.
- **No Automatic Deletion**: The application must never automatically delete questions. Deletion is a manual, explicit action. Problematic questions should generally be triaged rather than deleted.
- **Execution Environment**: No live cluster integration is required initially. Command and manifest evaluation will use dry-run capabilities.
- **AI Provider Management**: The user can change providers and manage API keys via the "AI" setting. The application will indicate the active provider and recognize keys set in the environment.
- **Duplicate Check**: The application should check for and avoid generating duplicate or overly similar questions.

## 7. Testing and Validation
- **Question Generation**: Must support generating questions for all 4 question types and all 21 subjects.
- **Question Ingestion**: Ensure questions can be added and reformatted from various document types.
- **Answering Mechanics**: Validate that each question type can be answered according to its specified interaction model.
- **Data Persistence**: Generated questions must be automatically saved to YAML files and indexed in the database.
- **Content Management**: Verify that questions can be deleted and that triaged questions can be fixed.
- **Uniqueness**: The system must prevent the creation of duplicate questions.
