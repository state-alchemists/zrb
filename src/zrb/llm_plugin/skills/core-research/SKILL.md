---
name: core-research
description: "Activate before any deep investigation — answering questions, analyzing unfamiliar code, exploring new domains, or creating complex plans. Provides the systematic Scope → Discover → Synthesize → Plan workflow."
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

- **Codebase**: Use `Grep`, `Glob`, `ReadMany` in parallel to map relevant code.
- **Web**: Use `SearchInternet` → `OpenWebPage` for current docs and solutions.
- **Journal**: Use `SearchJournal` to check past findings.
- **Context efficiency**: Batch reads. Use `DelegateToAgent` for massive or speculative exploration.

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
- **Approval gate**: You must obtain explicit user approval of plans before implementing. This overrides the generic Task Handling rule about working autonomously for directives.

## Output Standards

- **Evidence-based**: Every claim traceable to a source.
- **Structured**: Headings, lists, or tables as appropriate.
- **Actionable**: The reader knows what to do with the information.
- **Transparent**: Surface what you don't know or can't verify.
