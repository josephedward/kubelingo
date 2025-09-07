### Detailed Roadmap Implementation Plan

This plan outlines the steps to move from the current state to a fully robust implementation of the Kubernetes Question Generation System, addressing the remaining incomplete phases of the roadmap.

**Phase 1: Completing Core Functionality & Robustness**

**Goal:** Ensure the core generation and grading system is fully online-dependent, robustly tested, and has enhanced performance tracking.

**1. Audit & Cleanup (Focus on Offline Mode Removal)**
    *   **1.1 Identify Offline Artifacts:**
        *   Search the entire codebase for keywords like `offline_mode`, `local_cache`, `file_cache`, `mock_data`, and any configuration flags or branches related to offline operation.
        *   Review `kubelingo/kubelingo.py`, `kubelingo/utils.py`, and any other modules that handle question loading or data persistence for local file-based fallbacks.
        *   List all identified code paths, UI toggles, or config settings.
    *   **1.2 Decide on Removal vs. Repurposing:**
        *   For each identified artifact, determine if it should be completely removed or repurposed (e.g., the existing local question cache could be adapted into a "retry queue" for failed API calls, but *not* as a primary data source).
    *   **1.3 Implement Removal/Repurposing:**
        *   Refactor code to remove all `if offline_mode` branches.
        *   Modify question loading logic to *always* attempt generation via the AI engine first. If a local cache is repurposed for retries, ensure it's clearly distinct from the primary online flow.
        *   Delete unused files or configurations related to offline mode.
    *   **1.4 Update Documentation:**
        *   Remove all mentions of "offline mode" from `README.md`, `docs/usage.md`, and any other user-facing documentation.
        *   Update CLI help messages to remove any flags or options related to offline functionality.

**3. Introduce Mandatory AI-key + Online-only Guard (Full Implementation)**
    *   **3.1 Enforce Online Connection for All Question Paths:**
        *   Modify `list_and_select_topic` and any other question retrieval functions in `kubelingo/kubelingo.py` to ensure that if an AI provider is configured, questions are primarily sourced or generated via the AI engine. Local YAML files should only serve as a fallback for *existing* questions if the AI fails, or for historical data, not as a primary source for new questions.
        *   Ensure that if no valid AI key is present, the application either prompts the user to configure one or gracefully exits, preventing any "offline" operation.
    *   **3.2 Remove Non-API Fallbacks:**
        *   Verify that any code that previously used a local cache as a feature toggle (i.e., as an alternative to the AI) now exclusively invokes the AI engine, with any local file-based retry queue serving only for API errors.
    *   **3.3 Bump Version:**
        *   Update the project's version number (e.g., in `pyproject.toml` or a dedicated version file) to reflect this significant architectural change.

**5. Design & Implement Performance & Outcome Tracking (Enhancement)**
    *   **5.1 Re-evaluate Data Model (SQL vs. YAML):**
        *   **Decision Point:** Confirm if an SQL database is truly preferred over the existing `user_data/performance.yaml`. If so, define a detailed SQL schema for a `question_attempts` table, including fields like `user_id`, `question_id`, `difficulty`, `timestamp`, `response_time`, `grade_score`, `passed_bool`, `ai_feedback`, `static_feedback`, `model_used`, etc.
    *   **5.2 Implement Database Integration (If SQL):**
        *   Choose a suitable Python ORM (e.g., SQLAlchemy, Peewee) and integrate it into the project.
        *   Create database connection and session management utilities.
    *   **5.3 Migrate Existing Data (If SQL):**
        *   Write a one-time script to read data from `user_data/performance.yaml` and insert it into the new SQL database.
        *   Ensure data integrity and proper mapping of fields.
    *   **5.4 Enhance Tracker Module:**
        *   Refactor `kubelingo/performance_tracker.py` (or create a new `kubelingo/tracking.py`) to:
            *   Record every question generation request (prompt, latency, success/failure, model used).
            *   Record every grading event (score, feedback length, any API errors, model used).
            *   Store detailed static and AI evaluation results.
    *   **5.5 Implement Metrics Pushing (Optional but Recommended):**
        *   If external metrics backend (e.g., Prometheus, StatsD) is desired, integrate a client library to push key performance indicators (KPIs) from the tracker module.

**6. End-to-end Integration & Sanity Checks (Comprehensive Testing)**
    *   **6.1 Develop Comprehensive Integration Tests:**
        *   Create new test files (e.g., `tests/integration/test_e2e_generation.py`, `tests/integration/test_e2e_grading.py`).
        *   Write tests that:
            *   Generate a batch of questions across different topics and difficulty levels.
            *   Simulate user answers (both correct and incorrect, and varying formats).
            *   Call the `KubernetesGrader` with simulated answers.
            *   Assert the shape, content, and correctness of the returned `GradingResult` objects.
            *   Verify that performance tracking records are correctly created and persisted (in the new data store, if applicable).
            *   Test the full flow from question selection to grading and performance update.
    *   **6.2 Mock External Dependencies:**
        *   Ensure that all integration tests mock external services (OpenAI, Gemini, OpenRouter APIs) to keep tests fast, deterministic, and independent of network connectivity or API rate limits. Use libraries like `unittest.mock` or `pytest-mock`.

**Phase 2: Documentation & Deployment Preparation**

**Goal:** Provide clear, up-to-date documentation for users and developers, and prepare for deployment.

**7. Documentation & Developer Onboarding**
    *   **7.1 Update User-Facing Documentation (`README.md`, `docs/usage.md`):**
        *   Clearly state the "online-only" requirement and the necessity of valid API keys (Gemini, OpenAI, OpenRouter).
        *   Provide detailed instructions on how to obtain and configure API keys.
        *   Document any new CLI arguments or configuration options for prompt customization, difficulty levels, or AI provider selection.
        *   If an SQL database is introduced, provide instructions on how to set it up, run migrations, and inspect performance data.
        *   Update examples to reflect the new online-first workflow.
    *   **7.2 Create Developer Onboarding Guide:**
        *   Add a new section or file (e.g., `docs/developer_guide.md`) with a short HOW-TO for future engineers on "adding a new question type." This should cover:
            *   How to define new question templates.
            *   How to integrate new topics or difficulty levels.
            *   Guidelines for writing effective prompts for the AI generator.
            *   How to extend the grader for new validation checks (if applicable).
            *   How to run and extend the new integration tests.

**Phase 3: Rollout & Finalization**

**Goal:** Safely deploy the new system, monitor its performance, and finalize the transition.

**8. Soft Rollout & Monitoring**
    *   **8.1 Implement Feature Flags (If Applicable):**
        *   If there's a need for a gradual transition, implement feature flags to enable/disable the new AI-powered generation/grading for specific user groups or environments.
    *   **8.2 Deploy to Staging/Test Group:**
        *   Deploy the updated application to a staging environment or release it to a small, controlled test group.
    *   **8.3 Set Up Comprehensive Monitoring:**
        *   Monitor logs and metrics for:
            *   **API Error Rates:** Track errors from calls to OpenAI, Gemini, and OpenRouter.
            *   **Generation/Grade Latencies:** Measure the response times for question generation and answer grading.
            *   **Distribution of Difficulty vs. Pass-Rates:** Analyze how well users perform on questions of different difficulties generated by the AI.
            *   **Resource Utilization:** Monitor CPU, memory, and network usage, especially during AI interactions.
    *   **8.4 Gather Feedback & Tune:**
        *   Actively collect feedback from the test group.
        *   Iteratively tune AI prompts, grading thresholds, and difficulty calibration based on user performance and feedback.

**9. Full Cutover & Cleanup**
    *   **9.1 Remove Leftover Offline Artifacts:**
        *   Once confidence in the online-only system is high, perform a final sweep to remove any remaining offline-related code, configurations, or test cases that were not removed in earlier steps.
        *   Delete any old local question files or caches that are no longer needed.
    *   **9.2 Bump to New Major Version:**
        *   Update the project's version to a new major release (e.g., `v2.0.0`) to signify the complete transition to an online-only, AI-powered system.
    *   **9.3 Announce Online-Only Release:**
        *   Communicate the change to users, highlighting the new features and the requirement for an internet connection and API keys.
    *   **9.4 Archive Old Code Branch:**
        *   Create a specific Git tag or branch to archive the state of the codebase just before the full cutover, preserving the old offline functionality for historical reference.


        PHASE 1 – “Generate” Menu Core

    1. Wire up the Generate submenu with three commands:
       • trivia → use `QuestionGenerator.generate_question(…)`, format into Q/A or MCQ
       • command → same generator but only imperative-style prompts (you can extend your templates)
       • manifest → your YAML manifest builder from CLI
    2. For each mode, draft the minimal AI prompt and test in a REPL that you get back a valid question + “suggested_answer” using your tight builders.
    3. On success, write the Q object to `/questions/uncategorized/{id}.json`.

PHASE 2 – Post-Question Navigation & Persistence

    1. Load your `/questions/uncategorized/*.json` (or by‐topic) into a session, track an index.
    2. Implement “backward”, “forward”, “skip”, “show solution”, “visit source”, “quit quiz”.
    3. On each “show solution” call, pretty-print the `suggested_answer` as YAML.
    4. On “correct”/“missed”/“remove” move the file into `/questions/correct/{topic}/` or `/questions/incorrect/{topic}/`.

PHASE 3 – Review Menu (AI-Driven Reflection)

    1. Define “correct” script:
       • Scan `/questions/correct/…/*.json`, aggregate question+answer pairs.
       • Prompt AI: “Given these completed exercises, what strengths do I have vs. the CKAD curriculum?”
       • Return a short actionable summary.
       • Allow an interactive follow-up Q/A loop.
    2. Mirror for “incorrect” with “What weaknesses do I need to work on?”
    3. If you want edits, these scripts should be able to rename/move files, e.g.
       • “Group all networking failures into `/review/needs-networking/`”
       • “Merge these 3 YAMLs into a single study file.”
    4. Each sub-feature (aggregation, summarization, interactive Q&A) gets its own prompt prototype and small script.

PHASE 4 – Import Menu (AI-Assisted Ingestion)

    1. **Uncategorized**: Prompt: “Here’s an old YAML from legacy… rewrite into our JSON schema (id, topic, etc.)” and save into `/questions/uncategorized`.
    2. **From URL**:
       • Fetch page, extract code blocks or text, prompt AI: “Generate a question+answer from this snippet.”
       • Fall back gracefully if scraping fails.
    3. **From File Path**:
       • Read arbitrary file, hand off to AI: “Here’s a file—extract any Kubernetes-style exercises you see.”
       • Save the results into uncategorized.
    4. Test each import type with edge cases (no YAML, multiple code blocks, corrupted).

# Main Menu 
- config/settings
- review (requires AI)
- generate (requires AI)
- import (requires AI) 

# Config Menu (already implemented) 
- api keys etc already done 

# Review Menu
- correct (runs a script to categorize, file into folders and provide an AI summary of what you appear to good at relative to the CKAD - requires AI prompt)  
- incorrect (runs a script to categorize, file into folders and provide an AI summary of what you appear to be BAD at relative to the CKAD - requires AI prompt) 
(Ideally these will be INTERACTIVE, and allow the user to have a dialogue with the AI about what they have worked on, where they need to improve, formatting questions - and these scripts should have the ability to reformat files, rename, combine, organize them into folders etc) 


# Generate Menu (all of these choices immediately move to the subject matter menu)
- trivia (simple question and answer; vocabulary/true-false/multiple choice) 
- command (user must enter an imperative bash command) 
- manifest (user must use vim to provide a manifest as an answer)

# Subject Matter Menu
- pods
- deployments
- services
- configmaps
- secrets
- ingress
- volumes
- rbac
- networking
- monitoring
- security
- troubleshooting


# Import Menu (all of these options require AI queries)
- uncategorized (user selects a file from questions/uncategorized/ and the AI uses it for inspiration; not hardcoded static values/checks)
- from url (requires scraping too)
- from file path (may provide difficult file types or strange parsing; definitely requires AI and may need to fail cleanly) 

# Question Menu (do not write this literally; it comes after every question is asked)
- vim - opens vim for manifest-based questions 
- backward - previous question 
- forward  - skip to next question  
- solution - shows solution and the post-answer menu 
- visit - source (opens browser at source) 
- quit - back to main menu 

# Post Answer Menu (always comes after a question is answered)
- again (try again - formerly ‘retry) 
- correct 
- missed 
- remove question 

Example schema for question: 
    {
        "id": "a1b2c3d4",
        "topic": "pods",
        "difficulty": "beginner",
        "question": "Create a simple Pod named ‘demo-pod running the latest nginx image" (notice how the exact fields expected match with the answer),
        "documentation_link": "https://kubernetes.io/docs/concepts/workloads/pods/",
        "suggested_answer": """ | 
            apiVersion: v1
            kind: Pod
            metadata:
              name: demo-pod
            spec:
              containers:
              - name: main
                image: nginx:latest
            """ (this must be properly formatted yaml) 
        "user_answer": "" (after answered)
    }



/questions/ folder: 
- correct 
- incorrect 
- uncategorized (legacy yaml files, other context files I would like to try to deliberately test towards) 