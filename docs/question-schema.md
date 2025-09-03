# Question Schema Definition

This document defines the canonical schema for all Kubelingo questions.  Every question must adhere to the following fields.

Required Fields:

| Field        | Type    | Description                                              |
|--------------|---------|----------------------------------------------------------|
| id           | string  | Unique identifier for the question                       |
| topic        | string  | Topic or module name (matches the filename without .yaml)|
| question     | string  | The prompt text presented to the user                    |
| requirements | mapping | Key→value map of the answer properties to validate against |
| source       | string  | URL or reference for the canonical source/documentation  |

Optional Fields:

| Field      | Type    | Description                                         |
|------------|---------|-----------------------------------------------------|
| difficulty | string  | Difficulty level (e.g. "beginner", "intermediate", "advanced") |

Notes:
- The `requirements` mapping encodes exactly what the user’s answer (command or manifest) must contain.  For example:
  
  ```yaml
  requirements:
    kind: Pod
    metadata.name: web-server
    spec.containers[0].image: nginx:1.20
  ```
  
- No other top‐level fields (e.g. `suggestions`, `success_criteria`, `hints`, `scenario_context`, `expected_resources`) are permitted in question YAML.
  
All question files under `questions/*.yaml` must list their questions under a top‐level `questions:` sequence.  Each entry in that sequence must follow this schema exactly.