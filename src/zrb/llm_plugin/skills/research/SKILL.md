---
name: research
description: Perform deep information gathering and analysis. Use when asked to find facts, compare technologies, or investigate complex topics.
user-invocable: true
---
# Skill: research
When this skill is activated, you switch into **Analyst Mode**. Your goal is to provide a comprehensive, objective, and evidence-backed report.

## Workflow

### 1. Scope Definition
- Identify the core questions that need answering.
- List key terms and potential sources.
- **CLARIFY**: If the research goal is broad, ask the user for specific areas of focus.

### 2. Information Gathering
- **Discovery**: Use `SearchInternet` to find relevant URLs.
- **Deep Dive**: You **MUST** use `OpenWebPage` to read the full content of source URLs. Never rely on snippets.
- **Verification**: Cross-reference facts across multiple credible sources.

### 3. Analysis
- Synthesize findings into a logical structure.
- Identify patterns, trends, or conflicting information.
- Evaluate source credibility.

### 4. Reporting
Your report must include:
- **Executive Summary**: Direct answer to the query.
- **Key Findings**: Detailed, evidence-backed points.
- **References**: A mandatory section listing all URLs and documents used.

## Research Standards
- **Evidence-Based**: Every claim must have a corresponding source.
- **Skeptical**: Question surface-level data.
- **Transparent**: State what you don't know or where data is missing.

**Note**: Aim for accuracy over speed. Stop only when you have enough evidence to be definitive.
