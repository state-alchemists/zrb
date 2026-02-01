# Introducing Zrb-Flow: AI-Native Automation for Developers Who Live in the CLI

If you spend your days in a terminal, juggling Docker builds, Kubernetes deploys, and a growing pile of brittle scripts, this one’s for you.

Today we’re launching **Zrb-Flow** – an AI-native automation layer for CLI-first engineers. It plugs directly into your existing workflows, speaks Docker and Kubernetes fluently, and turns your ad‑hoc shell scripts into something that actually *wants* to keep working.

Think of it as: **`make`, but intelligent**. Or **GitHub Actions, but local, fast, and under your control**.

---

## Why We Built Zrb-Flow

Modern infra stacks are powerful—but also incredibly noisy:

- You’ve got **Docker images** to build, tag, and push.
- **Kubernetes manifests** to apply, roll back, and debug.
- A pile of **bash/Python scripts** that only two people on the team really understand.
- CI pipelines that fail for reasons no one has time to chase.

Most automation tools help you *run* this complexity. **Zrb-Flow helps you *tame* it.**

We wanted a tool that:

- Lives in the **CLI**, not hidden behind a web UI.
- Plays nicely with **Docker** and **K8s** instead of reinventing them.
- Uses **AI to repair** broken bits of automation instead of just printing stack traces.

That’s Zrb-Flow.

---

## What Is Zrb-Flow?

At its core, **Zrb-Flow** is an AI-augmented automation runner for terminal-native workflows.

- Define tasks as **simple commands or Python functions**.
- Chain them into **flows** that build, test, deploy, and validate your services.
- Let the built‑in **AI engine observe failures** and suggest (or apply) fixes.

It’s designed for developers who:

- Prefer `vim` over browser UIs.
- Already know Docker and Kubernetes.
- Want automation that’s **transparent, inspectable, and hackable**.

---

## Key Capabilities

### 1. Deep Docker & Kubernetes Integration

Zrb-Flow doesn’t pretend Docker and K8s don’t exist. It leans into them:

- **Docker-aware tasks** for building, tagging, and publishing images.
- Integrated **Kubernetes deploy flows** that can apply manifests, wait for readiness, and roll back on failure.
- Easy hooks to run **pre- and post-deploy checks** (migrations, smoke tests, health checks, etc.).

Instead of sprinkling `kubectl` and `docker` commands across random scripts, you define them as **first-class tasks** with clear inputs, outputs, and dependencies.

### 2. Self-Healing Pipelines

This is the fun part.

Zrb-Flow ships with **Self-Healing Pipelines**: when a task fails, the AI engine inspects the logs, the command, and the surrounding context to:

1. **Identify what broke** (a changed CLI flag, a renamed env var, a missing dependency, etc.).
2. **Propose a concrete fix** – e.g. updating a flag, adjusting a script, adding a missing step.
3. Optionally **apply the fix automatically** (with your approval).

Typical scenarios where this shines:

- Your Docker CLI changes a default behavior and your build script quietly dies.
- A Kubernetes manifest moves or a label changes and your rollout task stops matching pods.
- Someone “just tweaks” a script in `scripts/` and half your pipeline goes red.

Instead of spending an afternoon diffing shell history and CI logs, Zrb-Flow says:

> “This step failed because `kubectl rollout status` is targeting the wrong deployment name. Here’s the fix. Apply? (y/N)”

You’re still in control—but now you’ve got an assistant who can read logs at machine speed.

### 3. CLI-First, Code-First

Zrb-Flow is built around two simple ideas:

- **Everything is a task** – build, test, deploy, cleanup, migrations, checks.
- **Tasks are code** – version-controlled, reviewable, and reusable.

No YAML labyrinth required. You define flows in Python or simple config files, and run them via:

```bash
zrb flow deploy
```

or trigger individual steps:

```bash
zrb task docker-build
zrb task k8s-apply
```

The result is automation that is:

- **Discoverable** – `zrb list` shows you what exists.
- **Composable** – chain tasks, reuse them across projects.
- **Portable** – runs on your laptop, your CI runner, or inside a container.

### 4. Designed for Real Teams

Zrb-Flow is intentionally opinionated about collaboration:

- **Named flows** (`build`, `deploy`, `rollback`, `smoke-test`) that everyone can recognize.
- **Explicit inputs and env vars**, so onboarding doesn’t mean reading 800 lines of bash.
- **Consistent logging and output**, so your CI logs are actually readable.

New team members don’t need to reverse‑engineer your scripts. They can inspect the flows, run them locally, and let the AI explain failures in plain language.

---

## What Can You Automate with Zrb-Flow?

A few concrete examples:

- **Container builds**
  - Build, tag, and push images.
  - Run test suites inside containers.
  - Automatically bump versions or labels.

- **Kubernetes deployments**
  - Apply manifests and wait for readiness.
  - Run post-deploy smoke tests against services.
  - Roll back if health checks fail.

- **Environment setup**
  - Spin up local dev stacks using Docker Compose and K8s.
  - Initialize databases, seed data, and run migrations.

- **Maintenance & ops**
  - Scheduled cleanups, cache purges, log rotations.
  - Health checks and simple SLO/SLA verifications.

If it starts with a CLI command, it probably fits.

---

## Who Is Zrb-Flow For?

Zrb-Flow will feel natural if you are:

- A **DevOps / platform engineer** maintaining homegrown scripts and CI pipelines.
- A **backend or infra engineer** who prefers typing commands over clicking around.
- A **tech lead** trying to make your team’s automation less fragile and more transparent.

If you’ve ever said “it’s just a bash script” and regretted it six months later, this is aimed squarely at you.

---

## Getting Started

Ready to try it?

1. **Install Zrb-Flow** (assuming you have Python and pip installed):

   ```bash
   pip install zrb-flow
   ```

2. **Initialize a new flow in your repo**:

   ```bash
   zrb init
   ```

3. **Define a couple of tasks** (e.g., `docker-build`, `k8s-deploy`) and chain them into a `deploy` flow.

4. **Break something on purpose** and watch the **Self-Healing Pipelines** kick in with suggestions.

---

## Try It, Break It, Tell Us What Hurts

Zrb-Flow is built for real-world messiness, and we fully expect you to push it into weird corners.

Install it, wire it into a Docker/K8s workflow you care about, and see how it behaves when things go sideways.

👉 **Install Zrb-Flow now:**

```bash
pip install zrb-flow
```

Then jump back into your terminal and let your automation start fixing *itself*.
