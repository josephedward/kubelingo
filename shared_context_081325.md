# Bug Report and Fix Plan - 2025-08-13

## Bug Description

When running the `kubelingo` CLI, the application crashes with a `NameError`.

**Traceback:**
```
Traceback (most recent call last):
  File "/Users/user/.pyenv/versions/3.11.0/bin/kubelingo", line 3, in <module>
    from kubelingo.cli import main
  File "/Users/user/Documents/GitHub/kubelingo/kubelingo/cli.py", line 44, in <module>
    from kubelingo.modules.kubernetes.study_mode import KubernetesStudyMode
  File "/Users/user/Documents/GitHub/kubelingo/kubelingo/modules/kubernetes/study_mode.py", line 59, in <module>
    class KubernetesStudyMode:
  File "/Users/user/Documents/GitHub/kubelingo/kubelingo/modules/kubernetes/study_mode.py", line 244, in KubernetesStudyMode
    def _run_drill_menu(self, category: QuestionCategory):
                                        ^^^^^^^^^^^^^^^^
NameError: name 'QuestionCategory' is not defined
```

The error occurs in `kubelingo/modules/kubernetes/study_mode.py` because the type hint `QuestionCategory` is used in the `_run_drill_menu` method signature without being imported.

## Fix Plan

The `QuestionCategory` enum is defined in `kubelingo/question.py`. To fix this bug, I will add `QuestionCategory` to the existing import from `kubelingo.question` in `kubelingo/modules/kubernetes/study_mode.py`.

**File to modify:** `kubelingo/modules/kubernetes/study_mode.py`

**Change:**
```python
# Before
from kubelingo.question import Question, QuestionSubject

# After
from kubelingo.question import Question, QuestionCategory, QuestionSubject
```
This will resolve the `NameError` and allow the application to run correctly.
