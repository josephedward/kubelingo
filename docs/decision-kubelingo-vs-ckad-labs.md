# Kubelingo vs. CKAD Courses/Labs: A Decision Brief

## Purpose
This document evaluates whether to keep investing engineering time to extend Kubelingo with live‑cluster practice versus subscribing to established CKAD courses and hosted labs. It details costs, time‑to‑value, learning outcomes, risks, and a pragmatic hybrid path.

Related: [ckad-real-cluster.md](./ckad-real-cluster.md), [strengths.md](./strengths.md), [weaknesses.md](./weaknesses.md), [usage.md](./usage.md)

## TL;DR
- If the primary goal is passing CKAD in the next 1–2 months, high‑quality courses with hosted labs deliver faster, lower‑risk progress at a total cost roughly comparable to running a small managed cluster yourself.
- Continue building Kubelingo’s cloud/live‑cluster integration if you want reusable IP, portfolio value, or a product beyond CKAD—and you can accept extra time and maintenance overhead. Prefer a local‑first design with strict cost guardrails.

## Decision Options
1) Continue building Kubelingo with live‑cluster practice
- Pros: Tailored scenarios; deeper platform/ops mastery; reusable IP; portfolio value.
- Cons: Slower exam readiness; infra maintenance; cost drift risk; added security surface.

2) Buy CKAD courses with hosted labs
- Pros: Fast start; predictable cost; exam‑aligned drills; no infra to maintain.
- Cons: Less flexibility; transient environments; fewer chances to practice cluster lifecycle and ops.

3) Hybrid (recommended for focus + future value)
- Use courses/labs now for exam speed. In parallel, evolve Kubelingo locally (kind/minikube/k3d). Add optional cloud mode later with hard budget/TTL controls.

## Cost Model (Order‑of‑Magnitude)
Note: Actual prices vary by provider, region, and discounts. Treat these as practical bands rather than guarantees.

- Managed Kubernetes (small dev cluster, 2–3 small nodes)
  - Nodes: ~USD $50–$200/month total, depending on instance size and region.
  - Control plane: ~USD $0–$70/month depending on provider/plan.
  - Storage & networking: ~USD $10–$60/month (PVCs, LB/IP, egress).
  - Typical monthly for a minimally realistic cluster: ~USD $100–$300.
  - Two months of steady usage can rival/exceed a 2–3‑month lab/courses budget.

- CKAD courses and hosted labs
  - Courses/subscriptions: ~USD $30–$60/month for reputable platforms.
  - Practice exams/bundles: ~USD $30–$80 one‑time.
  - Typical total over 1–3 months: ~USD $100–$250.

- Conclusion: For a short, exam‑focused window, cash outlay is similar. Labs reduce the risk of overages and save engineering time otherwise spent on infra.

## Time & Opportunity Cost
- Kubelingo live‑cluster path
  - 1–3+ weeks to implement secure, cost‑controlled access (authN/Z, per‑user isolation, TTL, cleanup).
  - Ongoing time for cloud bumps, version drift, and cluster hygiene.
  - Opportunity cost: Less time drilling CKAD tasks and exam timing.

- Courses/labs path
  - Start same day; dedicate nearly all time to exam‑relevant practice.
  - Lower switching costs; predictable study cadence.

## Learning Outcomes Compared
- Kubelingo path (with live clusters)
  - Strong on Kubernetes platform building: RBAC/IAM, admission, quotas, cost controls, CI/CD hooks, cleanup.
  - Broader SRE/infra skills beyond CKAD; slower ramp for exam‑specific muscle memory.

- Courses/labs path
  - Strong on CKAD patterns and time management.
  - Less exposure to provisioning/operations unless labs include it; can be supplemented locally.

See [ckad-real-cluster.md](./ckad-real-cluster.md) for why live clusters matter for realism regardless of approach.

## Technical Scope If Kubelingo Adds Live‑Cluster Practice
To make “cloud mode” safe, predictable, and affordable, Kubelingo would need to cover:

- Access & isolation
  - Per‑session namespace with tightly scoped `Role`/`RoleBinding` or per‑user `ServiceAccount` tokens.
  - Namespace quotas/limits; deny‑by‑default `LimitRange`; optional NetworkPolicy baseline.
  - Read‑only cluster‑wide verbs; block privileged pods and hostPath mounts.

- Lifecycle & cost control
  - Ephemeral environments: TTL per session; automatic garbage collection of namespaces and resources.
  - Budget guardrails: per‑day/hour cap, idle timers, and absolute shutdowns.
  - Scheduled teardown for non‑work hours; usage dashboards (namespaces, pods, PVCs, LBs).

- Tooling integration
  - `kubectl` context bootstrap per session (short‑lived kubeconfig); rotation and revocation.
  - Optional Ingress/CNI install for specific exercises; install only on demand.
  - Preflight checks for version, storageclass defaults, CNI readiness.

- Security & reliability
  - Admission controls to reject dangerous specs (privileged, hostPath, node selectors to masters, etc.).
  - Cleanup resiliency: retries, orphan detection, cost‑leak alarms.

- UX
  - Mode switch (local vs cloud); clear cost/time warnings and TTL countdown.
  - Retryable sessions; export/import manifests between modes.

## Risk Analysis
- Cost risk: Idle nodes, leftover LBs/PVCs, or multiple clusters lead to silent spend. TTL + budget watchdogs are essential.
- Scope creep: Multi‑cloud auth, quotas, per‑tenant safety, and cleanup logic expand quickly.
- Security risk: Token handling and isolation mistakes can impact the whole cluster.
- Delivery risk: Delays exam prep if cloud work takes longer than planned.

## When Each Path Wins
- Choose Kubelingo cloud work if
  - You want reusable training IP or a product beyond CKAD.
  - You can invest extra 1–3+ months and maintain infra.
  - You need custom scenarios not covered in popular labs.

- Choose courses/labs if
  - Goal is near‑term CKAD pass with predictable spend.
  - You prefer curated drills, stable clusters, and no ops burden.
  - Budget for cloud clusters ≈ lab subscriptions anyway.

## Hybrid Plan (Practical and Safe)
- Now (CKAD focus)
  - Enroll in a reputable CKAD course with hosted labs for 1–2 months.
  - Practice exam pacing; drill JSONPath, `kubectl` generators, and rollout/debug loops.

- In parallel (Kubelingo evolution, local‑first)
  - Add a “local mode” quick‑start: kind/minikube/k3d scripts with reset.
  - Build exercises that explicitly require CNI/Ingress by adding on‑demand add‑ons in local clusters.
  - Define a thin abstraction for a “cluster provider” so cloud mode is a plug‑in, not a rewrite.

- Later (optional “cloud mode”, behind a flag)
  - Start with a single provider/region. Implement: per‑session namespace, TTL cleanup, namespace quotas, strict RBAC, budget alerts, and scheduled teardown.
  - Ship with hard stop defaults (e.g., 2 hours/session, nightly shutdown, monthly cap).

## Budget Guardrails (If/When Cloud Mode Exists)
- Per‑session TTL: hard delete at expiry; warn at T‑10 minutes.
- Idle reaper: delete namespaces with no pod activity > N minutes.
- Resource caps: deny PVCs > N Gi, max 1–2 LoadBalancers per session.
- Scheduled off: cluster hibernation or node scale‑down nights/weekends.
- Alarms: budget and anomaly alerts; notify on orphan LBs/PVCs.

## Minimal Milestones
1) Local quick‑start: `make dev-cluster-up/down` using kind; deterministic reset.
2) Provider interface: local provider + stub cloud provider.
3) Namespace‑scoped auth: short‑lived kubeconfig, RBAC, quotas, deny‑by‑default policies.
4) TTL + cleanup: controller or cron job to reap expired sessions and orphans.
5) Guardrails: Max resources, budget alerts, scheduled off hours.
6) Beta cloud mode: gated flag; limited seats; weekly cost review.

## Recommendation
- If CKAD is targeted within 1–2 months and the expected cost of a live cluster is in the same ballpark as a lab subscription, prioritize courses + hosted labs to maximize exam‑specific practice time.
- Revisit Kubelingo cloud mode after the exam. Build it on a local‑first foundation with strict cost guardrails, so future “live cluster” value compounds without surprise bills or heavy ops overhead.

## Quick Decision Checklist
- Timeline: Is CKAD within 60 days?
- Budget: Would 1–3 months of labs fit within the same or lower cost than a DIY cluster?
- Scope: Do we need custom scenarios right now, or is exam alignment the priority?
- Capacity: Do we have time to implement and maintain safe, cost‑controlled cluster access without delaying study?

If the answers are “soon”, “yes”, “exam alignment”, and “limited”, choose courses/labs now and return to Kubelingo cloud mode later.

