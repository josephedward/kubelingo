- There is no root-level cli.py, only kubelingo/cli.py

- Menu must be colored.  

- Main Menu 
	+ quiz
	+ import 
	+ settings

- Config Menu: 
	--- API Key Configuration ---
	  1. Set Gemini API Key (current: ****5ru8 (Valid)) (Model: gemini-1.5-flash-latest)
	  2. Set OpenAI API Key (current: ****lQwA (Valid)) (Model: gpt-3.5-turbo)
	  3. Set OpenRouter API Key (current: ****61c2 (Valid)) (Model: deepseek/deepseek-r1-0528:free)
	  4. Set Perplexity API Key (current: ()) (Model: )

	--- AI Provider Selection ---
	  4. Choose AI Provider (current: openai)
	  5. Back
	? Enter your choice: 

- AI providers
	+ create scripts and test each one can generate each type of question 
	+ 4 providers * 5 question types + 20 tests (provided of course, you have valid API keys to test with - which you should have)
	+  all providers must work across all types and topics


- Quiz Menu
	+ True/False
	+ Vocab
	+ Multiple Choice 
	+ Imperative (Commands)
	+ Declarative (Manifests)
	+ Stored 

- Subject Matters
 	+ api_discovery_docs, app_configuration, commands_args_env, configmap, core_workloads, deployment, helm_basics, image_registry_use, imperative_vs_declarative ingress_http_routing, jobs_cronjobs, kubectl_common_operations, kubectl_operations, labels_annotations_selectors, linux_commands_syntax, logging, namespaces_contexts, networking_utilities, observability_troubleshooting, persistence, pod_design_patterns, probes_health, pvc, resource_management, resource_reference, scheduling_hints, secrets, security_basics, service_accounts_in_apps, services, rbac, monitoring, troubleshooting
	+ questions need to be more specific to the domain, and more detailed - individual flags for resources, low-level 


- Questions must be complex and varied; cannot be repetitive 

- Generate Vocab Question
	+ seeks a single term 
	+ does not ask for them to provide definition verbatim 

- Generate MCQ
	+ provides three deceptively wrong answers and seeks the correct one
	+ must ALWAYs provide 4 detailed answers (one of them being correct)
 
- Generate True/False; seeks one of two Options 

- Generate Commands 
	+ kubectl, helm, linux
	+ all the variables in the answer must be in the body of the question 
	+ absolutely MUST be syntactically correct; this is the entire point 

- Generate Manifests 
	+ absolutely MUST be syntactically correct; this is the entire point
	+ all the variables in the answer must be in the body of the question 



- Import Menu 
	+ File/Folder Path 
	+ URL

- Must be able to import questions from diverse sources 
	+ local folders with pdf, docx, txt, yaml, json, md
	+ and from URL via web automation  


- Questions/ folder: 
	+ correct 
	+ incorrect 
	+ uncategorized 


Example schema for a question: 
    {
        "id": "a1b2c3d4",
        "topic": "pods",
        "question": "Create a simple Pod named ‘demo-pod running the latest nginx image" (notice how the exact fields expected match with the answer),
        "source": "https://kubernetes.io/docs/concepts/workloads/pods/",
        "suggested_answer": """ | 
            apiVersion: v1
            kind: Pod
            metadata:
              name: demo-pod
            spec:
              containers:
              - name: main
                image: nginx:latest
            """ (this must be properly formatted yaml) 
        "user_answer": "" (after answered)
		"ai_feedback": "" (after answered)
    }


-  Question Menu 
	+ do not write the title of the menu literally
	+ it comes right after the text of the question
	+ quit should bring them back to the main menu 
	+ the line below the menu should be blank, a blank REPL that user can navigate like a normal CLI, users can delete or navigate back/forward with arrow keys, can scroll up to get previously input lines
	+ when a user presses enter (or if the user quits vim), the question should be graded 
	+ once this loop is exited, and the results/feedback is shown, we should always move directly into the post-answer menu (below)
	+ do not want to rely on AI for verdict; but detailed AI feedback is helpful 
	+ if the answer is verbatim the same as the suggested answer, you do not need to show AI feedback
	+ v)im, c)lear, n)ext, p)revious, a)nswer s)ource, q)uit 
	________________(input line)

- AI feedback is shown after the user answers, before the post-answer menu

- Post Answer Menu 
	+ always comes after a question is answered)
	+ AI does not determine correct/missed; feedback is what is important from AI 
	+ user chooses to save as correct or missed, or delete as a bad question 
	+ if the answer is verbatim the same as the suggested answer, you do not need to show AI feedback
	+ source should be in both menus, its helpful in research 
	+ r)etry, c)orrect, m)issed, s)ource, d)elete question 

- kubernetes command and manifest tools
	+ test every single one of them 
	+ make a list of the ones that work 
	+ don't worry about static evaluation 
	+ AI feedback is a critical component

question_flow: 
	• Construct a system+user prompt (e.g. “You are a Kubernetes instructor… generate a true or false statement about <topic>…”)
	• Call our existing ai_chat helper in a loop until we have count unique questions
	• Parse the JSON response into your question dicts with keys id, topic, type: 'tf', question (starting “True or False: …”) and answer ('true' or 'false')
	• Filter out any questions already in correct_folder

question_generator
	- vocab definitions are repeated twice 
	- vocab definitions are far too simple; to truly cover the k8s API would require thousands and thousands of entries
	- difficulty is not even a concept in the current implementation of the quiz
	- static rules are going to produce results that are far too simplisitic
	- all of these functions must use AI to get the proper level of detail  
	- use advanced tooling specfied in docs/general_instructions.md

difficulty
	- is not a concept for now 
	- introduces too much complexity into the app 
	- remove it where you find it 
