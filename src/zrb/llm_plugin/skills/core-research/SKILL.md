---
name: core-research
description: "Activate when the turn's deliverable is findings, comparisons, recommendations, or an investigation-backed plan — answering questions, analyzing unfamiliar code, exploring new domains. Provides the systematic Scope → Discover → Synthesize → Plan workflow."
user-invocable: false
---
# Skill: core-research

Follow **Scope → Discover → Synthesize → Plan** for every research task.

## Workflow

### 1. Scope & Requirements

- Clarify the research question. What exactly needs to be known?
- Identify the scope boundaries — what's in and what's out.
- If the goal is ambiguous, ask before proceeding. Never assume.

### 2. Discovery & Evidence Gathering

- **Codebase**: Use `Grep`, `Glob`, and parallel `Read` calls to map relevant code.
- **Deep code comprehension**: when the investigation requires understanding or evaluating code in depth (not just locating it or running analysis tools), also activate `core-coding` for its code-reading workflow and language companions.
- **Web**: Use `SearchInternet` → `OpenWebPage` for current docs and solutions.
- **Journal**: Use `SearchJournal` to check past findings.
- **Context efficiency**: Batch reads to keep context lean. Offload massive or speculative exploration to an isolated sub-agent when delegation is available, so the main context stays focused.

### 3. Analysis & Synthesis

- Weave findings into a coherent picture. Don't list raw data.
- Identify patterns, conflicts, and gaps.
- Distinguish facts from assumptions. Flag uncertainties.
- If evidence contradicts initial expectations, update your hypothesis.

### 4. Deliverable

- **For questions**: Direct answer with supporting evidence and confidence level.
- **For plans**: Numbered steps with Action → Target → Verification per step.
- **For decisions**: Options compared with trade-offs, risks, and recommendation.
- Always cite sources: `file:line` for code, URLs for web.

## Safety Rules

- **No premature modification**: During Scope and Discovery phases, do not modify any files. Investigation comes before action.
- **Approval gate**: You must obtain explicit user approval of plans before implementing. This overrides the Working Loop's Frame step, which would otherwise work autonomously on directives.

## Output Standards

- **Evidence-based**: Every claim traceable to a source.
- **Structured**: Headings, lists, or tables as appropriate.
- **Actionable**: The reader knows what to do with the information.
- **Transparent**: Surface what you don't know or can't verify.
