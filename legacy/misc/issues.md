----------------------------------------------------------------------------------------------------------------------------------------------------
```
Question 1/4 (Topic: persistence)
----------------------------------------
Pod manifest using an emptyDir volume mounted at /cache.
----------------------------------------
Enter command(s). Type 'done' to check. Special commands: 'solution', 'flag', 'generate', 'vim'.
> vim

Validating manifest with AI...

--- AI Feedback ---
The student's manifest is functionally correct.  While the `apiVersion`, container image, and container name differ from the solution, it correctly defines a Pod with an `emptyDir` volume named "cache" mounted at `/cache` within a container.
-------------------
----------------------------------------
Press Enter for the next question...
```

- it should alwaysshow the 'expected' solution given, even if it differs from the student's answer (will require a test to be written )
----------------------------------------------------------------------------------------------------------------------------------------------------
- generate should come after all the questions for a section are asked (will require a test to be written )
----------------------------------------------------------------------------------------------------------------------------------------------------
- there should be some colorful formatting around the CLI output (will require a test to be written )
----------------------------------------------------------------------------------------------------------------------------------------------------
- number the count of questions for each topic next to the topic name(will require a test to be written )
----------------------------------------------------------------------------------------------------------------------------------------------------
- .vimrc needs to specify tab as two spaces (will require a test to be written )
----------------------------------------------------------------------------------------------------------------------------------------------------
```
Question 4/4 (Topic: persistence)
----------------------------------------
Traceback (most recent call last):
  File "/Users/user/Documents/GitHub/kubelingo/kubelingo.py", line 445, in <module>
    main()
  File "/Users/user/Documents/GitHub/kubelingo/kubelingo.py", line 436, in main
    run_topic(topic)
  File "/Users/user/Documents/GitHub/kubelingo/kubelingo.py", line 318, in run_topic
    print(q['question'])
          ~^^^^^^^^^^^^
KeyError: 'question'
```

- the above issue may be related to questions we have added with complex yaml schemas that do not match our simple schema we have laid out
- reformat for simplicity 
-------------------------------------------------------------------------------------------------------------------------------------------------------------------
- need the ability to navigate forward and backward through individual characters in answers (will require a test to be written ) - this is what happens when I try to use the left and right arrow keys: '''> helm repo install bitnami/node ^[[D^[[D^[[D'''
------------------------------------------------------------------------------------------------------------------------------------------------------------------- 
```
- question: "Pod manifest using an emptyDir volume mounted at /cache."
    solution: |
      apiVersion: v1
      kind: Pod
      metadata:
        name: cache-user
      spec:
        volumes:
          - name: cache
            emptyDir: {}
        containers:
          - name: app
            image: busybox
            volumeMounts:
              - name: cache
                mountPath: /cache
                readOnly: false
```

- I think this question it incorrectly told my my answer was correct, even though I had a section that said: 
```
volumes:
- name: cache
  type: emptyDir
```
is that in fact correct? 
----------------------------------------------------------------------------------------------------------------------------------------------------
the user should be able to navigate through their answers with the arrow keys, like if they want to back up and edit a command without deleting it all (will require a test to be written )
----------------------------------------------------------------------------------------------------------------------------------------------------
We should have the ability to permanently store API keys, there should be a menu option/command for accessing settings etc where you can view and edit your API keys - we also need OpenAI API key (will require a test to be written )
----------------------------------------------------------------------------------------------------------------------------------------------------
We should support multiple AI providers; OpenAI being the first one. What would be the most flexible way to approach this? Is there a way we can pay one company to access all of the AI apis?  
----------------------------------------------------------------------------------------------------------------------------------------------------
Issues should be added here, add the issue and then another line of dashes below 
----------------------------------------------------------------------------------------------------------------------------------------------------
issues should be timestamped, with tags for feature or bugs etc (will require a test to be written )
-------------------------------------------------------------------------------------------------------------------------------------------------------------------
delete does not work; I cannot edit my answers after I type them (will require a test to be written )
-------------------------------------------------------------------------------------------------------------------------------------------------------------------
is it better to use yaml or markdown for this? realistically, you must be doing this 
-------------------------------------------------------------------------------------------------------------------------------------------------------------------
multiple line issues are not supported; they need to be handed because we will often be copying and pasting from the terminal (will require a test to be written )
-------------------------------------------------------------------------------------------------------------------------------------------------------------------

Question 2/7 (Topic: imperative_vs_declarative)
----------------------------------------
Generate a YAML file for a deployment with nginx image without creating it.
----------------------------------------
Enter command(s). Type 'done' to check. Special commands: 'solution', 'issue', 'generate', 'vim', 'back'.
> k create deployment nginx --image=nginx -o yaml --dry-run=client
> 
> done

Not quite. Here's one possible solution:

kubectl create deployment nginx --image=nginx --dry-run=client -o yaml > deploy.yaml

--- AI Feedback ---
The student's answer uses `k create` which is not a standard Kubernetes command;  it should use `kubectl create`.  Also, the student's answer is missing the redirection (`> deploy.yaml`) needed to save the YAML output to a file.  Adding `kubectl` and redirection will fix the issue.

----------------------------------------
Press Enter for the next question, or type 'issue' to report a problem: 

- question does not have the level of detail required 

-------------------------------------------------------------------------------------------------------------------------------------------------------------------




Question 4/7 (Topic: imperative_vs_declarative)
----------------------------------------
Generate the YAML for a pod named 'nginx' with image 'nginx:latest' without creating it. Save it to a file named 'pod.yaml'.
----------------------------------------
Enter command(s). Type 'done' to check. Special commands: 'solution', 'issue', 'generate', 'vim', 'back'.
> k run nginx --image=nginx:latest --dry-run=client > pod.yaml
> 
> done

Not quite. Here's one possible solution:

kubectl run nginx --image=nginx:latest --dry-run=client -o yaml > pod.yaml

--- AI Feedback ---
The student used `k run`, which is not a standard Kubernetes command.  They should use `kubectl run` instead, the correct Kubernetes command-line tool for creating pods.  This small correction will make their YAML generation work perfectly.

----------------------------------------
Press Enter for the next question, or type 'issue' to report a problem: 


- it still seems to think that k run is not correct, when its a valid alias for kubectl 

-------------------------------------------------------------------------------------------------------------------------------------------------------------------

Question 7/7 (Topic: imperative_vs_declarative)
----------------------------------------
Command to generate a Pod manifest named web-pod using image nginx.
----------------------------------------
Enter command(s). Type 'done' to check. Special commands: 'solution', 'issue', 'generate', 'vim', 'back'.
> k run web-pod --image=nginx -o yaml
> 
> done

Not quite. Here's one possible solution:

kubectl run web-pod --image=nginx --restart=Never --dry-run=client -o yaml

--- AI Feedback ---
The student's command uses `k run`, a shorthand, which implies automatic restart.  The correct solution explicitly sets `--restart=Never` to avoid unexpected restarts and uses `--dry-run=client` for generating a manifest without deployment, crucial for the exam's focus on manifests.  Adding these options will make the answer accurate.



-------------------------------------------------------------------------------------------------------------------------------------------------------------------
need to be grading performance and tracking relative strengths and weaknesses of students (will require a test to be written )
-------------------------------------------------------------------------------------------------------------------------------------------------------------------
there should be a rule enforced; if the user cannt answer all question in a given section correctly, they cannot generate more questions (will require a test to be written ) ; this should also encourage them to create issues around problematically worded questions to ensure they can in fact be answered correctly
-------------------------------------------------------------------------------------------------------------------------------------------------------------------
show a diff of the users manifest yaml and the correct manifest yaml  (will require a test to be written )
-------------------------------------------------------------------------------------------------------------------------------------------------------------------

Question 2/8 (Topic: pod_design_patterns)
----------------------------------------
Create a Deployment named `test-init-container` in namespace `mars`. It should have one replica. The Pods should have an `nginx:1.17.3-alpine` container and an `initContainer` named `init-con` using `busybox:1.31.0`. An `emptyDir` volume `web-content` should be mounted to `/usr/share/nginx/html` in the nginx container and `/tmp/web-content` in the init container. The init container should run `echo 'check this out!' > /tmp/web-content/index.html`.
----------------------------------------
Enter command(s). Type 'done' to check. Special commands: 'solution', 'issue', 'generate', 'vim', 'back'.
> vim

Validating manifest with AI...

--- AI Feedback ---
The student's manifest has a typo in the `metadata` section (namespace; mars should be namespace: mars), uses `commands` instead of `command` in the initContainer, and omits a crucial `ports` declaration in the nginx container, preventing the web server from functioning correctly.  While the core functionality is mostly present, these errors would lead to deployment failure or malfunction.
-------------------

That wasn't quite right. Here is the solution:

apiVersion: apps/v1
kind: Deployment
metadata:
  name: test-init-container
  namespace: mars
spec:
  replicas: 1
  selector:
    matchLabels:
      id: test-init-container
  template:
    metadata:
      labels:
        id: test-init-container
    spec:
      volumes:
      - name: web-content
        emptyDir: {}
      initContainers:
      - name: init-con
        image: busybox:1.31.0
        command: ['sh', '-c', 'echo "check this out!" > /tmp/web-content/index.html']
        volumeMounts:
        - name: web-content
          mountPath: /tmp/web-content
      containers:
      - name: nginx
        image: nginx:1.17.3-alpine
        volumeMounts:
        - name: web-content
          mountPath: /usr/share/nginx/html
        ports:
        - containerPort: 80



- this question does not make it clear that it needs to be on containerPort 80

-------------------------------------------------------------------------------------------------------------------------------------------------------------------
should we create a system for logging wrong answers? the ai explanations? if we did do this, the app could function offline more easily 
-------------------------------------------------------------------------------------------------------------------------------------------------------------------
how to install this on mobile CLI? iphone? 
-------------------------------------------------------------------------------------------------------------------------------------------------------------------



Question 6/8 (Topic: pod_design_patterns)
----------------------------------------
Run a pod named busybox with image busybox that runs indefinitely.
----------------------------------------
Enter command(s). Type 'done' to check. Special commands: 'solution', 'issue', 'generate', 'vim', 'back'.
> k run busybox --image=busybox --restart=Never
> 
> done

Not quite. Here's one possible solution:

kubectl run busybox --image=busybox --restart=Never -- /bin/sh -c "sleep 3600"

--- AI Feedback ---
The student's answer only creates the pod;  it doesn't specify a command to keep it running.  To fix this, add a command that runs indefinitely, such as `-- /bin/sh -c "sleep 3600"` (or a similar long-running process),  inside the `kubectl run` command.  This ensures the container within the pod continues to run, fulfilling the "indefinitely" requirement.

----------------------------------------

- this question is potentially confusing, a sleep command sounds like it is not running indefinitely; would it be better to have an empty while loop 

-------------------------------------------------------------------------------------------------------------------------------------------------------------------


Question 7/8 (Topic: pod_design_patterns)
----------------------------------------
Pod manifest with a sidecar that tails a shared log file.
----------------------------------------
Enter command(s). Type 'done' to check. Special commands: 'solution', 'issue', 'generate', 'vim', 'back'.
> solution

Solution:

apiVersion: v1
kind: Pod
metadata:
  name: app-with-sidecar
spec:
  volumes:
    - name: logs
      emptyDir: {}
  containers:
    - name: app
      image: busybox
      command: ["sh","-c","while true; do date >> /var/log/app/app.log; sleep 2; done"]
      volumeMounts:
        - name: logs
          mountPath: /var/log/app
    - name: log-tailer
      image: busybox
      command: ["sh","-c","tail -n+1 -F /var/log/app/app.log"]
      volumeMounts:
        - name: logs
          mountPath: /var/log/app

----------------------------------------
Press Enter for the next question, or type 'issue' to report a problem: 

- are users really expected to be able to infer this? at least at the stage of my current comfort with kubernetes, I would not have been able to answer this question correctly; needs to have much more detail in the answer 

--------------------------------------------------------------------------------------------------------------------------------------------------------------------


Question 1/44 (Topic: linux_syntax)
----------------------------------------
In Vim, how do you go to line 10?
----------------------------------------
Enter command(s). Type 'done' to check. Special commands: 'solution', 'issue', 'generate', 'vim', 'back'.
> :10
> 
> done

Not quite. Here's one possible solution:

:10 or 10gg or 10G

--- AI Feedback ---
The student's answer is partially correct, but the exam likely requires demonstrating knowledge of multiple Vim commands to achieve the same result.  To improve, the student should familiarize themselves with alternative commands like `10gg` and `10G` which achieve the same goal using different Vim navigation shortcuts.  This demonstrates a broader understanding of Vim's capabilities.

----------------------------------------
Press Enter for the next question, or type 'issue' to report a problem: 

- this was basically correct 

--------------------------------------------------------------------------------------------------------------------------------------------------------------------
remove 'back' and just be certain the arrows and delete buttons work on a single line
--------------------------------------------------------------------------------------------------------------------------------------------------------------------


Question 2/44 (Topic: linux_syntax)
----------------------------------------
List ServiceAccounts using the short alias 'sa'.
----------------------------------------
Enter command(s). Type 'done' to check. Special commands: 'solution', 'issue', 'generate', 'vim', 'back'.
> 

- this command is in the wrong section 

--------------------------------------------------------------------------------------------------------------------------------------------------------------------
formatting of these does not matter; you will need gitscaffold to handle this with real issues on your repo 
--------------------------------------------------------------------------------------------------------------------------------------------------------------------


Please select a topic to study:
  1. Api Discovery Docs (3/3 correct - 100%)
  2. App Configuration
  3. Commands Args Env
  4. Core Workloads
  5. Helm Basics
  6. Image Registry Use
  7. Imperative Vs Declarative
  8. Ingress Http Routing
  9. Jobs Cronjobs
  10. Kubectl Common Operations
  11. Kubectl Operations
  12. Labels Annotations Selectors
  13. Linux Syntax
  14. Namespaces Contexts
  15. Networking Utilities
  16. Observability Troubleshooting
  17. Persistence
  18. Pod Design Patterns
  19. Probes Health
  20. Resource Management
  21. Resource Reference
  22. Scheduling Hints
  23. Security Basics
  24. Service Accounts In Apps
  25. Services

Or, select a special action:
  m. Review Missed Questions

Enter a number (1-25) or letter 'm': 
Invalid input. Please enter a number or letter.

Enter a number (1-25) or letter 'm': 1



































Question 1/5 (Topic: api_discovery_docs)
----------------------------------------
Command to view the fields under Deployment.spec.strategy.
----------------------------------------
Enter command(s). Type 'done' to check. Special commands: 'solution', 'issue', 'generate', 'vim', 'back'.
> 

- should not be as much of a space for the next question, that whitespace should be removed
- grading is not correct (I scored 3 our 5)
- total questions should be listed next to each topic
- menus need color 

write tests and make sure all of these are fixed 
--------------------------------------------------------------------------------------------------------------------------------------------------------------------







Question 1/4 (Topic: commands_args_env)
----------------------------------------
Pod manifest overriding command and args to print 'hello'.
----------------------------------------
Enter command(s). Type 'done' to check. Special commands: 'solution', 'issue', 'generate', 'vim', 'back'.
> solution

Solution:

apiVersion: v1
kind: Pod
metadata:
  name: cmd-args
spec:
  containers:
    - name: c
      image: busybox
      command: ["sh","-c"]
      args: ["echo hello && sleep 3600"]

----------------------------------------
Press Enter for the next question, or type 'issue' to report a problem: 


Question 2/4 (Topic: commands_args_env)
----------------------------------------
Pod manifest loading env from a ConfigMap named app-cm.
----------------------------------------
Enter command(s). Type 'done' to check. Special commands: 'solution', 'issue', 'generate', 'vim', 'back'.
> vim

Validating manifest with AI...

--- AI Feedback ---
The student's manifest is missing the crucial `envFrom` section within the container specification, which is necessary to load environment variables from the ConfigMap.  It also uses the ConfigMap's name for the Pod, which is not required and may lead to naming conflicts.

That wasn't quite right. Here is the solution:

apiVersion: v1
kind: Pod
metadata:
  name: envfrom-cm
spec:
  containers:
    - name: c
      image: busybox
      envFrom:
        - configMapRef:
            name: app-cm

----------------------------------------

Question 1/25 (Topic: kubectl_common_operations)
----------------------------------------
View a diff reading from stdin.
----------------------------------------
Enter command(s). Type 'done' to check. Special commands: 'solution', 'issue', 'generate', 'vim', 'back'.
> solution

Solution:
cat pod.json | kubectl diff -f -







- non adequate level of detail to properly answer these questions 

--------------------------------------------------------------------------------------------------------------------------------------------------------------------

Question 4/25 (Topic: kubectl_common_operations)
----------------------------------------
Delete a pod using the definition in pod.yaml.
----------------------------------------
Enter command(s). Type 'done' to check. Special commands: 'solution', 'issue', 'generate', 'vim', 'back'.
> k delete pod -f pod.yaml
> 
> done

Not quite. Here's one possible solution:
kubectl delete -f pod.yaml

--- AI Feedback ---
The student's answer is missing the `kubectl` command prefix, which is essential for interacting with the Kubernetes API.  They should always use `kubectl` before any Kubernetes command.  Simply adding `kubectl` before `delete pod -f pod.yaml` will correct the answer.



- this one just didnt recognize the alias


--------------------------------------------------------------------------------------------------------------------------------------------------------------------
should we mark as incorrect AGAIN if they miss it on a second run?  when I did, it was becasue it did not recognize the alias; 
--------------------------------------------------------------------------------------------------------------------------------------------------------------------
it seems to be skipping to the next question too quickly, so they cant make an issue for the previous question, they should be able to navigate forward (skip - mark as incorrect), backward, and create an issue - all occuring after the question has been answered, solution has been shown, and AI feedback has been given  
--------------------------------------------------------------------------------------------------------------------------------------------------------------------
make sure that the app will search for a source, give the user a choice of sources, and then let the user select which source will be added to the questions yaml - defaulting to the top one if nothing is selected 

--------------------------------------------------------------------------------------------------------------------------------------------------------------------
needs to be an option for quitting: '''Please select a topic to study:
  1. Api Discovery Docs [5 questions] (5/5 correct - 100%)
  2. App Configuration [17 questions] (0/17 correct - 0%)
  3. Commands Args Env [4 questions] (0/4 correct - 0%)
  4. Core Workloads [18 questions] (0/18 correct - 0%)
  5. Helm Basics [20 questions] (0/20 correct - 0%)
  6. Image Registry Use [3 questions] (0/3 correct - 0%)
  7. Imperative Vs Declarative [7 questions] (0/7 correct - 0%)
  8. Ingress Http Routing [4 questions] (0/4 correct - 0%)
  9. Jobs Cronjobs [5 questions] (0/5 correct - 0%)
  10. Kubectl Common Operations [25 questions] (0/25 correct - 0%)
  11. Kubectl Operations [44 questions] (0/44 correct - 0%)
  12. Labels Annotations Selectors [9 questions] (0/9 correct - 0%)
  13. Linux Syntax [44 questions] (3/44 correct - 7%)
  14. Namespaces Contexts [11 questions] (0/11 correct - 0%)
  15. Networking Utilities [3 questions] (0/3 correct - 0%)
  16. Observability Troubleshooting [4 questions] (0/4 correct - 0%)
  17. Persistence [3 questions] (0/3 correct - 0%)
  18. Pod Design Patterns [8 questions] (0/8 correct - 0%)
  19. Probes Health [5 questions] (0/5 correct - 0%)
  20. Resource Management [5 questions] (0/5 correct - 0%)
  21. Resource Reference [138 questions] (0/138 correct - 0%)
  22. Scheduling Hints [3 questions] (0/3 correct - 0%)
  23. Security Basics [7 questions] (0/7 correct - 0%)
  24. Service Accounts In Apps [9 questions] (0/9 correct - 0%)
  25. Services [9 questions] (0/9 correct - 0%)

Or, select a special action:
  m. Review Missed Questions [65]

Enter a number (1-25) or letter 'm': 

Study session ended. Goodbye!
Error: Question file not found at questions/None.yaml
Available topics: imperative_vs_declarative, linux_syntax, networking_utilities, ingress_http_routing, services, commands_args_env, probes_health, kubectl_operations, api_discovery_docs, resource_reference, pod_design_patterns, labels_annotations_selectors, app_configuration, helm_basics, security_basics, jobs_cronjobs, resource_management, observability_troubleshooting, service_accounts_in_apps, core_workloads, kubectl_common_operations, persistence, scheduling_hints, namespaces_contexts, image_registry_use
No questions found in the specified topic file.

Returning to the main menu...
^C
'''
--------------------------------------------------------------------------------------------------------------------------------------------------------------------
enter should be 'all' by default: 

'''
Enter number of questions to study (1-4, or 'all'): 
'''



--------------------------------------------------------------------------------------------------------------------------------------------------------------------

Question 5/5 (Topic: api_discovery_docs)
----------------------------------------
Command to list namespaced resources supporting 'list'.
----------------------------------------
Enter command(s). Type 'done' to check. Special commands: 'solution', 'vim', 'clear', 'menu'.
> k api-resources --verbs=list -namespaced
> 
> done

Correct! Well done.

--- Question Completed ---
Options: [n]ext, [b]ack, [i]ssue, [g]enerate, [s]ource, [r]etry, [q]uit
> s

No source available for this question.
Press Enter to continue...


- source should find sources and provide AI clarification
- small paragraph explanation should come up (llm or llm-gemini would be helfgul here)
- list of links from search (used to be in /scripts)
- should automatically set the top link as source in the questions yaml

--------------------------------------------------------------------------------------------------------------------------------------------------------------------

Question 1/2 (Topic: commands_args_env)
----------------------------------------
Create a manifest for a Pod named 'args-pod' with image 'busybox'. Override the container's command to be `['/bin/sh', '-c']` and its arguments to be `['echo Hello world']`.
----------------------------------------
Enter command(s). Type 'done' to check. Special commands: 'solution', 'vim', 'clear', 'menu'.
> vim

Validating manifest with AI...

--- AI Feedback ---
The student's manifest is functionally equivalent to the solution.  It correctly specifies the Pod's name, image, command, and arguments, resulting in the same "Hello world" output.  The only difference is the container name, which is not a functional requirement of the question.

--- Question Completed ---
Options: [n]ext, [b]ack, [i]ssue, [g]enerate, [s]ource, [r]etry, [q]uit
> 





- did not say 'answer correct' 

--------------------------------------------------------------------------------------------------------------------------------------------------------------------

Question 3/20 (Topic: resource_reference)
----------------------------------------
Is Binding a namespaced resource?
----------------------------------------
Enter command(s). Type 'done' to check. Special commands: 'solution', 'vim', 'clear', 'menu'.
> false
> 
> done

Not quite. Here's one possible solution:
true

--- AI Feedback ---
INFO: Set GEMINI_API_KEY or OPENAI_API_KEY for AI-powered feedback.

--- Question Completed ---
Options: [n]ext, [b]ack, [i]ssue, [g]enerate, [s]ource, [r]etry, [q]uit
> 


- we should changed the wording to something like "Incomplete Answer. Here is our default stored answer: "

--------------------------------------------------------------------------------------------------------------------------------------------------------------------
