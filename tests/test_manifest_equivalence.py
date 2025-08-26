import yaml
import pytest

from kubelingo.kubelingo import manifests_equivalent

def test_block_vs_inline_pod_manifest_equivalence():
    block_yaml = '''
apiVersion: v1
kind: Pod
metadata:
  name: cmd-args
spec:
  containers:
  - name: c
    image: busybox
    command:
    - sh
    - -c
    args:
    - echo hello && sleep 3600
'''
    inline_yaml = '''
apiVersion: v1
kind: Pod
metadata:
  name: different-name
spec:
  containers:
  - name: busybox-container
    image: busybox
    command: ["sh", "-c"]
    args: ["echo hello && sleep 3600"]
'''
    sol_obj = yaml.safe_load(block_yaml)
    user_obj = yaml.safe_load(inline_yaml)
    assert manifests_equivalent(sol_obj, user_obj)

@pytest.mark.parametrize("user_name", ["my-pod", "cmd-args", None])
def test_metadata_name_ignored(user_name):
    sol_yaml = '''
apiVersion: v1
kind: Pod
metadata:
  name: cmd-args
spec:
  containers:
  - name: c
    image: busybox
'''
    sol_obj = yaml.safe_load(sol_yaml)
    user_obj = yaml.safe_load(sol_yaml)
    # Change metadata.name if provided
    if user_name is not None:
        user_obj['metadata']['name'] = user_name
    else:
        # Remove metadata.name entirely
        user_obj['metadata'].pop('name', None)
    assert manifests_equivalent(sol_obj, user_obj)

def test_image_difference_not_equivalent():
    sol_yaml = '''
apiVersion: v1
kind: Pod
metadata:
  name: test-pod
spec:
  containers:
  - name: c
    image: busybox
'''
    user_yaml = '''
apiVersion: v1
kind: Pod
metadata:
  name: test-pod
spec:
  containers:
  - name: c
    image: nginx
'''
    sol_obj = yaml.safe_load(sol_yaml)
    user_obj = yaml.safe_load(user_yaml)
    assert not manifests_equivalent(sol_obj, user_obj)