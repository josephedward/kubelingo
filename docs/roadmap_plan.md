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
            *   Generate a batch of questions across different topics and question types.
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
        *   Document any new CLI arguments or configuration options for prompt customization, question types, or AI provider selection.
        *   If an SQL database is introduced, provide instructions on how to set it up, run migrations, and inspect performance data.
        *   Update examples to reflect the new online-first workflow.
    *   **7.2 Create Developer Onboarding Guide:**
        *   Add a new section or file (e.g., `docs/developer_guide.md`) with a short HOW-TO for future engineers on "adding a new question type." This should cover:
            *   How to define new question templates.
            *   How to integrate new topics or question types.
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
            *   **Distribution of Question Type vs. Pass-Rates:** Analyze how well users perform on questions of different types generated by the AI.
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