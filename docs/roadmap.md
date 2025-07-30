# Kubelingo Project Roadmap

This document outlines the vision, features, and enhancements planned for the Kubelingo CLI quiz tool. It is organized into key focus areas and milestone ideas.

> _This roadmap is a living document. Feel free to propose additions or reprioritize items via issues or pull requests._

## Phase 0: Current Implementation

### Existing Features to Maintain
- [x] **LLM Integration**: OpenAI API integration for detailed explanations (`kubelingo/utils/llm_integration.py`)
- [x] **Review/Flagging System**: Mark questions for later review (`mark_question_for_review`, `unmark_question_for_review`)
- [x] **Rust-Python Bridge**: Performance-critical validation functions in Rust (`kubelingo_core` module)
- [x] **Session History**: Basic session logging and history tracking
- [x] **Semantic YAML Validation**: Compare parsed YAML structures, not raw text
- [x] **Category Filtering**: Filter questions by Kubernetes topic areas
- [x] **Randomized Question Order**: Prevent memorization of question sequences
- [x] **Multiple Question Types**: Command-based and YAML editing exercises

### Technical Infrastructure
- [x] **Hybrid Architecture**: Python CLI with Rust performance modules
- [x] **Maturin Build System**: Python package with Rust extensions
- [x] **CI/CD Pipeline**: GitHub Actions with multi-Python version testing
- [x] **Modular Design**: Separate modules for different quiz types

## Phase 1: Unified Shell Experience

### Question Schema Enhancements
_Labels: enhancement, schema_
- Add `pre_shell_cmds`, `initial_files`, `validation_steps` to the Question model.
- Extend content loaders (JSON/MD/YAML) to populate the new fields.

### Sandbox Runner & Helper
_Labels: enhancement, sandbox_
- Implement `run_shell_with_setup(pre_shell_cmds, initial_files, validation_steps)` in `sandbox.py`:
  - Creates a temporary workspace and writes initial files.
  - Executes `pre_shell_cmds` (e.g., `kubectl apply -f …`).
  - Spawns an interactive shell (PTY or container) and logs the session transcript.
  - Runs validation steps (`step.cmd`) and applies matchers.
  - Cleans up (teardown and workspace removal).
- Ensure deterministic evaluation of `kubectl`/`helm` commands and cluster state.

### CLI & Session Refactor
_Labels: enhancement, cli_
- Refactor `Session._run_shell_question` to invoke the sandbox helper.
- Simplify CLI menus to a single “Answer (opens shell)” flow.
- Remove legacy YAML/Vim-specific branches.

### Session Transcript & AI-Based Evaluation
_Labels: enhancement, logging, ai_
- Record full terminal session using `script` or PTY logging (captures Vim keystrokes and shell commands).
- Sanitize and store transcripts for audit and replay.
- Implement deterministic evaluation pipeline based on transcript parsing and sanity checks.
- (Optional) Integrate AI-based evaluator to grade freeform workflows via LLM.

### Testing & Documentation
_Labels: testing, docs_
- Write unit and integration tests for the unified shell experience.
- Update or add documentation under `docs/` to reflect the new flow.

## Test Coverage Improvements

### Comprehensive CLI Testing
_Labels: testing, enhancement_

Add tests for main entry points, argument parsing, and error handling

## Body
The current CLI module lacks comprehensive test coverage. We need to add tests for:

- Main entry point logic
- Argument parsing edge cases  
- Session initialization
- Error handling and user feedback
- Configuration management

## Acceptance Criteria
- [ ] Test main CLI entry points
- [ ] Test argument parsing validation
- [ ] Test error handling scenarios
- [ ] Test user interaction flows
- [ ] Achieve >80% coverage for CLI module

## Priority
Critical - needed for reliability

### YAML Editing Workflow Tests
_Labels: testing, yaml-editing_

Mock vim subprocess calls and test file I/O operations

## Body
The YAML editing workflow currently has minimal test coverage. We need comprehensive tests that mock external dependencies and also test against a real Vim instance.

- [x] Mock vim subprocess calls
- [ ] Test file I/O operations
- [ ] Validate exercise generation
- [ ] Test validation feedback loops
- [ ] Test error recovery scenarios
- [ ] **(New)** Add real Vim integration tests using a `vimrunner` harness.

## Acceptance Criteria
- [ ] All YAML editing workflows tested
- [ ] Subprocess calls properly mocked
- [ ] File operations tested
- [ ] >85% coverage for VimYamlEditor

## Priority
High - core functionality

### Integration Test Framework
_Labels: testing, integration_

End-to-end workflow testing for complete user journeys

## Body
We need an integration test framework to test complete user workflows from start to finish.

- [ ] End-to-end workflow tests
- [ ] User journey validation
- [ ] Cross-module integration testing
- [ ] Performance validation
- [ ] Error path testing

## Acceptance Criteria
- [ ] Framework supports full workflow testing
- [ ] Tests cover major user journeys
- [ ] Integration between modules validated
- [ ] Performance benchmarks included

## Priority
High - ensures system reliability

### Performance Benchmarks
_Labels: testing, performance_

Add tests for question loading and validation performance

## Body
Add performance testing to ensure the system scales well with larger question sets.

- [ ] Question loading performance tests
- [ ] YAML validation speed benchmarks
- [ ] Memory usage optimization tests
- [ ] Startup time benchmarks
- [ ] Large dataset handling tests

## Acceptance Criteria
- [ ] Performance benchmarks established
- [ ] Regression testing in place
- [ ] Memory usage optimized
- [ ] Startup time < 2 seconds

## Priority
Medium - optimization

### Error Handling Coverage
_Labels: testing, error-handling_

Test edge cases and error recovery scenarios

## Body
Improve test coverage for error handling and edge cases throughout the application.

- [ ] Test all error paths
- [ ] Validate error messages
- [ ] Test recovery scenarios
- [ ] Test invalid input handling
- [ ] Test network failure scenarios

## Acceptance Criteria
- [ ] All error paths tested
- [ ] Error messages validated
- [ ] Recovery scenarios work
- [ ] Graceful degradation tested

## Priority
High - user experience

## Enhanced Validation System

### Improve YAML Structure Validation Logic
_Labels: validation, enhancement_

Enhance the YAML validation to support comprehensive Kubernetes schema checks.

## Body
The current YAML validation only checks for the presence of basic keys like `apiVersion`, `kind`, and `metadata`. We need to implement more robust validation against the Kubernetes API schema to provide more accurate feedback.

- [ ] Integrate a Kubernetes schema validation library
- [ ] Validate resource types against their official schemas
- [ ] Check for deprecated API versions
- [ ] Provide detailed error messages for validation failures

## Acceptance Criteria
- [ ] YAML validation covers all standard Kubernetes resources
- [ ] Validation errors are specific and actionable
- [ ] The system can handle custom resource definitions (CRDs) gracefully

## Priority
Medium - improves core functionality

### Enhance Command Equivalence Logic
_Labels: validation, enhancement_

Improve the logic for comparing user-provided 'kubectl' commands with expected solutions.

## Body
The current command comparison logic is basic and only normalizes whitespace. It should be enhanced to understand 'kubectl' command structures, including aliases, argument order, and shorthand flags.

- [ ] Parse 'kubectl' commands into a structured format
- [ ] Compare command components (resource, verb, flags) semantically
- [ ] Handle common aliases (e.g., 'po' for 'pods')
- [ ] Ignore non-essential differences in flag order

## Acceptance Criteria
- [ ] Command comparison is robust and flexible
- [ ] Correctly validates a wider range of user inputs
- [ ] The system correctly identifies equivalent but non-identical commands

## Priority
Medium - improves user experience

### Multi-Document YAML Support
_Labels: validation, enhancement_

Support for multi-document YAML files.

## Body
- Handle YAML files with multiple Kubernetes resources
- Parse document separators correctly
- Validate each document independently
- Aggregate validation results

### Advanced Semantic Comparison
_Labels: validation, enhancement_

Improve YAML semantic comparison logic.

## Body
- Improve YAML structure comparison for complex nested objects
- Handle array ordering differences
- Support partial matching for dynamic fields
- Add fuzzy matching for similar values

### Validation Error Quality
_Labels: validation, ux_

Improve the quality of YAML validation errors.

## Body
- Provide more specific and actionable error messages
- Include line numbers in error reports
- Suggest corrections for common mistakes
- Add context-aware hints

### Custom Validation Rules
_Labels: validation, enhancement_

Allow exercises to define custom validation rules.

## Body
- Allow exercises to define custom validation criteria
- Support regex patterns for flexible matching
- Add conditional validation rules
- Enable plugin-based validators

## Developer Experience

### Add Developer Documentation
_Labels: documentation, developer-experience_

Create comprehensive developer documentation to streamline onboarding and contributions.

## Body
To encourage community contributions and make maintenance easier, we need clear documentation for developers. This should cover project setup, architecture, and contribution guidelines.

- [ ] Write a `CONTRIBUTING.md` guide
- [ ] Document the project architecture and module interactions
- [ ] Provide instructions for setting up the development environment
- [ ] Explain the process for running tests and adding new ones

## Acceptance Criteria
- [ ] A clear and comprehensive `CONTRIBUTING.md` exists
- [ ] New developers can set up the project and run tests successfully
- [ ] The documentation is sufficient to guide the addition of new features

## Priority
High - developer experience

### Implement CI/CD Pipeline
_Labels: ci-cd, developer-experience_

Set up a continuous integration and deployment pipeline to automate testing and releases.

## Body
A CI/CD pipeline will improve code quality and development velocity by automating routine tasks. The pipeline should run tests on every pull request and facilitate automated releases.

- [ ] Set up a GitHub Actions workflow
- [ ] Configure the pipeline to run linters and formatters
- [ ] Add a step to run the full test suite
- [ ] Automate building binaries for different platforms
- [ ] (Optional) Set up automated releases to GitHub

## Acceptance Criteria
- [ ] Tests are automatically run for all pull requests
- [ ] The pipeline provides clear feedback on test failures
- [ ] The build process is automated and reliable

## Priority
High - developer experience

### Ensure Cross-Platform Compatibility
_Labels: compatibility, developer-experience_

Verify and ensure that the application builds and runs correctly on Windows, macOS, and Linux.

## Body
The application uses both Python and Rust, which can introduce cross-platform compatibility challenges. We need to test and address any issues to ensure a consistent experience for all users.

- [ ] Test the build process on Windows, macOS, and Linux
- [ ] Verify that all tests pass on each platform
- [ ] Address any platform-specific issues, such as path handling or binary execution
- [ ] Document any platform-specific setup steps

## Acceptance Criteria
- [ ] The application can be successfully built on all three major platforms
- [ ] The test suite passes consistently across platforms
- [ ] Users have a seamless experience regardless of their operating system

## Priority
Medium - improves accessibility

### Automated Test Coverage Reporting
_Labels: developer-experience, ci-cd_

Set up automated test coverage reporting.

## Body
- Integrate codecov.io for coverage tracking
- Add coverage badges to README
- Set up coverage thresholds in CI
- Generate detailed coverage reports

### Pre-commit Hooks
_Labels: developer-experience, tooling_

Implement pre-commit hooks for quality gates.

## Body
- Add linting and formatting validation
- Run tests before commits
- Check for security vulnerabilities
- Validate documentation updates

### Documentation Generation
_Labels: developer-experience, documentation_

Automate generation of project documentation.

## Body
- Auto-generate API docs from docstrings
- Create interactive documentation
- Add code examples to docs
- Set up documentation deployment

### Dependency Management
_Labels: developer-experience, dependencies_

Improve dependency management workflow.

## Body
- Regular security updates
- Compatibility checks across Python versions
- Automated dependency updates
- Vulnerability scanning

## Phase 1: Core Enhancements

Focus on solidifying the core quiz experience and adding high-value features.

### Bug Fixes & Stability
- [x] **Fix Command Validation**: `k get sa` should be equivalent to `kubectl get sa` - RESOLVED ✅
- [x] **Fix YAML Validation API**: Update validation function calls to use new dictionary format - RESOLVED ✅
- [x] **Fix Import Errors**: Resolve `kubelingo_core` import issues in tests - RESOLVED ✅
- [x] **Fix Vim Editor Integration**: Handle KeyboardInterrupt and validation errors properly - RESOLVED ✅

### Difficulty Levels
- [ ] Implement a mechanism to tag questions with difficulty levels (Beginner, Intermediate, Advanced). [#1]
- [ ] Add a command-line flag (`--difficulty`) to let users filter questions. [#2]
- [ ] Adjust scoring or hints based on the selected difficulty. [#3]

### Performance Tracking & History
- [ ] Enhance history tracking to include time taken per question and streaks. [#4]
- [ ] Implement a `kubelingo history` command to show detailed performance analytics. [#5]
- [ ] Visualize progress over time (e.g., ASCII charts in the terminal). [#6]

### Spaced Repetition System (SRS)
- [ ] Integrate an SRS algorithm to prioritize questions the user has previously answered incorrectly. [#7]
- [ ] Automatically schedule questions for review based on performance. [#8]

## Phase 2: Interactive Environments

Bridge the gap between theory and practice by integrating with live Kubernetes clusters.

### Sandbox Integration
- [ ] Finalize integration with a sandbox provider (e.g., a custom Go-based sandbox environment). [#9]
- [ ] Develop a session manager to request, configure, and tear down ephemeral Kubernetes environments for quiz sessions. [#10]
- [ ] Ensure `kubectl` commands are correctly routed to the sandbox cluster. [#11]

### Homelab Integration
- [ ] Add functionality to allow users to use their own homelab cluster. [#12]
- [ ] Implement a configuration flow (`kubelingo config --use-context <my-homelab-context>`) to point KubeLingo to a user-provided kubeconfig context. [#13]
- [ ] Add safety checks and warnings when operating on a non-ephemeral cluster. [#14]

### Command Validation in Live Environments
- [ ] Develop a robust system to capture commands run by the user within the live environment. [#15]
- [ ] Validate the *state* of the cluster after a user's command, rather than just comparing command strings. (e.g., "Was a pod named 'nginx' actually created?"). [#16]

## Phase 3: Advanced Editing and Content

Improve the YAML editing experience and expand the question library.

### CKAD-Level Vim Integration
_Status: Planned. See [Vim Integration Analysis](vim_integration_analysis.md) for details._

#### Foundation
- [ ] **Enhanced Vim Editor**: Extend `VimYamlEditor` with efficiency tracking and command recording. [#55]
- [ ] **Vim Command Trainer**: Create a dedicated module for practicing Vim commands, modal editing, and efficiency patterns. `pyvim` has been integrated as an optional editor. [#56]

#### Realistic Scenarios
- [ ] **CKAD Scenario Engine**: Develop an engine to generate realistic exam scenarios (pods, deployments, troubleshooting). [#57]
- [ ] **`kubectl edit` Simulation**: Implement a workflow to simulate `kubectl edit` and `dry-run` patterns. [#58]

#### Advanced Features
- [ ] **Performance Analytics**: Build a system to analyze Vim usage, generate efficiency reports, and track progress. [#59]
- [ ] **Adaptive Difficulty**: Implement logic to adjust exercise difficulty and time limits based on user performance. [#60]

#### Integration and Polish
- [ ] **Comprehensive Vim Testing**: Add integration tests using a real Vim process and a Vim automation framework. [#61]
- [ ] **Documentation and Guides**: Create Vim quick-reference guides and training materials for CKAD-specific techniques. [#62]

### Real-time YAML Validation
- [ ] Integrate a YAML linter (e.g., `yamllint`) and the Kubernetes OpenAPI schema. [#19]
- [ ] Provide immediate feedback on syntax errors and invalid Kubernetes resource definitions as the user types. [#20]

### Expanded Content & New Question Types
- [ ] Add question packs for CKA and CKS certification topics. [#21]
- [ ] Introduce troubleshooting scenarios where the user must diagnose and fix a broken resource in a live environment. [#22]
- [ ] Add questions about Kubernetes security best practices. [#23]

## Phase 4: Advanced Features

### Enhanced Learning Analytics
- [ ] **Detailed Performance Metrics**: Time per question, accuracy trends, weak topic identification [#24]
- [ ] **Learning Curve Analysis**: Track improvement over time with statistical analysis [#25]
- [ ] **Adaptive Difficulty**: Automatically adjust question difficulty based on performance [#26]
- [ ] **Competency Mapping**: Map performance to specific CKAD exam objectives [#27]

### Development Workflow
- [ ] **Hot Reload for Development**: Automatically reload question data during development [#28]
- [ ] **Question Authoring Tools**: CLI tools for creating and validating new questions [#29]
- [ ] **Bulk Question Import**: Import questions from various formats (CSV, JSON, YAML) [#30]
- [ ] **Question Analytics**: Track which questions are most/least effective [#31]

### Integration Enhancements
- [ ] **IDE Plugins**: VSCode/Vim plugins for in-editor practice [#32]
- [ ] **Kubernetes Dashboard Integration**: Practice directly in K8s web UI [#33]
- [ ] **CI/CD Integration**: Run kubelingo tests in development pipelines [#34]
- [ ] **Slack/Discord Bots**: Team-based practice and competitions [#35]

### Advanced Validation
- [ ] **Multi-Solution Support**: Accept multiple correct answers for open-ended questions [#36]
- [ ] **Partial Credit Scoring**: Grade partially correct YAML with detailed feedback [#37]
- [ ] **Context-Aware Validation**: Validate based on cluster state, not just manifest content [#38]
- [ ] **Security Scanning**: Integrate with tools like Falco for security best practices [#39]

## Phase 5: Ecosystem Integration

### Cloud Provider Specific Features
- [ ] **GCP GKE Integration**: Google Cloud sandbox environments [#40]
- [ ] **Azure AKS Integration**: Azure sandbox environments  [#41]
- [ ] **Multi-Cloud Scenarios**: Practice migrating workloads between providers [#42]
- [ ] **Cloud-Native Tools**: Integration with Helm, Kustomize, ArgoCD [#43]

### Enterprise Features
- [ ] **Team Management**: Multi-user environments with progress tracking [#44]
- [ ] **Custom Branding**: White-label versions for training organizations [#45]
- [ ] **Reporting Dashboard**: Manager/instructor view of team progress [#46]
- [ ] **Integration APIs**: Connect with LMS and HR systems [#47]

## Future Vision & Long-Term Goals

Ideas that are further out on the horizon.

### Web UI / TUI
- [ ] Develop a full-featured Text-based User Interface (TUI) using a library like `rich` or `textual`. [#48]
- [ ] Explore creating a companion web application for a more graphical experience. [#49]

### Custom Question Decks
- [ ] Allow users to write their own questions and answers in a simple format (e.g., JSON or YAML). [#50]
- [ ] Implement functionality to share and download question packs from a central repository or URL. [#51]

### AI-Powered Features
- [ ] Use an LLM to provide dynamic hints or detailed explanations. [#52]
- [ ] Experiment with AI-generated questions for a virtually unlimited question pool. [#53]

### Multiplayer Mode
- [ ] A competitive mode where two or more users race to answer questions correctly. [#54]

