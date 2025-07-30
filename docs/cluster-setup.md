# Setting Up a Kubernetes Cluster for Kubelingo

Many Kubelingo exercises require a running Kubernetes cluster to validate `kubectl` commands. If you run a quiz without a configured cluster, you will see connection errors.

Here are three ways to provide a cluster environment for your learning session, from most recommended to least.

## Option 1: Use a Real Local Cluster (Recommended)

This is the best option for a realistic learning experience. You'll interact with a genuine Kubernetes API server, and your skills will be directly transferable to production environments.

1.  **Install a local cluster tool** like [Kind](https://kind.sigs.k8s.io/docs/user/quick-start/#installation) or [Minikube](https://minikube.sigs.k8s.io/docs/start/).
2.  **Start the cluster** in a separate terminal before running Kubelingo:
    *   For Kind: `kind create cluster --name kubelingo-quiz`
    *   For Minikube: `minikube start`
3.  **Run Kubelingo**. Your `kubectl` will now automatically connect to the local cluster, and the exercises will work as expected.

## Option 2: Use AI Fallback Evaluation

If you don't have a local cluster and have an OpenAI API key, you can use the AI evaluation feature. The AI will analyze your command history instead of running commands against a live cluster.

-   Set the `OPENAI_API_KEY` environment variable.
-   Launch Kubelingo with the `--ai-eval` flag:
    ```bash
    kubelingo --module kubernetes --ai-eval
    ```

After you finish the "Work on Answer" shell, the AI will review your transcript and determine if your commands were correct.

## Option 3: Mock `kubectl` with a Stub (Advanced)

For zero-dependency, deterministic grading without a real cluster, you can ship a fake `kubectl` script with a specific question. This is an advanced technique for question authors.

-   In your question's data file (e.g., a `.md` or `.yaml` file), use `initial_files` to create a `kubectl` shell script.
-   Use `pre_shell_cmds` to make it executable.

Here is an example for a question:

```yaml
prompt: Check the rollout status of a deployment.
initial_files:
  kubectl: |
    #!/bin/sh
    # Fake rollout/status check always succeeds
    if [ "$1" = "rollout" ]; then exit 0; fi
    # Delegate everything else to real kubectl if present
    command kubectl "$@"
pre_shell_cmds:
  - "chmod +x kubectl"
validation_steps:
  - cmd: "kubectl rollout status deployment/frontend"
```

Now, when this specific question is run, its local `kubectl` stub will be executed and will always succeed for the `rollout` command.

### Summary

| Approach                          | Pros                                        | Cons                                                    |
| --------------------------------- | ------------------------------------------- | ------------------------------------------------------- |
| **1. Real Local Cluster**         | Most realistic, validates skills properly   | Requires installing Kind/Minikube                       |
| **2. AI Fallback Evaluation**     | No local cluster needed                     | Requires OpenAI key, evaluation is non-deterministic    |
| **3. Mock `kubectl` Stub**        | No dependencies, deterministic              | Must be configured per-question, not realistic practice |

For the best learning experience, we strongly recommend **Option 1**.
