# Analysis of Startup Issues - 2025-08-13

The application's startup sequence has several critical design flaws and bugs that need to be addressed. The core issue is that a destructive and slow bootstrapping process runs before the application is properly configured, leading to errors and a poor user experience.

## Key Problems Identified

### 1. Incorrect Execution Order
- **Problem**: The application attempts to run a database bootstrap process (`bootstrap_on_startup`) *before* prompting the user to configure their AI provider and API keys.
- **Impact**: This leads to errors when the bootstrap process tries to use AI features that haven't been configured yet. The user setup flow should always be the first thing that runs.

### 2. Destructive Database Operations
- **Problem**: The bootstrap process clears all questions from the database (`DELETE FROM questions`) on every startup.
- **Impact**: This is a destructive action that wipes out user-generated or custom data. The application should never clear the database automatically.

### 3. Flawed Data Persistence Model
- **Problem**: The application ingests entire YAML questions into the SQLite database. The database should only store *metadata* (like review status, performance stats, etc.) and a reference to the source YAML file. The YAML files should remain the single source of truth for question content.
- **Impact**: This creates data duplication, synchronization issues, and makes the startup process slow and fragile.

### 4. Misplaced Enrichment Logic
- **Problem**: The application tries to perform AI-based categorization and enrichment on every startup.
- **Impact**: This is inefficient and costly. Enrichment should be an explicit, user-triggered action (e.g., during triage or via a dedicated script), not an implicit startup task.

### 5. Startup Bugs
- **Bug**: `Failed to initialize LLM client for AICategorizer: Unsupported LLM client type in configuration: None`.
- **Cause**: This is a direct result of the incorrect execution order. The `AICategorizer` is instantiated before the user has a chance to select an AI provider.
- **Bug**: `Database error during bootstrap: no such column: category_id`.
- **Cause**: The database schema is out of sync with the application's code, which now expects a `category_id` column that doesn't exist. This indicates the database migration/setup logic is broken or missing.

## Proposed High-Level Fixes
1.  **Refactor Startup Sequence**: Move the API key and provider check to be the very first action in `initialize_app`. The database bootstrap logic should be removed from the startup path entirely.
2.  **Adopt a Metadata-Only DB Model**: The database should only store pointers to YAML questions (e.g., file path + question ID) and user-specific metadata. Loading questions should be done on-demand from YAML files.
3.  **Remove Startup Bootstrap**: Eliminate the `bootstrap_on_startup` function. Database setup should be handled by a one-time migration script or an initial setup check.
4.  **Fix Database Schema**: A script needs to be created or run to update the database schema to include `category_id` and any other missing columns.
