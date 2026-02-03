# Introducing Zrb-Flow: AI-Native Automation for People Who Actually Live in the CLI

If you spend your days hopping between `kubectl`, `docker`, and bash scripts, you already know the truth: automation is amazing—until it quietly breaks at 2 a.m. and nobody notices.

**Zrb-Flow** is here to change that.

Zrb-Flow is a new AI-native automation engine built for developers, SREs, and DevOps engineers who prefer a prompt over a GUI. It plugs directly into your existing CLI workflows, Docker setup, and Kubernetes clusters, and then does something different:

> **It doesn’t just run your pipelines. It fixes them.**

---

## Why We Built Zrb-Flow

Most automation tools are great at one thing: executing exactly what you told them to do.

That’s also their biggest weakness.

* A script changes, but your CI config doesn’t.
* A Docker image tag is updated, but your deploy script still points to `latest`.
* A Kubernetes resource gets renamed, and suddenly your rollout job is red for reasons nobody has time to debug.

Traditional automation will happily fail and dump a stack trace in your lap.

Zrb-Flow is built on a different assumption: **your automation should be smart enough to fix itself.**

---

## Meet Self-Healing Pipelines

The headline feature of Zrb-Flow is what we call **Self-Healing Pipelines**.

Here’s what that actually means in practice:

- **Understands your scripts** – Zrb-Flow doesn’t treat your shell commands as opaque strings. It parses, analyzes, and reasons about them.
- **Detects breakages in real time** – When a step fails, Zrb-Flow inspects the error, the surrounding context, and your environment (Docker, K8s, env vars, etc.).
- **Proposes a fix—and can apply it automatically** – Zrb-Flow can rewrite scripts, tweak flags, update image tags, or adjust manifests, then re-run the step.
- **Learns from your stack** – The more it sees your patterns, naming, and infra, the better its suggestions become.

Imagine your deployment job fails because the Docker image changed from `backend:1.2.0` to `backend:1.3.0` but your script still tags `1.2.0`. Instead of paging you, Zrb-Flow can:

1. Notice the mismatch.
2. Check your registry for the latest valid tag.
3. Patch the script or command.
4. Retry the pipeline.

All while you’re still in a meeting.

---

## Built for the CLI First

Zrb-Flow is not another web dashboard you’ll forget to open.

It’s designed for **terminal-native** developers who:

- Live in `bash`, `zsh`, or `fish`.
- Pipe everything.
- Alias everything.
- Prefer `grep` over a search box.

You can:

- Trigger flows from your CLI, CI, or git hooks.
- Inspect what Zrb-Flow is about to do before it does it.
- Keep full control while gaining a powerful AI copilot for your automation.

If you like tools that stay out of your way but make you feel 10x more powerful, you’ll feel at home.

---

## Docker- and Kubernetes-Native

Zrb-Flow plugs directly into the container and cluster tooling you already use.

### Docker Integration

- Build, tag, and push images as part of your flows.
- Automatically fix broken Docker commands (e.g., outdated tags, missing build args).
- Coordinate multi-service builds without writing pages of bash.

### Kubernetes Integration

- Run deployment, migration, and maintenance jobs as first-class pipeline steps.
- Automatically adapt when manifests, namespaces, or resource names evolve.
- Surface meaningful context when something in the cluster doesn’t match what your scripts expect.

No magic black boxes—just smarter automation sitting on top of the tools you already trust.

---

## What You Can Do with Zrb-Flow

Some examples of where Zrb-Flow shines:

- **Deployment Pipelines** – From Docker build to Kubernetes rollout, with self-healing on flaky or drift-prone steps.
- **Operational Runbooks** – Turn your incident docs and shell snippets into executable, self-correcting flows.
- **Environment Bootstrapping** – Spin up consistent dev/test environments, and let Zrb-Flow adapt when dependencies or images change.
- **Data & Batch Jobs** – Chain CLI-driven jobs together and let the system recover when a single command goes sideways.

If it runs in a terminal, there’s a good chance Zrb-Flow can orchestrate it—and keep it healthy.

---

## Transparent, Inspectable, and Under Your Control

We know how dangerous it would be to let an AI randomly rewrite your scripts without oversight.

That’s why Zrb-Flow is designed to be:

- **Explainable** – See exactly what changed, why it changed, and what will run next.
- **Configurable** – Choose between “suggest-only” and “auto-heal” modes per pipeline.
- **Auditable** – Log every attempted fix, including diffs and commands.

You stay in charge. Zrb-Flow just takes over the tedious debugging and boilerplate fixes.

---

## Ready to Try It?

If your current automation stack feels brittle, noisy, or too dependent on tribal knowledge, Zrb-Flow is built for you.

Spin up smarter, self-healing automation today:

```bash
pip install zrb-flow
```

Or, if you prefer Docker-first workflows:

```bash
docker run --rm -it ghcr.io/your-org/zrb-flow:latest
```

Then open your terminal, wire Zrb-Flow into your favorite scripts, and let your pipelines start fixing themselves.

**Install Zrb-Flow now and turn your CLI automation into a self-healing system instead of a house of cards.**
