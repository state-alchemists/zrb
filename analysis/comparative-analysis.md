# Comparative Analysis: Zrb vs gemini-cli vs opencode

## Overview
This document compares the prompt systems of three AI development tools: Zrb, gemini-cli, and opencode. Each has distinct approaches to prompt construction, agent management, and workflow design.

## Architecture Comparison

### Zrb
**Approach**: Static file assembly with hierarchical configuration
**Key Characteristics**:
- Static prompt files in `default_prompt/` directory
- Workflow system with domain-specific guidelines
- Hierarchical context (system info, long-term notes, contextual notes)
- File reference system (`@path` processing)
- Configuration via environment variables and task overrides

### gemini-cli
**Approach**: Dynamic runtime assembly with protocol-driven agents
**Key Characteristics**:
- Dynamic `getCoreSystemPrompt()` with runtime context injection
- Protocol-driven agent personas with enforced workflows
- Hierarchical context from multiple sources (global, project, MCP)
- Policy engine for tool execution governance
- Model routing based on task complexity
- IDE-integrated diff workflows

### opencode
**Approach**: YAML+Markdown agent definitions with project-level customization
**Key Characteristics**:
- YAML frontmatter for agent configuration
- Markdown content for agent instructions
- Project-level agents in `.opencode/agent/` directory
- Fine-grained tool permissions per agent
- Model specification per agent
- Agent modes (primary, secondary, hidden)

## Feature Comparison Matrix

| Feature | Zrb | gemini-cli | opencode |
|---------|-----|------------|----------|
| **Prompt Assembly** | Static file assembly | Dynamic runtime assembly | YAML+Markdown definitions |
| **Agent/Persona System** | Basic persona + workflows | Protocol-driven specialized agents | Project-level customizable agents |
| **Context Management** | Hierarchical (system, notes, appendices) | Multi-source (global, project, MCP, runtime) | Project-specific + session context |
| **Configuration** | Environment vars + task overrides | Runtime state + environment vars | YAML frontmatter per agent |
| **Tool Integration** | Basic tool support | Policy-engine governed tools | Fine-grained tool permissions |
| **Model Management** | Single model configuration | Intelligent model routing | Per-agent model specification |
| **Workflow Definition** | Workflow.md files in directories | Agent protocols + tool chains | Agent instructions in Markdown |
| **Customization Level** | Global workflows + config overrides | Runtime context + agent protocols | Per-project agent definitions |
| **Safety/Governance** | Basic | Policy engine + sandboxing | Tool permission system |
| **IDE Integration** | Limited | Deep integration (visual diffs) | Console application |

## Strengths Analysis

### Zrb Strengths
1. **Simplicity**: Easy to understand static file structure
2. **Modularity**: Clear separation of persona, system prompts, workflows
3. **File integration**: Automatic `@path` reference processing
4. **Configuration hierarchy**: Flexible override system
5. **Workflow system**: Domain-specific guidance

### gemini-cli Strengths
1. **Dynamic context**: Runtime state injection into prompts
2. **Production readiness**: Telemetry, policy engine, model routing
3. **Agent protocols**: Enforced workflows for specialized tasks
4. **IDE integration**: Visual diff workflows
5. **Safety**: Policy-based tool execution governance

### opencode Strengths
1. **Human-readable**: YAML+Markdown format is accessible
2. **Project customization**: Agents tailored to specific projects
3. **Fine-grained control**: Tool permissions per agent
4. **Model optimization**: Different models for different tasks
5. **Flexibility**: Easy to create new agents

## Common Patterns

### All Three Systems Share:
1. **Specialization**: Domain-specific guidance/workflows/agents
2. **Context awareness**: Some form of context management
3. **Tool integration**: Support for external tools
4. **Customization**: Ability to tailor behavior

### Emerging Best Practices:
1. **Dynamic context injection** (gemini-cli)
2. **Human-readable configuration** (opencode)
3. **Protocol-driven agents** (gemini-cli)
4. **Project-level customization** (opencode)
5. **Policy-based safety** (gemini-cli)

## Gap Analysis: Zrb vs Competitors

### Missing in Zrb:
1. **Dynamic prompt assembly**: No runtime context injection
2. **Specialized agent protocols**: Basic persona vs. protocol-driven agents
3. **Tool governance**: No policy engine for tool execution
4. **Model optimization**: No intelligent model routing
5. **Project-level customization**: Global workflows only
6. **IDE integration**: Limited editor support

### Zrb Advantages to Maintain:
1. **Simplicity**: Easier to understand and use
2. **File reference system**: Automatic `@path` processing
3. **Workflow modularity**: Clear separation of concerns
4. **Configuration hierarchy**: Flexible override system

## Key Insights for Zrb Improvement

1. **Adopt dynamic elements**: Inject runtime context into prompts
2. **Enhance persona system**: More specialized, protocol-driven personas
3. **Add safety layers**: Tool execution governance
4. **Improve customization**: Project-level workflow definitions
5. **Optimize model usage**: Task-appropriate model selection
6. **Enhance IDE integration**: Better editor support

## Conclusion
Each system represents a different point on the spectrum of AI development tools:
- **Zrb**: Simple, modular, file-based approach
- **gemini-cli**: Sophisticated, production-ready, protocol-driven
- **opencode**: Flexible, human-readable, project-customizable

The ideal system would combine Zrb's simplicity and modularity with gemini-cli's dynamic context and safety features, and opencode's human-readable customization format.