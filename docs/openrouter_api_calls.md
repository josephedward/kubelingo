Here are three **OpenRouter API** call examples for generating Kubernetes CKAD-related questions, covering trivia, command, and manifest formats, each with sufficient details for model answering. These use the OpenRouter API's chat-compatible endpoint, which closely mimics the OpenAI API schema. Any current, stable model that supports chat completion can be used; simply set its ID (e.g., "openrouter/gpt-3.5" or "openrouter/llama-3") in the "model" field.[1][2][3]

***

## Example 1: Trivia Question

```json
POST https://openrouter.ai/api/v1/chat/completions

{
  "model": "openrouter/gpt-3.5",
  "messages": [
    {
      "role": "system",
      "content": "You are an expert Kubernetes CKAD exam tutor."
    },
    {
      "role": "user",
      "content": "Generate one trivia question and its answer about Kubernetes, appropriate for CKAD exam practice. The question must contain all necessary details for a self-contained answer."
    }
  ]
}
```
**Sample Question Generated**:
_Q: What is the purpose of the 'ConfigMap' resource in Kubernetes, and how is it typically used for application configuration in pods?_

_A: The ConfigMap resource lets you store key-value pairs of configuration data separately from container images. Applications running in pods can either mount these values as files or inject them as environment variables, allowing dynamic configuration without rebuilding the image._[4][5]

***

## Example 2: Command-Based Question

```json
POST https://openrouter.ai/api/v1/chat/completions

{
  "model": "openrouter/gpt-3.5",
  "messages": [
    {
      "role": "system",
      "content": "You are an expert Kubernetes CKAD exam tutor."
    },
    {
      "role": "user",
      "content": "Generate a CKAD exam-style question that asks for a specific kubectl command and its correct answer. The question must include all details needed to write the command answer."
    }
  ]
}
```
**Sample Question Generated**:
_Q: In the default namespace, create a pod named pod1 with the image httpd:2.4.41-alpine and container named pod1-container. What kubectl command would create this pod?_

_A: kubectl run pod1 --image=httpd:2.4.41-alpine --restart=Never --container-name=pod1-container --namespace=default_[6]

***

## Example 3: Manifest-Based Question

```json
POST https://openrouter.ai/api/v1/chat/completions

{
  "model": "openrouter/gpt-3.5",
  "messages": [
    {
      "role": "system",
      "content": "You are an expert Kubernetes CKAD exam tutor."
    },
    {
      "role": "user",
      "content": "Generate a CKAD exam-style question that asks for a YAML manifest and provide the complete answer. The question must be detailed enough that the solution is self-contained."
    }
  ]
}
```
**Sample Question Generated**:
_Q: Write a manifest to create a ConfigMap named app-config with the following key-value pairs: 'connection_string' set to 'localhost:4096' and 'external_url' set to 'google.com', and a pod named question-two-pod running image kubegoldenguide/alpine-spin:1.0.0, which exposes both config values as environment variables. All resources should be in the namespace ggckad-s2._

_A:
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
  namespace: ggckad-s2
data:
  connection_string: "localhost:4096"
  external_url: "google.com"
---
apiVersion: v1
kind: Pod
metadata:
  name: question-two-pod
  namespace: ggckad-s2
spec:
  containers:
    - name: web
      image: kubegoldenguide/alpine-spin:1.0.0
      env:
        - name: CONNECTION_STRING
          valueFrom:
            configMapKeyRef:
              name: app-config
              key: connection_string
        - name: EXTERNAL_URL
          valueFrom:
            configMapKeyRef:
              name: app-config
              key: external_url
```


***

These templates work for any stable OpenRouter model and provide clear question/answer formats tailored to CKAD exam prep.[2][3]

[1](https://openrouter.ai/docs/quickstart)
[2](https://openrouter.ai/docs/api-reference/overview)
[3](https://github.com/OpenRouterTeam/openrouter-examples)
[4](https://k21academy.com/docker-kubernetes/cka-ckad-exam-questions-answers/)
[5](https://dev.to/coherentlogic/answers-to-five-kubernetes-ckad-practice-questions-2020-3h0p)
[6](https://www.youtube.com/watch?v=PtqEElhBzao)
[7](https://www.optimizesmart.com/what-is-openrouter-api-and-how-to-use-it/)
[8](https://www.sohamkamani.com/java/openrouter/)
[9](https://www.youtube.com/watch?v=p_g-zxZ0eL0)
[10](https://itnext.io/how-to-ace-ckad-certified-kubernetes-application-developer-exam-ff5eb34ed7bf)
[11](https://openrouter.ai/docs/features/provisioning-api-keys)
[12](https://kodekloud.com/community/t/sep-2021-changes-practice-test-api-versions-deprecations/121525)
[13](https://openrouter.ai/docs/use-cases/usage-accounting)
[14](https://github.com/jamesbuckett/ckad-questions)
[15](https://www.youtube.com/watch?v=YhByx0xEXiA)
[16](https://www.reddit.com/r/kubernetes/comments/100nii1/passed_ckad_test_taken_yday_lot_of_questions_on/)
[17](https://www.reddit.com/r/SillyTavernAI/comments/1kuyyks/can_anyone_help_me_understanding_how_open_router/)
[18](https://www.reddit.com/r/kubernetes/comments/12s5rxf/how_to_practice_real_exam_questions_for_ckad/)
[19](https://blog.devgenius.io/ckad-hard-question-3-how-to-make-one-user-able-to-authenticate-to-the-api-server-with-a-b60a7c17d6)
[20](https://kodekloud.com/community/t/ckad-exam-doubt-for-api-deprecation/469746)