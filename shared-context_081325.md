# Bug Fixes and Improvements (08-13-2025)

This document outlines the fixes for two issues identified in the interactive mode of Kubelingo.

## 1. Drill Mode Question Loading

*   **Problem:** The main menu correctly showed a count of questions for a category (e.g., "Command Syntax (43)"), but selecting the drill would result in a "No questions found" message.
*   **Root Cause:** The drill-down logic required questions to have both a `category` and a `subject`. The questions in the database had a category but were missing a subject, causing the subject-selection menu to find nothing and fail.
*   **Fix:**
    1.  The `_run_subject_drill_menu` in `kubelingo/modules/kubernetes/socratic_mode.py` was updated. If it fails to find any specific subjects for a category, it now attempts to load all questions belonging to that category, regardless of subject.
    2.  The `_get_questions_by_category_and_subject` method was modified to support fetching questions by category alone, which enables the fix above.
*   **Outcome:** Users can now drill into a category and get a quiz on all available questions, even if those questions haven't been assigned to a specific subject.

## 2. Socratic Tutor AI Configuration Check

*   **Problem:** The "Study Mode (Socratic Tutor)" and other AI-dependent features were enabled in the menu even when no valid API key was configured. Selecting them would lead to a session failure error.
*   **Root Cause:** The check for AI readiness (`has_api_key` in `kubelingo/cli.py`) was too lenient. It only verified the existence of an LLM client object, which could be instantiated even without a valid API key. The failure occurred only when the client tried to make an API call.
*   **Fix:** The logic in `run_interactive_main_menu` was improved to explicitly check for an active API key using `get_active_api_key()`. If no key is present, the LLM client is set to `None`, which correctly disables the AI-related menu items.
*   **Outcome:** AI-dependent features are now correctly disabled in the UI when not configured, preventing users from entering a broken session and providing a clearer indication that setup is required.
