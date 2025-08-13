"""
Loader for YAML-based question files.
"""
import os
try:
    import yaml
except ImportError:
    yaml = None
from typing import List
from kubelingo.modules.base.loader import BaseLoader
from kubelingo.question import Question, ValidationStep
from kubelingo.utils.config import QUESTION_DIRS
from typing import Dict, Optional


class YAMLLoader(BaseLoader):
    """Discovers and parses YAML question modules."""

    def _infer_subject_matter(self, item: Dict) -> Optional[QuestionSubject]:
        """Infers the QuestionSubject from the question's category and prompt."""
        category = (item.get('category') or (item.get('metadata') or {}).get('category') or "").lower()
        prompt = (item.get('prompt') or item.get('question') or "").lower()

        # Specific keywords in prompt take precedence
        if 'readinessprobe' in prompt or 'readiness probe' in prompt or 'livenessprobe' in prompt or 'liveness probe' in prompt:
            return QuestionSubject.PROBES_HEALTH
        if 'resourcequota' in prompt or 'limitrange' in prompt or ('requests' in prompt and 'limits' in prompt):
            return QuestionSubject.RESOURCE_MANAGEMENT
        if 'serviceaccount' in prompt or 'service account' in prompt:
            return QuestionSubject.SERVICE_ACCOUNTS
        if 'job' in prompt or 'cronjob' in prompt:
            return QuestionSubject.JOBS_CRONJOBS
        if 'persistentvolume' in prompt or 'pvc' in prompt or 'storageclass' in prompt:
            return QuestionSubject.PERSISTENCE
        if 'service ' in prompt and 'serviceaccount' not in prompt:
            return QuestionSubject.SERVICES
        if 'ingress' in prompt:
            return QuestionSubject.INGRESS_ROUTING
        if 'label' in prompt or 'annotation' in prompt or 'selector' in prompt:
            return QuestionSubject.LABELS_SELECTORS
        if 'imperative' in prompt or 'declarative' in prompt or 'kubectl create' in prompt or 'kubectl apply' in prompt:
            return QuestionSubject.IMPERATIVE_DECLARATIVE

        # Category-based mapping
        if 'helm' in category:
            return QuestionSubject.HELM
        if 'configmap' in category or 'configmap' in prompt:
            return QuestionSubject.APP_CONFIGURATION
        if 'secret' in category or 'secret' in prompt:
            return QuestionSubject.SECURITY_BASICS
        if 'namespace' in category:
            return QuestionSubject.NAMESPACES_CONTEXTS
        if 'shell setup' in category or 'vim' in category or 'alias' in category:
            return QuestionSubject.LINUX_SYNTAX
        if 'resource reference' in category:
            return QuestionSubject.API_DISCOVERY_DOCS
        if 'deployment' in category or 'pod' in category or 'workload' in category or 'yaml authoring' in category:
            return QuestionSubject.CORE_WORKLOADS

        # Default for common operations
        if 'kubectl' in category or 'command' in category:
            return QuestionSubject.IMPERATIVE_DECLARATIVE

        return None

    def discover(self) -> List[str]:
        """Discovers YAML files in all configured question directories, including 'yaml'."""
        paths: List[str] = []
        # Use a set to handle duplicates gracefully
        search_dirs = set(QUESTION_DIRS)
        search_dirs.add('yaml')

        for directory in search_dirs:
            if not directory or not os.path.isdir(directory):
                continue

            for root, _, files in os.walk(directory):
                for fname in files:
                    if fname.endswith(('.yaml', '.yml')):
                        # Resolve to absolute path to prevent duplicates from relative/absolute paths
                        full_path = os.path.abspath(os.path.join(root, fname))
                        paths.append(full_path)

        return sorted(list(set(paths)))

    def load_file(self, path: str) -> List[Question]:
        # Load and normalize YAML file into Question objects
        if yaml is None:
            # PyYAML is required to load YAML quiz files
            return []
        # Load file content, strip any leading non-YAML docstrings before '---'
        with open(path, encoding='utf-8') as f:
            content = f.read()
        # If Python-style docstring or other preamble exists, skip to first '---'
        if '---' in content:
            lines = content.splitlines()
            for idx, line in enumerate(lines):
                if line.strip() == '---':
                    content = '\n'.join(lines[idx:])
                    break
        # Parse all YAML documents
        docs = list(yaml.load_all(content, Loader=yaml.UnsafeLoader))
        raw = docs[0] if docs else {}
        # If first document is not question data (e.g., a docstring), use second
        if not isinstance(raw, (list, dict)) and len(docs) > 1:
            raw = docs[1] or {}
        # Flatten nested 'prompts' sections into top-level question entries
        if isinstance(raw, list):
            flattened = []
            for section in raw:
                if isinstance(section, dict) and 'prompts' in section and isinstance(section['prompts'], list):
                    for prompt in section['prompts']:
                        # Copy all data from prompt to preserve all fields
                        entry = prompt.copy()

                        # Map legacy keys
                        if 'question_type' in entry:
                            entry['type_'] = entry.pop('question_type')
                        if 'starting_yaml' in entry:
                            entry['initial_yaml'] = entry.pop('starting_yaml')

                        # Inherit category from section, overriding any on the prompt
                        if 'category' in section:
                            entry['category'] = section.get('category')
                        flattened.append(entry)
                else:
                    flattened.append(section)
            raw = flattened
        # Normalize legacy 'question' key to 'prompt' and flatten nested metadata
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict):
                    if 'question' in item:
                        item['prompt'] = item.pop('question')
                    if 'metadata' in item and isinstance(item['metadata'], dict):
                        nested = item.pop('metadata')
                        for k, v in nested.items():
                            if k not in item:
                                item[k] = v
        module = raw.get('module') if isinstance(raw, dict) else None
        module = module or os.path.splitext(os.path.basename(path))[0]
        questions: List[Question] = []
        # Flat list of question dicts
        # Flat list of question dicts: allow explicit 'id' in item or fallback to module::index
        if isinstance(raw, list) and raw and isinstance(raw[0], dict):
            for idx, item in enumerate(raw):
                # Use explicit id if provided, else default to module::index
                qid = item.get('id') or f"{module}::{idx}"

                # Tolerate unknown fields by only passing known fields to Question constructor
                known_fields = set(Question.__dataclass_fields__.keys())
                question_data = {k: v for k, v in item.items() if k in known_fields}

                # Legacy field mapping
                if 'type' in question_data:
                    question_data['type_'] = question_data.pop('type')

                # Map legacy YAML keys to new dataclass field names before inference.
                if 'schema_category' in item:
                    question_data['category_id'] = item['schema_category']
                if 'subject_matter' in item:
                    question_data['subject_id'] = item['subject_matter']

                # Infer subject matter only if not explicitly provided.
                if 'subject_id' not in question_data:
                    subject_mat = self._infer_subject_matter(item)
                    if subject_mat:
                        question_data['subject_id'] = subject_mat

                # Set canonical fields
                question_data['id'] = qid
                question_data['source_file'] = path

                # Create question object, it will handle internal normalization
                questions.append(Question(**question_data))

            return questions

        # Fallback to standard 'questions' key in dict
        if isinstance(raw, dict) and 'questions' in raw:
            for idx, item in enumerate(raw.get('questions', [])):
                # Use explicit id if provided, else default to module::index
                qid = item.get('id') or f"{module}::{idx}"

                # Tolerate unknown fields
                known_fields = set(Question.__dataclass_fields__.keys())
                question_data = {k: v for k, v in item.items() if k in known_fields}

                if 'type' in question_data:
                    question_data['type_'] = question_data.pop('type')
                if 'question' in question_data and 'prompt' not in question_data:
                    question_data['prompt'] = question_data.pop('question')

                # Map legacy YAML keys to new dataclass field names before inference.
                if 'schema_category' in item:
                    question_data['category_id'] = item['schema_category']
                if 'subject_matter' in item:
                    question_data['subject_id'] = item['subject_matter']

                # Infer subject matter only if not explicitly provided.
                if 'subject_id' not in question_data:
                    subject_mat = self._infer_subject_matter(item)
                    if subject_mat:
                        question_data['subject_id'] = subject_mat

                # Set canonical fields
                question_data['id'] = qid
                question_data['source_file'] = path

                questions.append(Question(**question_data))

        return questions
