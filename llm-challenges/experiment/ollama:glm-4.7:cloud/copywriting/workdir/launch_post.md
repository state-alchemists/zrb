# 🚀 Announcing Zrb-Flow: The AI-Powered CLI Automation Engine

CLI warriors, system architects, and DevOps dreamers — meet your new best friend.

We're incredibly excited to introduce **Zrb-Flow**, the AI-driven automation engine designed to transform how you interact with your command line. If you've ever wished your terminal could think, adapt, and occasionally save you from your own messy scripts, you're in for a treat.

---

## What is Zrb-Flow?

Zrb-Flow isn't just another CLI tool. It's an **intelligent automation layer** that lives at the intersection of your terminal, your containers, and your clusters. Think of it as having a senior DevOps engineer looking over your shoulder — one that understands Docker, speaks Kubernetes, and doesn't complain about debugging at 2 AM.

At its core, Zrb-Flow hooks directly into your existing workflows. You define tasks in Python, and Zrb-Flow orchestrates them into powerful, observable pipelines. But the real magic? It learns. It adapts. And when things break, it fixes them.

---

## ✨ Key Features

### Self-Healing Pipelines
**This is the feature that made us build Zrb-Flow.**

We've all been there: You write a fragile script, push it to production, and pray it survives the night. With Zrb-Flow's Self-Healing Pipelines, that prayer is no longer necessary.

When a task fails, Zrb-Flow doesn't just crash. It **analyzes the error**, **understands the context**, and **rewrites the fix**. Failed Docker commands? Zrb-Flow retries with the corrected flags. Broken K8s manifests? Zrb-Flow patches the YAML automatically.

It's like having a built-in rubber band for your automation.

### Native Docker & Kubernetes Integration
Zrb-Flow speaks container fluently:

- **Docker** tasks with built-in pull, build, and readiness checks
- **Kubernetes** deployments, service creation, and pod monitoring
- Automatic health checks before chaining dependent tasks
- Seamless environment injection across all containerized workloads

### Write in Python, Run in the Cloud
Define tasks using a clean, declarative Python API:

```python
from zrb import CmdTask, cli

cli.add_task(
    CmdTask(
        name="deploy-to-k8s",
        cmd="kubectl apply -f deployment.yaml",
        readiness_check=HttpCheck("http://localhost:8080/health")
    )
)
```

Simple, readable, and infinitely composable.

### Observability Out of the Box
No more "it's probably running on that server somewhere." Zrb-Flow provides:

- Real-time task execution logs
- Dependency graph visualization
- Cross-task data sharing via XCom
- Web UI for monitoring and manual intervention

### LLM-Native
Zrb-Flow integrates with your favorite LLMs (OpenAI, Google Vertex, DeepSeek, and more out of the box). The Self-Healing feature is powered by these integrations, but you can also use LLMs for:
- Generating boilerplate code
- Analyzing logs
- Creating documentation
- Writing test cases

---

## Who is Zrb-Flow For?

- **DevOps Engineers** who want automation that doesn't break unexpectedly
- **Backend Developers** tired of debugging pipeline failures
- **System Architects** building complex, distributed workflows
- **CLI Enthusiasts** who believe the terminal should be smarter

If you spend any time in a terminal and value automation, Zrb-Flow is for you.

---

## The Road Ahead

This is just the beginning. We're building:

- 📊 Enhanced analytics dashboard
- 🔄 Cross-cloud deployment support
- 🤖 More LLM integrations
- 🧩 Community task marketplace

---

## 📥 Install Zrb-Flow Today

Ready to build pipelines that fix themselves? Installation takes seconds:

```bash
pip install zrb
```

Once installed, initialize your first project:

```bash
zrb project init my-automation
cd my-automation
zrb chat
```

The `zrb chat` command opens an interactive AI session where you can describe what you want to automate, and Zrb-Flow will write the tasks for you.

---

## Get Involved

- **Documentation**: [docs.zaruba.dev](https://docs.zaruba.dev)
- **GitHub**: [github.com/state-alchemists/zaruba](https://github.com/state-alchemists/zaruba)
- **Discord**: Join our community for real-time support

---

**Build smarter. Automate faster. Heal automatically.**

Welcome to the future of CLI automation. Welcome to Zrb-Flow.

— The Zrb Team