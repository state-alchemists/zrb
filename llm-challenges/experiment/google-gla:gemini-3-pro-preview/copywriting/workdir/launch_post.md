# 🚀 Introducing Zrb-Flow: The Self-Healing Automation Engine for CLI Natives

We are thrilled to announce the launch of **Zrb-Flow**, the next-generation AI automation tool designed specifically for engineers who live in the terminal.

Stop context-switching between your IDE, your cluster dashboard, and ChatGPT. Zrb-Flow brings intelligent orchestration directly to your command line, deeply integrated with the tools you already use.

## Why Zrb-Flow?

Automation should be robust, not fragile. Zrb-Flow isn't just another task runner; it's an intelligent agent that understands your infrastructure.

### 🧠 Self-Healing Pipelines
This is the game-changer. We've all been there: a nightly build fails because of a minor syntax error or a transient dependency issue.

With Zrb-Flow's **Self-Healing Mode**, the system doesn't just crash and send you an email. It captures the error, analyzes the stack trace using advanced LLMs, applies a fix to the script, and **automatically retries**. It fixes broken scripts while you sleep.

### 🐋 Deep Docker & Kubernetes Integration
Zrb-Flow doesn't sit on top of your infrastructure; it hooks directly into it.
*   **Smart Context:** It reads your `Dockerfile` and K8s manifests to understand your architecture.
*   **Live Debugging:** Pipe logs directly into the AI for instant root-cause analysis on crashing pods.
*   **Seamless orchestration:** Spin up dev environments that match production parity with a single command.

### ⚡ Built for the CLI
No drag-and-drop interfaces. No web wizards. Just pure, unadulterated CLI power. Define workflows in Python or YAML, and control everything from your shell.

## Get Started

Ready to upgrade your workflow? Zrb-Flow is available today.

```bash
pip install zrb-flow
zrb-flow init
```

Welcome to the future of intelligent engineering.
