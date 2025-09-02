"""
Question Generator Module for Kubelingo
Generates self-contained Kubernetes questions with multiple valid solution formats.
"""
import random
from typing import List, Dict, Any
from kubelingo.source_manager import get_source_for_kind

class GenerationError(Exception):
    """Raised when question generation fails due to unsupported kind or exhausted options."""
    pass

# Parameter pools for question generation
_POD_NAMES = ['web-server', 'cache-server', 'db-pod']
_POD_IMAGES = ['nginx:1.20', 'redis:6.2', 'mysql:5.7']

_DEPLOY_NAMES = ['nginx-deploy', 'api-server-deploy', 'worker-deploy']
_DEPLOY_IMAGES = _POD_IMAGES
_REPLICA_COUNTS = [1, 3, 5]

_SERVICE_NAMES = ['web-svc', 'cache-svc', 'db-svc']
_SERVICE_TYPES = ['ClusterIP', 'NodePort']
_PORTS = [80, 443, 6379]

_PVC_NAMES = ['data-pvc', 'cache-pvc']
_STORAGE_SIZES = ['1Gi', '5Gi']
_ACCESS_MODES = ['ReadWriteOnce', 'ReadOnlyMany']

_CM_NAMES = ['app-config', 'db-config']
_CM_KEYS = ['LOG_LEVEL', 'DB_HOST']
_CM_VALUES = ['DEBUG', 'db.example.com']

_SECRET_NAMES = ['app-secret', 'db-secret']
_SECRET_KEYS = ['USERNAME', 'PASSWORD']
_SECRET_VALUES = ['user1', 'pass123']

_JOB_NAMES = ['db-backup', 'email-job']
_JOB_IMAGES = ['busybox', 'alpine']

def _gen_pod() -> Dict[str, Any]:
    name = random.choice(_POD_NAMES)
    image = random.choice(_POD_IMAGES)
    question = f"Create a Pod named '{name}' that runs a container with the image '{image}'."
    suggestions = [
        f"kubectl run {name} --image={image}",
        {
            'apiVersion': 'v1',
            'kind': 'Pod',
            'metadata': {'name': name},
            'spec': {'containers': [{'name': name, 'image': image}]}
        }
    ]
    requirements = {'kind': 'Pod', 'name': name, 'image': image}
    return {'question': question, 'suggestion': suggestions,
            'source': get_source_for_kind('Pod'), 'requirements': requirements}

def _gen_deployment() -> Dict[str, Any]:
    name = random.choice(_DEPLOY_NAMES)
    image = random.choice(_DEPLOY_IMAGES)
    replicas = random.choice(_REPLICA_COUNTS)
    question = f"Create a Deployment named '{name}' with {replicas} replicas of the image '{image}'."
    suggestions = [
        f"kubectl create deployment {name} --image={image} --replicas={replicas}",
        {
            'apiVersion': 'apps/v1',
            'kind': 'Deployment',
            'metadata': {'name': name},
            'spec': {'replicas': replicas,
                     'selector': {'matchLabels': {'app': name}},
                     'template': {
                         'metadata': {'labels': {'app': name}},
                         'spec': {'containers': [{'name': name, 'image': image}]}
                     }}
        }
    ]
    requirements = {'kind': 'Deployment', 'name': name, 'image': image, 'replicas': replicas}
    return {'question': question, 'suggestion': suggestions,
            'source': get_source_for_kind('Deployment'), 'requirements': requirements}

def _gen_service() -> Dict[str, Any]:
    name = random.choice(_SERVICE_NAMES)
    svc_type = random.choice(_SERVICE_TYPES)
    port = random.choice(_PORTS)
    target = random.choice(_PORTS)
    selector = {'app': name.split('-')[0]}
    question = (f"Create a Service of type {svc_type} named '{name}' that exposes port {port}"
                f" targeting port {target} for Pods labeled app={selector['app']}." )
    suggestions = [
        f"kubectl expose deployment {selector['app']} --name={name} --port={port} --target-port={target} --type={svc_type}",
        {
            'apiVersion': 'v1',
            'kind': 'Service',
            'metadata': {'name': name},
            'spec': {'type': svc_type,
                     'selector': selector,
                     'ports': [{'port': port, 'targetPort': target}]}
        }
    ]
    requirements = {'kind': 'Service', 'name': name,
                    'service_type': svc_type, 'port': port,
                    'targetPort': target, 'selector': selector}
    return {'question': question, 'suggestion': suggestions,
            'source': get_source_for_kind('Service'), 'requirements': requirements}

def _gen_pvc() -> Dict[str, Any]:
    name = random.choice(_PVC_NAMES)
    size = random.choice(_STORAGE_SIZES)
    mode = random.choice(_ACCESS_MODES)
    question = (f"Create a PersistentVolumeClaim named '{name}' that requests {size} of storage"
                f" with access mode {mode}. Use the default storage class.")
    suggestions = [
        f"kubectl create pvc {name} --storage={size} --access-mode={mode}",
        {
            'apiVersion': 'v1',
            'kind': 'PersistentVolumeClaim',
            'metadata': {'name': name},
            'spec': {'accessModes': [mode],
                     'resources': {'requests': {'storage': size}}}
        }
    ]
    requirements = {'kind': 'PersistentVolumeClaim', 'name': name,
                    'storage': size, 'access_modes': [mode]}
    return {'question': question, 'suggestion': suggestions,
            'source': get_source_for_kind('PersistentVolumeClaim'), 'requirements': requirements}

def _gen_configmap() -> Dict[str, Any]:
    name = random.choice(_CM_NAMES)
    key = random.choice(_CM_KEYS)
    val = random.choice(_CM_VALUES)
    question = f"Create a ConfigMap named '{name}' with data key '{key}' set to '{val}'."
    suggestions = [
        f"kubectl create configmap {name} --from-literal={key}={val}",
        {
            'apiVersion': 'v1',
            'kind': 'ConfigMap',
            'metadata': {'name': name},
            'data': {key: val}
        }
    ]
    requirements = {'kind': 'ConfigMap', 'name': name, 'data': {key: val}}
    return {'question': question, 'suggestion': suggestions,
            'source': get_source_for_kind('ConfigMap'), 'requirements': requirements}

def _gen_secret() -> Dict[str, Any]:
    name = random.choice(_SECRET_NAMES)
    key = random.choice(_SECRET_KEYS)
    val = random.choice(_SECRET_VALUES)
    question = f"Create a Secret named '{name}' of type Generic with data key '{key}' set to '{val}'."
    suggestions = [
        f"kubectl create secret generic {name} --from-literal={key}={val}",
        {
            'apiVersion': 'v1',
            'kind': 'Secret',
            'metadata': {'name': name},
            'type': 'Opaque',
            'stringData': {key: val}
        }
    ]
    requirements = {'kind': 'Secret', 'name': name, 'type': 'Opaque', 'stringData': {key: val}}
    return {'question': question, 'suggestion': suggestions,
            'source': get_source_for_kind('Secret'), 'requirements': requirements}

def _gen_job() -> Dict[str, Any]:
    name = random.choice(_JOB_NAMES)
    image = random.choice(_JOB_IMAGES)
    question = f"Create a Job named '{name}' that runs a pod with the image '{image}'."
    suggestions = [
        f"kubectl create job {name} --image={image}",
        {
            'apiVersion': 'batch/v1',
            'kind': 'Job',
            'metadata': {'name': name},
            'spec': {'template': {'spec': {'containers': [{'name': name, 'image': image}], 'restartPolicy': 'OnFailure'}}}
        }
    ]
    requirements = {'kind': 'Job', 'name': name, 'image': image}
    return {'question': question, 'suggestion': suggestions,
            'source': get_source_for_kind('Job'), 'requirements': requirements}

_GENERATORS = {
    'pod': _gen_pod,
    'deployment': _gen_deployment,
    'service': _gen_service,
    'persistentvolumeclaim': _gen_pvc,
    'pvc': _gen_pvc,
    'configmap': _gen_configmap,
    'secret': _gen_secret,
    'job': _gen_job,
}

def generate_questions(kind: str, count: int = 1) -> List[Dict[str, Any]]:
    """Generate `count` unique questions of the given Kubernetes resource kind."""
    key = kind.lower()
    if key not in _GENERATORS:
        raise GenerationError(f"Unsupported resource kind: {kind}")
    gen_fn = _GENERATORS[key]
    questions = []
    seen = set()
    attempts = 0
    while len(questions) < count and attempts < count * 5:
        q = gen_fn()
        text = q['question']
        if text not in seen:
            seen.add(text)
            questions.append(q)
        attempts += 1
    if len(questions) < count:
        raise GenerationError(f"Could not generate {count} unique questions for kind '{kind}'")
    return questions