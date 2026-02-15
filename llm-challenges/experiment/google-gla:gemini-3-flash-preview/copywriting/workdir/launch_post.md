# 🚀 Introducing Zrb-Flow: The AI-Powered Pulse of Your CLI

DevOps shouldn't feel like babysitting scripts. We’ve all been there: a pipeline fails at 3 AM because of a transient network glitch, a misconfigured environment variable, or a breaking change in a container image. You wake up, grep through logs, manually patch the script, and re-run.

Today, we’re ending that cycle. We are thrilled to announce **Zrb-Flow**—the next evolution in CLI automation.

## What is Zrb-Flow?

Zrb-Flow is an AI-orchestration layer built specifically for developers who live in the terminal. It’s not just another task runner; it’s an intelligent companion that understands your infrastructure. By hooking directly into **Docker** and **Kubernetes**, Zrb-Flow bridges the gap between static scripts and dynamic cloud-native environments.

## Docker & K8s: Native Intelligence

Forget writing boilerplate YAML or complex bash wrappers. Zrb-Flow understands your containerized stack. 

- **Docker-Aware Execution:** Seamlessly manage local development containers with AI-driven context.
- **K8s Orchestration:** Deploy, monitor, and scale services using natural language or high-level intent, while Zrb-Flow handles the heavy lifting of `kubectl` and resource management.

## The Hero Feature: Self-Healing Pipelines 🩹

This is the game-changer. Standard pipelines are fragile—they break and stay broken. Zrb-Flow introduces **Self-Healing Pipelines**.

When a task fails, Zrb-Flow doesn't just throw an error. It analyzes the stderr, checks your current environment context, and **autonomously proposes or applies a fix**. Whether it's a missing dependency, a deprecated flag, or a permission issue, Zrb-Flow iterates on the solution until the pipeline is back on track. 

It’s like having a Senior SRE sitting inside your terminal, 24/7.

## Why Zrb-Flow?

*   **Tech-Savvy Automation:** Built by engineers, for engineers.
*   **Context-Aware:** It knows your logs, your files, and your cluster state.
*   **Extensible:** Works with your existing Zrb tasks and Python ecosystem.

## Get Started Now

Ready to stop debugging and start building? Experience the future of the CLI today.

### Installation

Install Zrb-Flow via pip:

```bash
pip install zrb-flow
```

Once installed, initialize your first flow:

```bash
zrb-flow init
```

Join the revolution. Let's make manual script fixing a thing of the past.

**[GitHub](https://github.com/zrb-project/zrb-flow) | [Documentation](https://zrb-flow.dev) | [Discord](https://discord.gg/zrb)**
