# Architecture Overview

This document outlines the high-level structure and organization of the kubelingo codebase.

```
kubelingo/                            # Main Python package for CLI and core modules
├── __init__.py                        # Package marker
├── __main__.py                        # Console script entrypoint
├── cli.py                             # Main CLI implementation
├── modules/vim_yaml_editor.py         # Vim-based YAML editing engine
├── modules/k8s_quiz.py                # Kubernetes command quiz engine
├── tools/session_manager.py           # CKADStudySession and GoSandbox integration
└── tools/gosandbox_integration/       # Cloud (GoSandbox) helpers

data/                                 # JSON/YAML data separate from code
├── ckad_quiz_data.json    # Standard kubectl command questions
├── yaml_edit_questions.json # YAML editing exercises
└── ckad_exercises_extended.json # Extended CKAD content

scripts/                   # Utility scripts and verification tools
├── merge_quiz_data.py     # Combine & dedupe multiple JSON sources
├── verify_quiz_data.py    # Lint & validate quiz data formatting
└── cross-reference.sh      # Helper for text extraction & reference builds

modules/                   # Deprecated — will be merged into `kubelingo` package
tools/                     # Deprecated — session_manager moved to kubelingo

edit_questions/            # Sample shell-based edit questions
logs/                      # Session logs & history

docs/                      # Project documentation (API ref, architecture)
```  

Key Principles:
1. **Separation of Concerns**: Code, data, and scripts are in distinct directories.  
2. **Modularization**: Core CLI, session management, and YAML editing are separate modules.  
3. **Deprecation Plan**: `modules/` and `tools/` will be removed once all code is migrated.  
4. **Documentation First**: Gaps in API and architecture are documented under `docs/`.  

**Next Steps**:  
- Migrate legacy `cli_quiz.py` functionality into `kubelingo/cli.py`.  
- Implement `cloud_env.py` for EKS cluster and cloud exercises.  
- Add unit tests under a new `tests/` directory.  
- Finalize removal of deprecated directories.  