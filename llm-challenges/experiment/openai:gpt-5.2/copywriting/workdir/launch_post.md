# Introducing Zrb-Flow: AI-Powered Automation for CLI, Docker, and Kubernetes

Today we’re launching **Zrb-Flow** — an AI automation tool built for people who live in the terminal and ship real systems.

Zrb-Flow turns your CLI into an intelligent, script-aware operator that can understand intent, orchestrate complex workflows, and integrate directly with **Docker** and **Kubernetes**. Whether you’re building, testing, deploying, or debugging production pipelines, Zrb-Flow helps you move faster while staying in control.

---

## Why Zrb-Flow

Modern engineering workflows are a patchwork of shell scripts, CI steps, YAML, container builds, and clusters. The glue code works… until it doesn’t.

Zrb-Flow is designed to reduce that friction:

- **AI-assisted CLI automation** that fits into the tools you already use
- **First-class Docker integration** for repeatable builds and local environments
- **Kubernetes-aware workflows** for shipping to real clusters with confidence
- **Composable automation** so you can standardize how your team runs common operations

---

## The standout feature: Self-Healing Pipelines

Scripts break for predictable reasons: missing dependencies, bad paths, changed environments, flaky services, outdated configs, and tiny differences between local + CI + production.

**Self-Healing Pipelines** is Zrb-Flow’s answer.

When a pipeline step fails, Zrb-Flow can:

- Detect what failed and **why** (not just the exit code)
- Suggest the most likely fix and apply it when appropriate
- Patch brittle scripts so they become **more resilient over time**
- Reduce time spent on reruns, log spelunking, and context switching

The goal isn’t to “hide errors.” The goal is to turn failures into a tight feedback loop where your automation gets smarter every run.

---

## Built for power users (without taking control away)

Zrb-Flow is built to be:

- **Terminal-native**: it fits into real CLI workflows
- **Transparent**: you can see what it plans to do before it does it
- **Pragmatic**: it automates the boring parts while keeping you in the driver’s seat
- **Ready for containers + clusters**: because that’s where the real work happens

If you’ve ever wished your scripts could diagnose themselves — and fix themselves — Zrb-Flow is for you.

---

## Get started

Install Zrb-Flow and try it on your current automation workflow — especially the one that breaks the most.

**Install now:**

```bash
# Replace with your preferred installation method
# (e.g., brew, pipx, curl installer, etc.)

zrb-flow --help
```

Want to see it in action? Start with a small pipeline, run it locally with Docker, then push the same flow to Kubernetes.

---

**Zrb-Flow is live.** Build faster. Ship safer. And let your pipelines heal themselves.
