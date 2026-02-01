# Introducing Zrb-Flow: AI-Native Automation for the CLI (with Docker + Kubernetes Built In)

Today we’re launching **Zrb-Flow**, a new automation tool for engineers who live in the terminal and ship real systems.

If your workflow involves a mix of shell scripts, Docker, Kubernetes manifests, and “just one more hotfix” to get a pipeline green again—Zrb-Flow is built for you. It’s a **CLI-first automation engine** with **AI assistance** designed to help you move faster *without* sacrificing reliability.

---

## Why Zrb-Flow

Modern delivery stacks are a patchwork:

- Local scripts that grew into “build systems”
- Docker images that need consistent, repeatable steps
- Kubernetes deployments where one tiny drift can break a release
- CI pipelines that fail for reasons that are obvious *after* you’ve lost an hour

Zrb-Flow unifies those moving parts into a single, operator-friendly workflow—while adding AI capabilities that help you diagnose, repair, and evolve automation safely.

---

## Built for CLI power users

Zrb-Flow is designed for teams that prefer **transparent, scriptable automation** over opaque UIs.

You define tasks as code, chain them together, and run them from your terminal or CI environment. The result is a tool that feels like a natural extension of how engineers already work:

- Fast iteration loops
- Composable commands
- Minimal ceremony
- Easy integration into existing repos

---

## Docker and Kubernetes integration that’s not an afterthought

Zrb-Flow hooks directly into **Docker** and **Kubernetes** workflows so you can automate end-to-end delivery:

- Build, tag, and push images predictably
- Run containerized tasks consistently across dev and CI
n- Orchestrate Kubernetes deployments and operational checks
- Bake readiness/health checks into your task graph

If your current automation is a mix of Makefiles, bash, and tribal knowledge, Zrb-Flow helps you turn it into something structured—and repeatable.

---

## The standout feature: Self-Healing Pipelines

Automation breaks. Scripts drift. Environments change. Dependencies update. And suddenly the “working” pipeline fails at 2:13 AM.

**Zrb-Flow’s “Self-Healing Pipelines”** are built to address that reality.

When a task fails, Zrb-Flow can use AI to:

- Analyze the failure context (command output, environment, recent changes)
- Suggest fixes to broken scripts or task definitions
- Apply safe, minimal modifications
- Re-run verification steps to confirm the pipeline is healthy again

The goal isn’t to replace engineers—it’s to eliminate the repetitive, time-sink debugging that slows teams down.

**Think of it as an on-call assistant for your automation layer:** pragmatic fixes, fast feedback, and validation that the repair actually worked.

---

## What you can do with Zrb-Flow right away

Here are a few common patterns teams are using Zrb-Flow for:

- **Build & release automation:** from local builds to CI pipelines
- **Environment bootstrapping:** repeatable dev/staging/prod setup tasks
- **Container workflows:** consistent Docker-based execution
- **Kubernetes operations:** deployments, checks, and automated rollouts
- **Reliability-driven automation:** self-healing tasks that keep delivery moving

---

## Get started: install Zrb-Flow

Ready to try it?

1. Install **Zrb-Flow**:
   - Follow the installation instructions in your distribution/package manager (or your internal setup guide).
2. Initialize it in a repo and run your first task.
3. Turn your existing scripts into a durable automation graph—and let Self-Healing Pipelines keep it healthy.

**Install Zrb-Flow today and start shipping faster from the terminal.**
