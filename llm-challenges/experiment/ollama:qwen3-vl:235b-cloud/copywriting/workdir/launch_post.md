# Announcing Zrb-Flow: Self-Healing Automation for CLI Power Users

🚀 **Your pipelines just got an AI-powered upgrade.** Today we're excited to launch **Zrb-Flow** – the missing link between your CLI wizardry and modern infrastructure (Docker, Kubernetes) that *fixes itself* when things go wrong.

## Why This Changes Everything

Tired of debugging pipeline failures at 2 AM? Zrb-Flow’s **Self-Healing Pipelines** analyze broken scripts in real-time and automatically generate patches. Whether it’s a missing volume mount in your Docker compose or a misconfigured K8s deployment, our AI:
- 🔍 Diagnoses failures by cross-referencing logs and manifests
- ✨ Proposes corrections with full context-aware explanations
- 🤖 Executes fixes *without* waiting for your approval (configurable safety thresholds)

## Built for the CLI-First Workflow

No more context switching between dashboards. Zrb-Flow integrates seamlessly with your terminal:

```bash
$ zrb flow run --self-heal my-broken-pipeline
> [AI] Detected missing secret reference in deployment.yaml
> Proposed fix: Add 'MY_SECRET' to envFrom
> ✅ Applied correction and restarted pipeline
```

## Get Started in 30 Seconds

For Docker and Kubernetes users who live in the terminal:

```bash
pip install zrb-flow
zrb flow init
```

👉 **[Join 1,200+ early adopters](https://zrb.dev/flow) and transform your automation workflow today**

*Zrb-Flow: Because infrastructure should be as smart as the engineers who build it.*