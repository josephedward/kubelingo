# Gemini API Examples for CKAD-style Kubernetes Questions and Answers

Here are three concrete examples for calling the Gemini API to get CKAD-style Kubernetes questions and answers — one trivia, one command, and one manifest. The examples below use a stable text generation API with JSON payloads, as typically found in Gemini’s REST or Python SDK interfaces. Each request fully specifies the prompt to get a complete question and answer.

## Get Trivia Question and Answer

**Request (Python SDK):**
```python
import google.generativeai as genai
genai.configure(api_key='YOUR_API_KEY')

prompt = (
    "Create a Kubernetes trivia question suitable for CKAD candidates. "
    "The question should require a conceptual answer and provide all necessary context. "
    "Return the question and the complete answer. "
    "Example: Question: What is the purpose of a Kubernetes Service? Answer: ..."
)

response = genai.GenerativeModel('gemini-2.5-flash').generate_content(prompt)
print(response.text)
```

**Sample Expected Output:**
```
Question: What is the difference between a Kubernetes Deployment and a StatefulSet?
Answer: A Deployment manages stateless app replicas and handles rolling updates, while a StatefulSet manages stateful apps, assigns stable, unique network identities, and ordered deployment/termination of pods.
```

## Get Command Question and Answer

**Request (Python SDK):**
```python
import google.generativeai as genai
genai.configure(api_key='YOUR_API_KEY')

prompt = (
    "Create a Kubernetes CKAD question that requires running a kubectl command. "
    "Include all required details: context, resource names, and expected result. "
    "Return both the question and the complete command answer."
)

response = genai.GenerativeModel('gemini-2.5-flash').generate_content(prompt)
print(response.text)
```

**Sample Expected Output:**
```
Question: In the 'dev' namespace, create a pod called web-server using the nginx image.
Answer: kubectl run web-server --image=nginx --namespace=dev
```

## Get Manifest Question and Answer

**Request (Python SDK):**
```python
import google.generativeai as genai
genai.configure(api_key='YOUR_API_KEY')

prompt = (
    "Create a Kubernetes CKAD question that requires writing a YAML manifest. "
    "Provide all required details, such as pod name, image, probes, and environment settings. "
    "Return both the question and a valid Kubernetes YAML manifest as the answer."
)

response = genai.GenerativeModel('gemini-2.5-flash').generate_content(prompt)
print(response.text)
```

**Sample Expected Output:**
```
Question: Write a manifest for a pod named 'health-check-pod' using the image nginx:1.19.2,
with a liveness probe on /healthz using HTTP GET on port 8080.
Answer:
apiVersion: v1
kind: Pod
metadata:
  name: health-check-pod
spec:
  containers:
  - name: nginx
    image: nginx:1.19.2
    livenessProbe:
      httpGet:
        path: /healthz
        port: 8080
      initialDelaySeconds: 10
      periodSeconds: 5
```

### References
1. https://dev.to/coherentlogic/answers-to-five-kubernetes-ckad-practice-questions-2020-3h0p
2. https://github.com/jamesbuckett/ckad-questions
3. https://www.reddit.com/r/kubernetes/comments/12s5rxf/how_to_practice_real_exam_questions_for_ckad/
4. https://www.youtube.com/watch?v=p_g-zxZ0eL0
5. https://codeburst.io/kubernetes-ckad-weekly-challenges-overview-and-tips-7282b36a2681
6. https://ai.google.dev/gemini-api/docs/quickstart
7. https://www.geeksforgeeks.org/techtips/how-to-use-google-gemini-api-key/
8. https://k21academy.com/docker-kubernetes/cka-ckad-exam-questions-answers/
9. https://serpapi.com/blog/access-real-time-data-with-gemini-api-using-function-calling/
10. https://github.com/google-gemini/cookbook
11. https://matthewpalmer.net/kubernetes-app-developer/articles/ckad-practice-exam.html
12. https://stackoverflow.com/questions/78564261/gemini-api-curl-command-successfully-calls-api-but-my-program-does-not
13. https://www.youtube.com/watch?v=heXuVxXG5Vo
14. https://github.com/dgkanatsios/CKAD-exercises
15. https://www.reddit.com/r/ckad/comments/1dewq1s/api_deprecation_ckad_question/
16. https://dev.to/wescpy/a-better-google-gemini-api-hello-world-sample-4ddm
17. https://ai.google.dev/api/semantic-retrieval/question-answering
18. https://youssefh.substack.com/p/getting-started-with-gemini-api-a
