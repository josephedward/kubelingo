# Roadmap from roadmap.md

## Features

### AI-Extracted Issues from roadmap.md

#### [ ] Ensure deterministic evaluation of `kubectl`/`helm` commands and cluster state
Make sure that the evaluation of `kubectl` and `helm` commands, as well as the cluster state, is consistent and deterministic to ensure accurate validation.

#### [ ] Persist quiz session state to allow resuming
Implement functionality to save the state of a quiz session so that users can resume where they left off.

#### [ ] Enhance end-of-quiz summary with per-question status
Improve the end-of-quiz summary by providing detailed status information for each question attempted during the quiz.

#### [ ] Implement a mechanism to tag questions with difficulty levels
Create a system to categorize questions into difficulty levels (Beginner, Intermediate, Advanced) for better user experience.

#### [ ] Add navigable menu actions to the CLI
Enhance the CLI by adding menu actions such as Open Shell, Check Answer, Next Question, Previous Question, Flag/Unflag, and Exit for improved user interaction.

#### [ ] Persist per-question `ShellResult` transcripts
Store the transcripts of shell sessions for each question in a mapping structure for future reference and evaluation.

#### [ ] Create `evaluate_transcript` helper for replaying recorded sessions
Develop a helper function to replay recorded session transcripts for accurate evaluation and validation.

#### [ ] Implement support for exit_code, contains, regex, and JSONPath matchers
Enhance the system to support various matchers for validating command outputs and cluster states in exercises.

#### [ ] Write unit tests for matcher logic and `evaluate_transcript` functions
Develop unit tests to ensure the correctness and reliability of the matcher logic and transcript evaluation functions.

#### [ ] Integrate AI-based evaluator as an optional `--ai-eval` second-pass
Explore the integration of an AI-based evaluator as an optional feature for evaluating freeform workflows in exercises.

#### [ ] Improve the logic for comparing user-provided 'kubectl' commands with expected solutions
## Background
In the Kubelingo CLI quiz tool, there is a need to enhance the logic for comparing user-provided 'kubectl' commands with expected solutions. The current command comparison logic is basic and only normalizes whitespace, which may not cover all variations in 'kubectl' command structures.

## Scope of Work
The goal is to improve the command comparison logic to understand 'kubectl' command structures comprehensively. This enhancement will involve parsing 'kubectl' commands into a structured format, comparing command components (resource, verb, flags) semantically, handling common aliases, and ignoring non-essential differences in flag order.

## Acceptance Criteria
- The command comparison logic should be robust and flexible, correctly validating a wider range of user inputs.
- The system should identify equivalent but non-identical commands accurately.
- The validation should provide more accurate feedback on user-provided 'kubectl' commands.

## Implementation Outline
1. **Parsing 'kubectl' Commands**:
   - Develop a parser to break down 'kubectl' commands into structured components.
2. **Semantic Comparison**:
   - Compare command components (resource, verb, flags) semantically for equivalence.
3. **Handling Common Aliases**:
   - Implement logic to recognize and handle common aliases in 'kubectl' commands.
4. **Ignoring Non-Essential Differences**:
   - Define rules to ignore non-essential differences in flag order to focus on the core command structure.

## Checklist
- [ ] Develop a parser for 'kubectl' commands
- [ ] Implement semantic comparison of command components
- [ ] Handle common aliases in 'kubectl' commands
- [ ] Define rules to ignore non-essential differences in flag order

Parent issue: #19

#### [ ] Improve YAML structure validation logic
### Background
The current YAML validation logic in the Kubelingo CLI quiz tool focuses on basic key presence checks like `apiVersion`, `kind`, and `metadata`. However, to improve the accuracy and effectiveness of the validation process, it is essential to enhance the validation to include comprehensive checks against the official Kubernetes schema.

### Scope of Work
- Integrate a Kubernetes schema validation library into the existing YAML validation logic.
- Validate Kubernetes resource types against their respective official schemas.
- Include checks for deprecated API versions to ensure compliance with the latest standards.
- Provide detailed and actionable error messages for validation failures to guide users effectively.

### Acceptance Criteria
- The YAML validation process covers all standard Kubernetes resources accurately.
- Validation errors are specific, informative, and actionable for users to understand and correct.
- The system gracefully handles custom resource definitions (CRDs) during the validation process.

### Implementation Outline
1. **Research and Library Integration**
   - Research and select a suitable Kubernetes schema validation library.
   - Integrate the selected library into the Kubelingo CLI project.

2. **Enhanced Validation Logic**
   - Implement logic to validate resource types against official Kubernetes schemas.
   - Include checks for deprecated API versions during validation.

3. **Error Messaging**
   - Enhance error messaging to provide specific details on validation failures.
   - Ensure error messages are actionable and guide users on potential corrections.

### Checklist
- [ ] Research and select a Kubernetes schema validation library.
- [ ] Integrate the selected library into the Kubelingo CLI project.
- [ ] Implement resource type validation against official Kubernetes schemas.
- [ ] Add checks for deprecated API versions during validation.
- [ ] Enhance error messaging to provide detailed and actionable information.

By addressing these tasks, the YAML structure validation logic in the Kubelingo CLI tool will be significantly improved to provide users with more accurate and helpful feedback during quiz exercises.

Parent issue: #19

#### [ ] Implement support for multi-document YAML files
## Issue Description: Implement support for multi-document YAML files

### Background
The current system lacks the capability to handle YAML files containing multiple Kubernetes resources. Support for multi-document YAML files is crucial for users dealing with complex configurations spread across different resource definitions within a single file.

### Scope of Work
- Modify the YAML parsing logic to recognize and process multiple documents within a single YAML file.
- Ensure proper separation and validation of each Kubernetes resource within the multi-document structure.
- Implement aggregation of validation results for all resources in the multi-document YAML file.
- Update the user interface to handle and display results from multi-document YAML validations.

### Acceptance Criteria
- The system can successfully parse and validate multi-document YAML files containing various Kubernetes resources.
- Each resource within a multi-document YAML file is independently validated for correctness.
- Aggregated validation results for all resources in the multi-document YAML file are accurately displayed to the user.
- The user interface reflects the handling of multi-document YAML files clearly and intuitively.

### Implementation Outline
1. Update the YAML parsing module to support multiple document handling.
2. Modify the validation logic to validate each resource individually.
3. Implement aggregation of validation results for all resources in a multi-document YAML.
4. Integrate the updated parsing and validation functionalities into the main system flow.
5. Update the user interface to accommodate the display of results for multi-document YAML files.

### Checklist
- [ ] Update YAML parsing module for multi-document support
- [ ] Modify validation logic for individual resource validation
- [ ] Implement aggregation of validation results
- [ ] Integrate changes into system flow
- [ ] Update user interface for multi-document YAML file handling

Feel free to provide feedback or additional requirements for this task.

Parent issue: #19

#### [ ] Store transcripts under `logs/transcripts/<session_id>/<question_id>.log`
## Background
Currently, the Kubelingo project lacks a standardized approach for storing transcripts of quiz sessions. To enhance auditing capabilities and facilitate replay functionality, it is necessary to implement a structured storage mechanism for transcripts under specific directories based on session and question identifiers.

## Scope of Work
The task involves creating a system to store transcripts in a hierarchical directory structure as follows:
```
logs/
  transcripts/
    <session_id>/
      <question_id>.log
```

## Acceptance Criteria
- Transcripts are stored under `logs/transcripts/<session_id>/<question_id>.log`.
- Each transcript file contains the complete session details, including Vim keystrokes, shell commands, and any interactions.
- Transcripts are stored in a secure and organized manner for easy retrieval and auditing purposes.

## Implementation Outline
1. Create a function to generate unique session identifiers.
2. Develop a method to associate each question with a unique identifier.
3. Implement a logging mechanism to capture session details and write them to the respective transcript files.
4. Ensure the storage location is configurable and adheres to the specified directory structure.
5. Add error handling to manage cases where transcript storage fails.

## Checklist
- [ ] Design a session ID generation algorithm.
- [ ] Establish a mapping between questions and unique identifiers.
- [ ] Implement transcript logging functionality.
- [ ] Configure the storage location and directory structure.
- [ ] Test the storage mechanism under various scenarios.
- [ ] Ensure error handling for storage failures.

By implementing this structured storage mechanism for transcripts, Kubelingo will enhance its logging capabilities and provide a robust foundation for future audit and replay features.

Parent issue: #19

#### [ ] Create `evaluate_transcript` helper to replay recorded session proof-of-execution
## Background
The Kubelingo project aims to enhance the CLI quiz tool by introducing a `evaluate_transcript` helper function to replay recorded session proof-of-execution for evaluation purposes. This feature will allow for deterministic evaluation based on recorded terminal session transcripts, enabling accurate assessment of user interactions and commands.

## Scope of Work
- Develop the `evaluate_transcript` helper function to replay session transcripts for evaluation.
- Ensure accurate replay of recorded terminal sessions for proof-of-execution assessment.
- Implement support for advanced deterministic validation and potentially AI-based evaluation modes.

## Acceptance Criteria
- The `evaluate_transcript` function accurately replays recorded session transcripts.
- The replayed sessions provide a reliable proof-of-execution for evaluation purposes.
- Basic deterministic validation is implemented to check for command correctness and session outcomes.
- Optional: Integration with AI-based evaluator to provide grading for freeform workflows.

## Implementation Outline
1. Design the `evaluate_transcript` function to parse and replay session transcripts.
2. Implement logic to compare expected outcomes with recorded session actions.
3. Integrate basic deterministic validation checks to ensure command accuracy and desired outcomes.
4. Optionally, explore AI-based evaluation integration for grading freeform workflows.

## Checklist
- [ ] Design and implement the `evaluate_transcript` helper function.
- [ ] Develop logic to parse and replay recorded session transcripts accurately.
- [ ] Include basic deterministic validation checks for command correctness and session outcomes.
- [ ] Optional: Investigate AI-based evaluation integration for enhanced grading capabilities.

Parent issue: #19

#### [ ] Persist per-question `ShellResult` transcripts in a `transcripts_by_index` mapping
## Background
In the Kubelingo CLI quiz tool project, there is a need to persist the transcripts of `ShellResult` for each question in a structured manner to enhance the quiz session experience and allow for better review and analysis of user interactions with the shell environment.

## Scope of Work
The task involves implementing a mapping structure called `transcripts_by_index` to store the `ShellResult` transcripts on a per-question basis. This will enable the system to track and manage the shell session data more efficiently, facilitating features like resuming quiz sessions and providing detailed per-question status summaries.

## Acceptance Criteria
- The `transcripts_by_index` mapping should store transcripts for each question's `ShellResult`.
- Each transcript should be associated with the respective question's index or identifier.
- The system should persist the transcripts accurately and consistently across sessions.
- The stored transcripts should be easily accessible for review and analysis purposes.
- The implementation should not impact the existing functionality negatively.

## Implementation Outline
1. Define the structure of the `transcripts_by_index` mapping to store the transcripts.
2. Modify the shell session handling logic to populate and update the transcripts in the mapping.
3. Ensure proper storage and retrieval mechanisms for the transcripts.
4. Implement a mechanism to link the transcripts to specific questions for easy reference.
5. Update relevant components to utilize the stored transcripts for enhancing the quiz session experience.

## Checklist
- [ ] Define the structure of `transcripts_by_index` mapping
- [ ] Modify shell session handling to update transcripts
- [ ] Implement storage and retrieval mechanisms
- [ ] Link transcripts to specific questions
- [ ] Update components to utilize stored transcripts

Feel free to ask for further clarification or details if needed.

Parent issue: #19

#### [ ] Integrate AI-based evaluator to grade freeform workflows via LLM
## Background
In the Kubelingo project roadmap, there is a plan to enhance the session transcript and evaluation process by potentially integrating an AI-based evaluator to grade freeform workflows using a Language Model like LLM. This addition aims to automate the grading process and provide more accurate and consistent feedback to users based on their interactions with the system.

## Scope of Work
The scope of this task includes the following key objectives:
- Record full terminal sessions for audit and replay purposes.
- Implement a deterministic evaluation pipeline based on transcript parsing and sanity checks.
- Explore the integration of an AI-based evaluator, specifically leveraging a Language Model like LLM, to grade freeform workflows.

## Implementation Outline
To achieve the integration of an AI-based evaluator for grading freeform workflows via LLM, the following steps may be considered:
1. **Session Transcript Logging**: Ensure the recording of complete terminal sessions using tools like `script` or PTY logging to capture user interactions accurately.
2. **Transcript Parsing & Storage**: Develop a mechanism to sanitize and store transcripts for further processing and evaluation.
3. **Deterministic Evaluation Pipeline**: Create a pipeline that parses transcripts, performs sanity checks, and generates evaluation results.
4. **AI-Based Evaluator Integration**: Research and integrate an AI-based evaluator, potentially leveraging a Language Model like LLM, to analyze and grade freeform workflows based on the parsed transcripts.

## Acceptance Criteria
- Full terminal sessions are recorded and stored securely.
- Session transcripts are sanitized and available for auditing and replay.
- The deterministic evaluation pipeline accurately assesses user interactions.
- Integration with an AI-based evaluator, such as LLM, successfully grades freeform workflows with high accuracy.
- The system provides detailed feedback and grading for user interactions.

## Checklist
- [ ] Implement session transcript logging functionality.
- [ ] Develop a robust transcript parsing and storage mechanism.
- [ ] Create a deterministic evaluation pipeline for grading user interactions.
- [ ] Investigate and integrate an AI-based evaluator, potentially LLM, for accurate grading.
- [ ] Test the end-to-end functionality to ensure accurate evaluation and grading.
- [ ] Update documentation to reflect the new AI-based evaluation feature.

Feel free to adjust or expand on these steps based on the specific requirements and constraints of the Kubelingo project.

Parent issue: #19

#### [ ] Record full terminal session using `script` or PTY logging
## Background
In the context of the Kubelingo CLI quiz tool, there is a need to enhance the session logging and history tracking feature by recording the full terminal session. This includes capturing Vim keystrokes and shell commands for auditability and replay purposes. The recording of the entire session will provide a comprehensive view of user interactions during quiz sessions, aiding in debugging, analysis, and improving the overall user experience.

## Scope of Work
The task involves implementing a mechanism to record the complete terminal session using either the `script` command or PTY (Pseudo-Terminal) logging. The recorded session should include all inputs and outputs, including user commands, responses, Vim interactions, and any other terminal activities that occur during a quiz session. The recorded data should be stored securely and sanitized for privacy considerations.

### Implementation Details
- Utilize the `script` command or implement PTY logging to capture the terminal session.
- Include support for recording Vim keystrokes and interactions.
- Sanitize and store the recorded sessions securely for audit and replay purposes.

## Acceptance Criteria
- The system can record the full terminal session accurately, capturing all user interactions and outputs.
- Vim keystrokes and shell commands are included in the recorded session.
- The recorded sessions are stored securely and can be accessed for audit and replay purposes.
- Ensure the privacy and security of sensitive information within the recorded sessions.
- Validate the accuracy and completeness of the recorded terminal sessions.

## Checklist
- [ ] Implement terminal session recording using `script` or PTY logging.
- [ ] Capture Vim keystrokes and interactions during the session.
- [ ] Securely store the recorded sessions for audit and replay.
- [ ] Ensure proper sanitization of recorded data.
- [ ] Validate the accuracy and completeness of the recorded terminal sessions.

Parent issue: #19

### build(deps): Bump pyo3 from 0.21.2 to 0.24.1
[![Dependabot compatibility score](https://dependabot-badges.githubapp.com/badges/compatibility_score?dependency-name=pyo3&package-manager=cargo&previous-version=0.21.2&new-version=0.24.1)](https://docs.github.com/en/github/managing-security-vulnerabilities/about-dependabot-security-updates#about-compatibility-scores)

Dependabot will resolve any conflicts with this PR as long as you don't alter it yourself. You can also trigger a rebase manually by commenting `@dependabot rebase`.

[//]: # (dependabot-automerge-start)
[//]: # (dependabot-automerge-end)

---

<details>
<summary>Dependabot commands and options</summary>
<br />

You can trigger Dependabot actions by commenting on this PR:
- `@dependabot rebase` will rebase this PR
- `@dependabot recreate` will recreate this PR, overwriting any edits that have been made to it
- `@dependabot merge` will merge this PR after your CI passes on it
- `@dependabot squash and merge` will squash and merge this PR after your CI passes on it
- `@dependabot cancel merge` will cancel a previously requested merge and block automerging
- `@dependabot reopen` will reopen this PR if it is closed
- `@dependabot close` will close this PR and stop Dependabot recreating it. You can achieve the same result by closing it manually
- `@dependabot show <dependency name> ignore conditions` will show all of the ignore conditions of the specified dependency
- `@dependabot ignore this major version` will close this PR and stop Dependabot creating any more for this major version (unless you reopen the PR or upgrade to it yourself)
- `@dependabot ignore this minor version` will close this PR and stop Dependabot creating any more for this minor version (unless you reopen the PR or upgrade to it yourself)
- `@dependabot ignore this dependency` will close this PR and stop Dependabot creating any more for this dependency (unless you reopen the PR or upgrade to it yourself)
You can disable automated security fix PRs for this repo from the [Security Alerts page](https://github.com/josephedward/kubelingo/network/alerts).

</details>
Labels: dependencies, rust

### Multiplayer Mode
## Background
Our project currently offers a single-player quiz mode where users can answer questions at their own pace. To increase user engagement and provide a new interactive experience, we want to introduce a multiplayer mode. In this mode, two or more users can compete against each other by racing to answer questions correctly.

## Summary
Implement a competitive multiplayer mode where users can play against each other in real-time quizzes.

## Acceptance Criteria
- [ ] Users can create or join a multiplayer game session.
- [ ] Once the game starts, users are presented with the same set of questions simultaneously.
- [ ] The user who answers a question correctly and faster earns points.
- [ ] The game ends after all questions are answered, and the user with the highest score wins.
- [ ] Users can view the leaderboard to see their ranking during the game.
- [ ] Users should receive appropriate feedback on their answers and performance.

## Implementation Notes
- Utilize websockets for real-time communication between players.
- Implement a matchmaking system to pair users for multiplayer games.
- Update the UI to display both the questions and the leaderboard during gameplay.
- Ensure fairness by synchronizing the question presentation for all players.
- Implement a scoring system to track and display points earned by each player.

### AI-Powered Features
## Background
Implementing AI-powered features in our software can greatly enhance user experience and provide valuable assistance. Leveraging Language Model (LLM) technology allows us to offer dynamic hints and detailed explanations to users, improving their understanding of the application. Additionally, generating questions using AI can create a virtually unlimited question pool, enhancing the educational aspect of our software.

## Summary
This GitHub issue aims to implement two AI-powered features:
1. Using an LLM to provide dynamic hints or detailed explanations.
2. Experimenting with AI-generated questions for a virtually unlimited question pool.

## Acceptance Criteria
- [ ] Integrate a Language Model (LLM) to provide dynamic hints or detailed explanations.
- [ ] Implement AI-generated questions to expand the question pool.
- [ ] Ensure the AI-powered features are intuitive and enhance user experience.
- [ ] Conduct thorough testing to validate the accuracy and effectiveness of the AI-generated content.

## Implementation Notes
- Research and select a suitable Language Model (LLM) for providing hints and explanations.
- Develop a mechanism to trigger the LLM for specific user interactions.
- Create a pipeline to generate AI-driven questions and add them to the question pool.
- Implement a user-friendly interface for users to access the AI-powered features.
- Monitor and evaluate the performance of the AI features, collecting feedback for continuous improvement.

### Custom Question Decks
### Background
Currently, our question deck feature only includes predefined question sets, limiting the flexibility for users to create their own custom question decks. To enhance user experience and engagement, we want to introduce the ability for users to write and share their own question decks in a simple format, as well as download question packs from a central repository.

### Summary
This GitHub issue aims to implement the functionality for users to create custom question decks and share/download question packs. This will empower users to personalize their learning experience and contribute to the platform's community-driven content.

### Acceptance Criteria
- [ ] Allow users to write questions and answers in a simple format (e.g., JSON or YAML).
- [ ] Implement functionality to share and download question packs from a central repository or URL.

### Implementation Notes
- Create a user-friendly interface for users to input their own questions and answers.
- Develop parsers to handle question decks in JSON or YAML formats.
- Implement APIs to allow users to share their question decks and download question packs.
- Ensure security measures are in place to prevent malicious content in shared question packs.
- Provide clear documentation and guidelines for users on how to create and share custom question decks.

### Web UI / TUI
## Background
Our project currently relies on a command-line interface (CLI) for user interaction. To enhance user experience and accessibility, we are considering the development of a Text-based User Interface (TUI) using libraries like `rich` or `textual`. Additionally, creating a companion web application could provide users with a more graphical and interactive experience.

## Summary
This issue aims to explore the implementation of a TUI using `rich` or `textual` and the development of a companion web application to complement our existing CLI.

## Acceptance Criteria
- [ ] Develop a full-featured TUI using `rich` or `textual` that provides an intuitive and user-friendly interface.
- [ ] The TUI should support essential functionality currently available in the CLI.
- [ ] Ensure seamless integration between the TUI and existing project components.
- [ ] Explore and implement user customization options for the TUI interface.
- [ ] Create a companion web application that enhances the user experience through graphical elements and interactivity.
- [ ] The web application should be responsive and compatible with various devices and browsers.

## Implementation Notes
- Research and compare the `rich` and `textual` libraries to determine the most suitable choice for the TUI implementation.
- Identify key features and functionalities from the existing CLI to be integrated into the TUI.
- Design a user-friendly TUI interface with clear navigation and visual elements.
- Ensure proper error handling and feedback mechanisms in the TUI to guide users effectively.
- Utilize modern web development technologies and frameworks for building the companion web application.
- Implement responsive design principles to ensure optimal user experience across different devices.
- Explore interactive elements such as charts, graphs, or animations to enhance the web application's visual appeal.

Let me know if you need any further details or modifications to the GitHub issue description!

### Expanded Content & New Question Types
## Background
As we aim to enhance our platform and provide more comprehensive learning resources for users preparing for CKA and CKS certifications, we are planning to expand the content and introduce new question types to improve the overall learning experience. This initiative will include adding question packs specific to CKA and CKS certification topics, incorporating troubleshooting scenarios in live environments, and integrating questions related to Kubernetes security best practices.

## Summary
The goal of this project is to expand the content offerings on our platform by introducing question packs tailored for CKA and CKS certification topics, incorporating real-world troubleshooting scenarios for users to practice diagnosing and fixing issues in live environments, and adding questions that focus on Kubernetes security best practices.

## Acceptance Criteria
- [ ] Question packs for CKA and CKS certification topics are added to the platform.
- [ ] Troubleshooting scenarios are introduced where users must diagnose and fix broken resources in a live environment.
- [ ] Questions covering Kubernetes security best practices are included in the question sets.

## Implementation Notes
- Research and curate question sets specific to CKA and CKS certification topics.
- Develop realistic troubleshooting scenarios that simulate issues in a live Kubernetes environment.
- Create questions that address various aspects of Kubernetes security best practices.
- Ensure questions are clear, concise, and aligned with the learning objectives for the certifications.
- Test the new question types and content extensively to verify accuracy and effectiveness.
- Roll out the expanded content and new question types in a phased approach to gather feedback from users and make any necessary adjustments.

### Real-time YAML Validation
## Background
When working with Kubernetes configurations in YAML format, it's crucial to ensure that the syntax is correct and the resource definitions are valid. However, manual validation can be time-consuming and error-prone. To streamline this process, we propose implementing real-time YAML validation using a YAML linter (such as `yamllint`) and the Kubernetes OpenAPI schema.

## Summary
The goal of this issue is to integrate a YAML linter with the Kubernetes OpenAPI schema to provide users with immediate feedback on syntax errors and invalid Kubernetes resource definitions as they type in their YAML files.

### Acceptance Criteria
- [ ] Integrate a YAML linter (e.g., `yamllint`) with the project.
- [ ] Implement real-time validation of the YAML files against the Kubernetes OpenAPI schema.
- [ ] Display immediate feedback to the user for syntax errors and invalid resource definitions.
- [ ] Ensure the validation process is lightweight and does not impact the user's editing experience.

### Implementation Notes
- Start by integrating the selected YAML linter (e.g., `yamllint`) into the project's build process.
- Utilize the Kubernetes OpenAPI schema to validate the structure and content of Kubernetes resource definitions in the YAML files.
- Implement a mechanism to trigger validation as the user types or saves the file.
- Display error messages or warnings directly within the editor interface to provide real-time feedback to the user.
- Optimize the validation process to ensure minimal performance overhead.
- Consider providing customization options for users to configure the validation rules or ignore specific warnings.

Let's work together to enhance the user experience by implementing real-time YAML validation for Kubernetes configurations.

### Vim Mode for YAML Editing
### Background
Currently, our YAML editing exercises lack a seamless integration with a terminal-based text editor that provides Vim keybindings. This makes the editing experience less efficient for users who are accustomed to Vim commands. To enhance the user experience and improve productivity, we need to implement a Vim mode for YAML editing.

### Summary
The goal of this issue is to integrate a terminal-based text editor with Vim keybindings for the YAML editing exercises. This will allow users familiar with Vim to leverage their expertise while working on YAML files within our platform.

### Acceptance Criteria
- [ ] Select and integrate a terminal-based text editor that supports Vim keybindings.
- [ ] Ensure the editor is accessible within the platform for YAML editing exercises.
- [ ] Test the functionality to confirm that Vim keybindings are fully functional for editing YAML files.
- [ ] Document the usage instructions for users who want to utilize the Vim mode during YAML editing.

### Implementation Notes
To achieve the Vim mode for YAML editing, we can consider the following approaches:
1. **Integrate existing tools:** Explore tools like `pyvim` that provide a Vim-like experience within a terminal-based text editor. Evaluate their compatibility with YAML editing requirements.
   
2. **Custom implementation:** If existing tools do not meet our needs, consider creating a temporary file and launching the user's default `$EDITOR` with Vim keybindings enabled. This approach can provide a more tailored Vim experience for YAML editing exercises.

3. **User guidance:** Provide clear instructions within the platform on how users can enable and utilize the Vim mode for YAML editing. This will ensure that users are aware of this feature and can make the most of it during their exercises.

By implementing a Vim mode for YAML editing, we aim to enhance the user experience and cater to users who prefer Vim keybindings for text editing tasks.

### Command Validation in Live Environments
## Issue: Command Validation in Live Environments

### Background
In live environments, it is crucial to ensure that commands executed by users produce the intended changes and do not cause unexpected issues. Currently, we are lacking a robust system to validate the effects of user commands beyond simply comparing the command strings. This issue aims to develop a mechanism to capture and validate the state of the cluster post-command execution for better transparency and error detection.

### Summary
Implementing a system to capture and validate user commands in live environments will enhance the reliability and stability of the cluster by ensuring that commands have the desired impact as intended.

### Acceptance Criteria
- [ ] Develop a system to capture commands executed by users within the live environment.
- [ ] Enhance validation by checking the actual state of the cluster post-command execution.
- [ ] Implement checks such as verifying if resources (e.g., pods, services) were created, modified, or deleted as expected.
- [ ] Ensure that the validation system provides clear feedback to users on the outcome of their commands.
- [ ] Conduct thorough testing to validate the accuracy and efficiency of the command validation mechanism.

### Implementation Notes
- Utilize event-driven architecture to capture user commands in real-time without impacting performance.
- Implement a monitoring component to track changes in the cluster's state post-command execution.
- Integrate with existing logging and monitoring tools to provide detailed insights into the effects of user commands.
- Consider incorporating machine learning algorithms to predict potential issues based on historical data.
- Document the validation process and results to aid in troubleshooting and auditing activities.

This issue will involve collaboration across teams to ensure seamless integration and efficient validation of user commands in the live environment.

### Homelab Integration
## Issue: Homelab Integration

### Background
Currently, KubeLingo only supports interacting with cloud-based Kubernetes clusters. However, many users also have their own homelab setups that they would like to use with KubeLingo. This issue aims to enhance KubeLingo by adding support for users to utilize their own homelab clusters.

### Summary
This issue involves implementing the necessary functionality to allow users to seamlessly integrate their homelab cluster with KubeLingo. Users should be able to specify their homelab kubeconfig context, perform operations on their homelab cluster, and receive appropriate warnings when working on a non-ephemeral cluster.

### Acceptance Criteria
- [ ] Add a new command `kubelingo config --use-context <my-homelab-context>` to set the kubeconfig context to a user-provided homelab cluster.
- [ ] Ensure that KubeLingo can connect to and operate on the specified homelab cluster successfully.
- [ ] Implement safety checks to warn users when attempting operations that could impact non-ephemeral homelab clusters.
- [ ] Update documentation to include instructions on configuring and using homelab clusters with KubeLingo.

### Implementation Notes
- Modify the existing configuration logic to handle homelab kubeconfig contexts.
- Validate user-provided inputs to prevent potential errors.
- Integrate safety checks into relevant operations to avoid unintended consequences on homelab clusters.
- Update the CLI interface and documentation to reflect the new homelab integration feature.

Once implemented, this enhancement will offer users the flexibility to leverage their homelab clusters with KubeLingo, expanding the tool's usability and appeal to a broader audience.

### Sandbox Integration
## Background
Currently, our application lacks a sandbox integration feature, which is essential for providing a secure and isolated environment for quiz sessions. To address this need, we aim to integrate with a sandbox provider, such as a custom Go-based sandbox environment. This integration will allow us to develop a session manager that can request, configure, and tear down ephemeral Kubernetes environments to host quiz sessions securely.

## Summary
The goal of this issue is to finalize the integration with a sandbox provider, develop a session manager for managing Kubernetes environments, and ensure that `kubectl` commands are correctly routed to the sandbox cluster. This will enable us to offer a safe and reliable environment for conducting quiz sessions.

## Acceptance Criteria
- [ ] Integration with a sandbox provider (e.g., custom Go-based sandbox environment) is successfully finalized.
- [ ] A session manager is developed to request, configure, and tear down ephemeral Kubernetes environments for quiz sessions.
- [ ] `kubectl` commands are correctly routed to the sandbox cluster.

## Implementation Notes
- Research and select a suitable sandbox provider for integration.
- Implement the necessary APIs and interfaces to interact with the sandbox provider.
- Develop the session manager module to handle the lifecycle of Kubernetes environments.
- Ensure proper routing of `kubectl` commands to the sandbox cluster.
- Test the integration thoroughly to validate the functionality and security of the sandbox environment.
- Document the integration process and usage instructions for future reference.

### Spaced Repetition System (SRS)
## Background
Spaced Repetition System (SRS) is a learning technique that incorporates increasing intervals of time between subsequent review of material to exploit the psychological spacing effect. This approach aims to enhance long-term retention of information and improve learning efficiency.

## Summary
In this issue, we aim to enhance our learning platform by integrating an SRS algorithm. The system will prioritize questions that the user has previously answered incorrectly and automatically schedule questions for review based on the user's performance.

## Acceptance Criteria
- [ ] Integrate an SRS algorithm into the platform.
- [ ] Prioritize questions that the user has answered incorrectly.
- [ ] Automatically schedule questions for review based on user performance.

## Implementation Notes
- Research and select a suitable SRS algorithm that fits the platform's requirements.
- Implement the algorithm to prioritize questions based on previous incorrect answers.
- Develop a mechanism to automatically schedule questions for review according to user performance.
- Ensure seamless integration with the existing platform functionalities.
- Perform thorough testing to validate the effectiveness of the SRS integration.
- Document the SRS algorithm implementation for future reference and maintenance.

### Performance Tracking & History
## Background
Currently, our system lacks detailed performance tracking and history features for users. This makes it difficult for users to monitor their progress and identify areas for improvement. Enhancing these capabilities will provide valuable insights for users to optimize their learning experience.

## Summary
This issue aims to improve performance tracking and history by introducing new features such as time tracking per question, streaks, and a dedicated command for viewing detailed performance analytics. Additionally, we aim to enhance user experience by visualizing progress over time with ASCII charts in the terminal.

## Acceptance Criteria
- [ ] Enhance history tracking to include the time taken per question and streaks.
- [ ] Implement a `kubelingo history` command to display detailed performance analytics.
- [ ] Visualize progress over time, allowing users to track their performance through ASCII charts in the terminal.

## Implementation Notes
- Update the data model to include fields for tracking time taken per question and streaks.
- Implement the `kubelingo history` command, which retrieves and displays detailed performance analytics from the user's history.
- Develop a visualization module to generate ASCII charts representing user progress over time.
- Ensure the visualization module is integrated seamlessly into the existing user interface for easy access.

By completing these tasks, users will have an improved experience with enhanced performance tracking and history features, empowering them to track their progress effectively and make informed decisions to enhance their learning journey.

### Difficulty Levels
## Background
As our platform grows, we aim to provide a better user experience for learners at various levels of expertise. Introducing difficulty levels for questions can help users find suitable challenges and enhance their learning journey.

## Summary
This issue addresses the implementation of a mechanism to tag questions with difficulty levels (Beginner, Intermediate, Advanced) and introduces a command-line flag (`--difficulty`) to allow users to filter questions based on their preferred difficulty level. Additionally, scoring and hints will be adjusted dynamically based on the selected difficulty, providing users with tailored support.

## Acceptance Criteria
- [ ] Implement a tagging system for questions with difficulty levels (Beginner, Intermediate, Advanced).
- [ ] Introduce a `--difficulty` command-line flag to filter questions based on the selected difficulty level.
- [ ] Adjust scoring and hints to reflect the chosen difficulty level for each question.

## Implementation Notes
- Create an enumeration for difficulty levels (Beginner, Intermediate, Advanced) to standardize tagging.
- Update the question model to include a field for storing the difficulty level.
- Modify the question retrieval mechanism to support filtering by difficulty level.
- Implement logic to adjust scoring and hint availability based on the selected difficulty level.
- Update user interfaces to display difficulty levels and provide filtering options.

Once implemented, this feature will enhance user engagement and satisfaction by offering personalized learning experiences tailored to their skill level.

### Future Vision & Long-Term Goals
## Background
As we look towards the future, we envision expanding the capabilities of our current application to provide a more immersive and dynamic user experience. The following ideas represent our long-term goals for enhancing the functionality and appeal of the application.

## Summary
The future vision and long-term goals for the application include implementing a Text-based User Interface (TUI), enabling users to create custom question decks, incorporating AI-powered features, and introducing a multiplayer mode for competitive gameplay.

## Acceptance Criteria
- [ ] Develop a full-featured Text-based User Interface (TUI) using a library like `rich` or `textual`.
- [ ] Explore creating a companion web application for a more graphical experience.
- [ ] Allow users to write their own questions and answers in a simple format (e.g., JSON or YAML).
- [ ] Implement functionality to share and download question packs from a central repository or URL.
- [ ] Use a Language Model (LLM) to provide dynamic hints or detailed explanations.
- [ ] Experiment with AI-generated questions for a virtually unlimited question pool.
- [ ] Implement a multiplayer mode where two or more users can race to answer questions correctly.

## Implementation Notes
- Consider the compatibility and usability of the Text-based User Interface (TUI) across different platforms.
- Design a user-friendly interface for creating and sharing custom question decks.
- Integrate AI technologies carefully to enhance the user experience without compromising the integrity of the questions and answers.
- Implement robust multiplayer functionality to ensure smooth and engaging gameplay for multiple users simultaneously.

These long-term goals represent our commitment to continuous improvement and innovation, providing our users with a dynamic and engaging experience.

### Phase 3: Advanced Editing and Content
### Background:
As we progress to Phase 3 of our project, we aim to enhance the user experience in YAML editing and enrich our question library to cover advanced topics in Kubernetes.

### Summary:
This phase focuses on implementing Vim mode for YAML editing, real-time YAML validation with feedback, and expanding the content with new question types related to CKA and CKS certification topics, troubleshooting scenarios, and Kubernetes security best practices.

### Acceptance Criteria:
- [ ] **Vim Mode for YAML Editing:**
    - [ ] Integrate a terminal-based text editor with Vim keybindings for YAML editing.
    - [ ] Explore options like `pyvim` or creating a temporary file and launching the user's `$EDITOR`.
- [ ] **Real-time YAML Validation:**
    - [ ] Integrate a YAML linter (e.g., `yamllint`) and the Kubernetes OpenAPI schema.
    - [ ] Provide immediate feedback on syntax errors and invalid Kubernetes resource definitions as the user types.
- [ ] **Expanded Content & New Question Types:**
    - [ ] Add question packs for CKA and CKS certification topics.
    - [ ] Introduce troubleshooting scenarios for diagnosing and fixing broken resources in a live environment.
    - [ ] Include questions about Kubernetes security best practices.

### Implementation Notes:
- For Vim mode integration, consider the user experience and ensure seamless switching between regular editing and Vim mode.
- Utilize `yamllint` for real-time validation and explore ways to efficiently incorporate the Kubernetes OpenAPI schema for enhanced accuracy.
- Develop engaging question packs for CKA and CKS certification topics by collaborating with subject matter experts.
- Create realistic troubleshooting scenarios to simulate real-world challenges and provide valuable learning experiences for users.
- Research and compile best practices related to Kubernetes security to craft insightful and educational questions for users.

Feel free to discuss any design decisions or challenges that arise during the implementation process. Let's work together to enhance our platform's capabilities in YAML editing and content diversity.

### Phase 2: Interactive Environments
### Background
To enhance the learning experience and provide hands-on practice for users, we aim to implement Phase 2: Interactive Environments in KubeLingo. This phase focuses on bridging the gap between theoretical knowledge and practical application by enabling interaction with live Kubernetes clusters.

### Summary
In Phase 2, we will integrate KubeLingo with live Kubernetes clusters to allow users to work in real-world environments. This will involve sandbox integration for quiz sessions, homelab cluster support, and developing a system for validating user commands in live environments.

### Acceptance Criteria
- [ ] **Sandbox Integration:**
    - [ ] Finalize integration with a sandbox provider (e.g., a custom Go-based sandbox environment).
    - [ ] Develop a session manager to request, configure, and tear down ephemeral Kubernetes environments for quiz sessions.
    - [ ] Ensure `kubectl` commands are correctly routed to the sandbox cluster.

- [ ] **Homelab Integration:**
    - [ ] Add functionality to allow users to use their own homelab cluster.
    - [ ] Implement a configuration flow (`kubelingo config --use-context <my-homelab-context>`) to point KubeLingo to a user-provided kubeconfig context.
    - [ ] Add safety checks and warnings when operating on a non-ephemeral cluster.

- [ ] **Command Validation in Live Environments:**
    - [ ] Develop a robust system to capture commands run by the user within the live environment.
    - [ ] Validate the *state* of the cluster after a user's command, rather than just comparing command strings. (e.g., "Was a pod named 'nginx' actually created?").

### Implementation Notes
- For sandbox integration, consider using a custom Go-based sandbox environment for flexibility and control.
- Develop a session manager that can efficiently handle the lifecycle of ephemeral Kubernetes environments for quiz sessions.
- Ensure proper routing of `kubectl` commands to the sandbox cluster to provide a seamless user experience.
- When implementing homelab integration, prioritize user-friendly configuration flows and safety checks to prevent accidental changes to non-ephemeral clusters.
- Design a system for capturing and validating user commands in live environments, focusing on verifying the actual state of the cluster post-command execution.

Let me know if you need further details or have any questions regarding this phase implementation.

### Phase 1: Core Enhancements
### Background
As we continue to enhance the quiz experience in Kubelingo, it's crucial to focus on solidifying the core functionalities and introducing high-value features that improve user engagement and learning outcomes.

### Summary
This phase aims to implement key enhancements in the core quiz experience, including the introduction of difficulty levels for questions, performance tracking and history features, and integration of a Spaced Repetition System (SRS) to optimize learning retention.

### Acceptance Criteria
- [ ] **Difficulty Levels:**
    - [ ] Questions can be tagged with difficulty levels (Beginner, Intermediate, Advanced).
    - [ ] Users can filter questions using the `--difficulty` command-line flag.
    - [ ] Scoring and hints adjust dynamically based on the selected difficulty level.

- [ ] **Performance Tracking & History:**
    - [ ] Time taken per question and streaks are recorded in the history tracking.
    - [ ] A `kubelingo history` command displays detailed performance analytics.
    - [ ] Progress over time is visualized, possibly through ASCII charts in the terminal.

- [ ] **Spaced Repetition System (SRS):**
    - [ ] An SRS algorithm prioritizes questions the user has answered incorrectly.
    - [ ] Questions are automatically scheduled for review based on user performance.

### Implementation Notes
- Difficulty Levels:
  - Utilize a tagging system to associate questions with difficulty levels.
  - Implement logic to adjust scoring and hint availability based on the selected difficulty.

- Performance Tracking & History:
  - Enhance existing history tracking functionality to capture time taken per question and streak information.
  - Develop a dedicated command (`kubelingo history`) to display performance analytics.
  - Consider using ASCII charts or other visualization techniques for showcasing progress.

- Spaced Repetition System (SRS):
  - Integrate an SRS algorithm to prioritize questions based on user performance.
  - Implement a scheduling mechanism to automate question review based on the SRS algorithm's recommendations.

By implementing these core enhancements, we aim to provide users with a more personalized and effective learning experience in Kubelingo.
