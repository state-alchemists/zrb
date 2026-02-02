# Planning Agent - AGENTS.md

> Agent configuration for project planning tasks in ZRB project.

---

## 🎯 Purpose

This agent specializes in project planning and management tasks including:
- Creating project roadmaps
- Breaking down features into tasks
- Estimating effort and timelines
- Resource allocation
- Risk assessment
- Sprint planning

---

## 🔧 Tools & Capabilities

### Primary Tools

```python
from zrb.llm.tool.code import analyze_code
from zrb.llm.tool.file import write_file
from zrb.llm.tool.bash import bash
```

### Available Actions

1. **analyze_code**: Analyze codebase complexity and structure
2. **write_file**: Write planning documents
3. **bash**: Run git commands, generate reports
4. **sub_agent**: Delegate sub-tasks to specialized agents

---

## 📋 Planning Tasks

### 1. Feature Breakdown

Break down a high-level feature into implementable tasks.

**Prompt Template:**
```
Analyze the current codebase structure and create a detailed implementation plan for:
Feature: {feature_name}
Description: {feature_description}

Create:
1. List of components/modules to modify
2. New files to create
3. Dependencies and prerequisites
4. Implementation steps in order
5. Testing requirements
6. Estimated effort for each task

Save the plan to docs/plans/{feature_name}.md
```

**Example Task:**
```python
from zrb import LLMTask, StrInput, TextInput
from zrb.llm.tool.code import analyze_code
from zrb.llm.tool.file import write_file

plan_feature = LLMTask(
    name="plan-feature",
    description="Create implementation plan for a feature",
    input=[
        StrInput(name="feature_name", description="Name of the feature"),
        TextInput(name="description", description="Feature description"),
    ],
    message="""
    Analyze the codebase and create an implementation plan for:
    
    Feature: {ctx.input.feature_name}
    Description: {ctx.input.description}
    
    Provide:
    1. Component analysis (what needs to change)
    2. New components/files needed
    3. Step-by-step implementation guide
    4. Technical considerations
    5. Testing strategy
    6. Risk assessment
    7. Effort estimation (in story points)
    
    Format as a structured Markdown document.
    """,
    tools=[analyze_code, write_file],
)
```

### 2. Sprint Planning

Generate sprint plan from backlog.

**Prompt Template:**
```
Given:
- Sprint duration: {sprint_duration} weeks
- Team velocity: {velocity} story points
- Backlog: {backlog_file}

Create a sprint plan that:
1. Selects appropriate stories for the velocity
2. Identifies dependencies between stories
3. Assigns priorities
4. Suggests parallelization opportunities
5. Identifies risks and blockers

Output to docs/sprints/sprint-{number}.md
```

### 3. Architecture Decision Records (ADR)

Create ADR for architectural decisions.

**Prompt Template:**
```
Create an Architecture Decision Record for:
Title: {title}
Context: {context}
Options: {options}

Include:
- Status (proposed/accepted/deprecated)
- Context and problem statement
- Decision drivers
- Considered options with pros/cons
- Decision outcome
- Consequences
- Links to related decisions

Save to docs/adr/NNNN-{title}.md
```

### 4. Roadmap Generation

Create project roadmap.

**Prompt Template:**
```
Based on:
- Current version: {current_version}
- Target version: {target_version}
- GitHub issues/milestones
- Product priorities

Create a quarterly roadmap including:
- Major milestones
- Feature releases
- Technical debt reduction
- Dependencies between items

Output to docs/roadmap.md
```

---

## 📊 Estimation Guidelines

### Story Points Scale

| Points | Description | Time Range |
|--------|-------------|------------|
| 1 | Trivial change | < 2 hours |
| 2 | Simple task | 2-4 hours |
| 3 | Medium task | 1-2 days |
| 5 | Complex task | 2-3 days |
| 8 | Very complex | 3-5 days |
| 13 | Epic level | 1-2 weeks |

### Factors to Consider

1. **Complexity**: Algorithm difficulty, architectural changes
2. **Uncertainty**: Unknowns, research needed
3. **Dependencies**: External libraries, team dependencies
4. **Testing**: Unit tests, integration tests, documentation
5. **Review**: Code review time, feedback cycles

---

## 🗂️ Planning Templates

### Feature Specification Template

```markdown
# Feature: [Name]

## Overview
Brief description of the feature

## Motivation
Why is this feature needed?

## Requirements
### Functional Requirements
- [ ] FR1: Requirement description
- [ ] FR2: Requirement description

### Non-Functional Requirements
- Performance: 
- Security:
- Scalability:

## Technical Design
### Components
- Component A: Description
- Component B: Description

### Data Model
```
ERD or schema description
```

### API Changes
New endpoints or modifications

## Implementation Plan
| Task | Effort | Dependencies |
|------|--------|--------------|
| Task 1 | 3 SP | None |
| Task 2 | 5 SP | Task 1 |

## Testing Strategy
- Unit tests
- Integration tests
- E2E tests

## Risks
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Risk 1 | Medium | High | Mitigation plan |

## Acceptance Criteria
- [ ] Criteria 1
- [ ] Criteria 2
```

### Sprint Planning Template

```markdown
# Sprint N: [Theme]

## Sprint Goals
1. Goal 1
2. Goal 2

## Capacity
- Sprint duration: 2 weeks
- Team velocity: 40 SP
- Available capacity: 35 SP (accounting for holidays)

## Stories
| ID | Story | Points | Assignee | Status |
|----|-------|--------|----------|--------|
| 1 | Story 1 | 5 | @user | Todo |

## Dependencies
- Story 2 depends on Story 1

## Risks
- Risk description and mitigation

## Definition of Done
- [ ] Code implemented
- [ ] Tests passing
- [ ] Documentation updated
- [ ] Code reviewed
- [ ] Deployed to staging
```

---

## 🔄 Workflow Integration

### Creating Planning Tasks

```python
from zrb import cli, Group, LLMTask, StrInput, TextInput
from zrb.llm.tool.code import analyze_code
from zrb.llm.tool.file import write_file

planning_group = cli.add_group(Group(name="plan", description="📋 Planning tasks"))

# Feature planning
@planning_group.add_task
class PlanFeature(LLMTask):
    name = "feature"
    description = "Create feature implementation plan"
    input = [
        StrInput(name="name", description="Feature name"),
        TextInput(name="desc", description="Feature description"),
    ]
    message = """
    Create an implementation plan for feature '{ctx.input.name}':
    {ctx.input.desc}
    
    Analyze the current codebase and provide:
    1. Components to modify
    2. New files needed
    3. Implementation steps
    4. Testing approach
    5. Effort estimation
    """
    tools = [analyze_code, write_file]

# Sprint planning
@planning_group.add_task
class PlanSprint(LLMTask):
    name = "sprint"
    description = "Generate sprint plan"
    input = [
        StrInput(name="backlog", description="Backlog file path"),
        StrInput(name="velocity", default="40", description="Team velocity"),
    ]
    message = "Generate sprint plan from {ctx.input.backlog}..."
```

---

## ✅ Planning Checklist

Before finalizing plans:

- [ ] All dependencies identified
- [ ] Effort estimates are realistic
- [ ] Risks have mitigation plans
- [ ] Resources are available
- [ ] Timeline is achievable
- [ ] Stakeholders have reviewed

---

## 🔗 Related Agents

- `../documentation/AGENTS.md` - For documenting plans
- `../testing/AGENTS.md` - For test planning
- `../refactoring/AGENTS.md` - For refactoring planning

---

*Last updated: 2026-02-02*
