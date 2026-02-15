# Introducing Zrb-Flow: Self-Healing Automation for People Who Actually Live in the CLI

If you spend your day wiring scripts together, babysitting CI jobs, or nudging Docker and Kubernetes back into shape, this launch is for you.

Meet **Zrb-Flow** — an AI-native automation layer designed for engineers who live in terminals, not dashboards.

Zrb-Flow sits on top of your existing scripts, containers, and clusters, then uses AI to **orchestrate, observe, and repair** your automation in real time. It doesn’t try to replace your tools. It **makes them smarter**.

---

## Why We Built Zrb-Flow

Most automation stacks today look like this:

- A pile of shell scripts and Makefiles
- A maze of CI/CD YAML
- Docker and Kubernetes configs sprinkled everywhere
- “It works on my machine” glued together with tribal knowledge

When something breaks, it’s always the same story:

1. A step fails.
2. Logs are cryptic.
3. Someone has to drop what they’re doing, SSH in, poke around, rerun things manually, and hope nothing else explodes.

You *have* automation, but you still end up doing **automation operations by hand**.

Zrb-Flow exists to fix that.

---

## What Zrb-Flow Actually Does

At its core, Zrb-Flow is an **AI-driven automation runtime** for CLI-first workflows that hooks directly into:

- **Docker** – Build, run, and manage containers with AI-aware pipelines.
- **Kubernetes** – Interact with clusters, deployments, and jobs as first-class automation targets.
- **Your CLI** – Shell scripts, Python tools, Make targets, `zrb` tasks, whatever you already use.

You define flows as **terminal-native automation** (commands, scripts, tasks). Zrb-Flow then:

1. **Executes** them with full context (env, logs, dependencies).
2. **Monitors** behavior and failure patterns.
3. **Uses AI to reason about what went wrong** when something breaks.
4. **Applies fixes or workarounds automatically** when it’s safe to do so.

---

## Self-Healing Pipelines: The Killer Feature

The signature feature of Zrb-Flow is **Self-Healing Pipelines**.

Instead of just failing on the first error, a Zrb-Flow pipeline can:

- Detect when a Docker image is missing, then **build or pull it automatically**.
- Notice a `kubectl` command failing due to context, then **switch to the right context or namespace**.
- Recognize transient issues (like a dependency registry hiccup) and **retry with backoff and better diagnostics**.
- Spot a broken shell script, **propose a patch**, and re-run the step with the fix applied.

In practice, that means fewer “why is the build red?” moments and more **“it fixed itself before I even noticed”**.

### A Concrete Example

Imagine a deploy pipeline step like this:

```bash
./scripts/build.sh && \
./scripts/push.sh && \
./scripts/deploy-k8s.sh
```

In a traditional setup, if `deploy-k8s.sh` fails because the Kubernetes context is wrong, the whole job goes red and waits for a human.

With **Zrb-Flow Self-Healing**:

1. The step fails.
2. Zrb-Flow inspects the command, logs, and environment.
3. It recognizes a context/namespace mismatch.
4. It adjusts the `kubectl` context (or prompts you once, then remembers).
5. It re-runs the deploy step.

Result: the pipeline recovers automatically. The failure becomes a **quiet self-correction** instead of a team-wide fire drill.

---

## Designed for Engineers, Not Just “Users”

Zrb-Flow is not a black box. It’s built for people who care about:

- **Transparency** – You see the commands, patches, and decisions Zrb-Flow makes.
- **Control** – Lock down what it’s allowed to change, and where it must ask first.
- **Composability** – Use it alongside your existing tools, not instead of them.

Some things you can do out of the box:

- Wrap existing bash scripts and turn them into **observable, self-healing flows**.
- Attach flows to Docker/Kubernetes operations and **codify your runbooks**.
- Let AI propose fixes to flaky jobs, while you keep the final say.

If your muscle memory is `kubectl`, `docker`, `make`, and `zrb`, Zrb-Flow is designed to **slot right into your current workflow**.

---

## How It Plays with Docker and Kubernetes

Zrb-Flow doesn’t reinvent containers or orchestration. It leverages what you already have:

### With Docker

- Build images as part of a flow (with smart cache-aware steps).
- Auto-retry builds on registry glitches with better diagnostics.
- Detect missing images and **resolve them automatically** before a step fails.

### With Kubernetes

- Run deployments, rollouts, and maintenance jobs as Zrb-Flow steps.
- Recover from common K8s issues: wrong context, missing namespace, out-of-date manifests.
- Attach self-healing behavior to jobs and cron-jobs so that **automation keeps running, not just failing**.

The end result: your Docker and Kubernetes automation becomes **more resilient, more observable, and less annoying to maintain**.

---

## Why This Matters Now

As we push more and more work into pipelines — builds, tests, security scans, provisioning, migrations — the failure modes get more complex. The scripts that used to be “good enough” are now business-critical.

We don’t just need *more* automation. We need automation that can:

- Understand context.
- Learn from past failures.
- Apply intelligent fixes.

That’s the gap Zrb-Flow is built to close.

---

## Try Zrb-Flow Today

If you’re the person people ping when “the pipeline is broken” or “the deploy is stuck,” Zrb-Flow is for you.

Install it, point it at your existing CLI workflows, and start turning fragile scripts into **self-healing automation**.

```bash
# Install Zrb-Flow
pip install zrb-flow

# Or add it to your project
pip install --upgrade zrb-flow
```

Once installed, plug it into your existing Zrb or CLI workflows and start defining flows that **fix themselves**.

**Stop babysitting scripts. Start shipping with Zrb-Flow.**
