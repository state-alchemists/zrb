# Gemini-CLI Prompt System Analysis

## Overview
gemini-cli is a sophisticated, production-grade AI-assisted development platform built by Google. It implements a comprehensive agent framework with dynamic prompt assembly, hierarchical agent architecture, and deep workflow management.

## Core Architecture

### 1. Dynamic Prompt System
gemini-cli constructs prompts dynamically at runtime rather than using static files:

- **`getCoreSystemPrompt()` function**: Dynamically generates instructions by injecting runtime context
- **Multi-source context assembly**: Combines global user memory, project-specific GEMINI.md files, and MCP server prompts
- **Environment-aware**: Adapts prompts based on model type, interactive mode, enabled tools, sandbox status, and git context

### 2. Context Hierarchy
The system assembles context from multiple discoverable sources:

1. **Global user memory**: `~/.gemini/` directory
2. **Project-specific context**: `GEMINI.md` files with `@import` support
3. **MCP server prompts**: Context from connected Model Context Protocol servers
4. **Runtime state**: Current tools, agents, sandbox status, git information

### 3. Specialized Agent Personas
gemini-cli uses protocol-driven agent personas rather than general assistants:

- **Codebase Investigator**: Hyper-specialized "reverse-engineering expert" with mandated `<scratchpad>` for structured reasoning
- **Local Agent Protocol**: All agents must call `complete_task` tool to signal success
- **Correction Personas**: Tightly constrained personas for specific fixes (e.g., Code-Editing Assistant)

## Key Components

### 1. Prompt Construction (`src/core/prompts.ts`)
- Dynamic system prompt generation with runtime context injection
- Model-specific configurations (temperature, thinking config)
- Environment variable overrides (`GEMINI_SYSTEM_MD`)

### 2. Agent System (`src/agents/`)
- Typed agent configurations (`PromptConfig`, `InputConfig`)
- `DelegateToAgentTool` for type-safe agent delegation
- `LocalAgentExecutor` with turn limits and isolated tool registries

### 3. Tool Framework
- Declarative tool definitions with Zod schema validation
- Policy engine for tool execution governance
- IDE-integrated diff workflows for file modifications

### 4. Model Management
- `ModelRouterService` with Chain of Responsibility pattern
- Intelligent routing based on task complexity
- Model health monitoring and fallback mechanisms

## Workflow Management

### 1. Agent Delegation
- Main LLM coordinates specialized sub-agents
- Unified tool interface for agent communication
- Protocol enforcement (e.g., must call `complete_task`)

### 2. Policy-Driven Execution
- TOML-based rule evaluation for tool calls
- User confirmation workflows with options like "ProceedAlways"
- Visual diff review in connected editors

### 3. Hook System
- 11 event types throughout agent lifecycle
- Extensibility points for custom behavior
- Message bus for system-wide communication

## Comparison with Zrb

### Strengths of gemini-cli
1. **Dynamic prompt assembly**: Context-aware prompts vs. Zrb's static file assembly
2. **Protocol-driven agents**: Specialized personas with enforced workflows
3. **Production-grade infrastructure**: Telemetry, policy engine, model routing
4. **Deep IDE integration**: First-class editor support with visual diffs
5. **Hierarchical context**: Multi-source context assembly with import support

### Areas where Zrb could learn
1. **Dynamic context injection**: Runtime state in prompts
2. **Specialized agent protocols**: Constrained personas for specific tasks
3. **Tool policy engine**: Governance for tool execution
4. **Model routing**: Intelligent model selection based on task
5. **Visual diff workflows**: IDE integration for change review

## Key Technical Features

### 1. Structured Output
- Heavy use of Zod schemas for validation
- Machine-readable communication patterns
- XML-like templates for specific operations

### 2. Security & Safety
- Sandboxed tool execution
- Policy-based access control
- Trust management for project-level agents

### 3. Observability
- OpenTelemetry-based telemetry
- Comprehensive logging and monitoring
- Model health tracking

### 4. Extensibility
- MCP server integration
- Hook system for custom behavior
- Plugin architecture for tools and agents

## Usage Patterns

### Basic Agent Definition
```typescript
const codebaseInvestigator: AgentDefinition = {
  name: "codebase-investigator",
  description: "Reverse-engineering expert",
  promptConfig: {
    systemPrompt: getCoreSystemPrompt(),
    // ...
  },
  inputConfig: {
    schema: z.object({
      questions: z.array(z.string()),
    }),
  },
};
```

### Tool Execution with Policy
```typescript
// Tool calls evaluated against policy rules
const result = await policyEngine.evaluate(toolCall, context);
if (result.requiresConfirmation) {
  await userConfirmationWorkflow(result);
}
```

### Model Routing
```typescript
const model = await modelRouter.route(
  conversationHistory,
  taskComplexity
);
```

## Summary
gemini-cli represents a sophisticated evolution of LLM prompt systems, moving from static templates to dynamic, context-aware assemblies with production-grade infrastructure. Its strengths in agent protocols, policy governance, and IDE integration provide valuable insights for improving Zrb's prompt system.