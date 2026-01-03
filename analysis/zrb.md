# Zrb Prompt System Analysis

## Overview
Zrb's prompt system is a sophisticated framework for managing LLM interactions with context-aware workflows, personas, and system prompts. The system is designed to be highly configurable while providing sensible defaults.

## Core Components

### 1. Prompt Structure
Zrb constructs prompts using several key components:

- **Persona**: Defines the AI agent's identity and behavior (default: helpful and efficient)
- **Base System Prompt**: Core operational guidelines and principles
- **Special Instruction Prompt**: Task-specific instructions
- **Workflows**: Domain-specific guidelines (coding, git, python, etc.)
- **Context**: System information, long-term notes, contextual notes, and appendices

### 2. Default Prompt Files
Located in `/src/zrb/config/default_prompt/`:

- `persona.md`: Basic agent identity
- `system_prompt.md`: Core operational guidelines for single-request sessions
- `interactive_system_prompt.md`: Guidelines for interactive sessions
- `summarization_prompt.md`: Instructions for history summarization
- Additional specialized prompts for file extraction, repo analysis, etc.

### 3. Workflow System
Workflows are stored in `/src/zrb/task/llm/default_workflow/`:

- Each workflow is a directory with a `workflow.md` file
- Workflows can be loaded automatically based on task requirements
- Built-in workflows: coding, python, git, shell, golang, java, javascript, html-css, rust, copywriting, researching
- Workflows follow a YAML frontmatter format with description

### 4. Context Management
Zrb implements a hierarchical context system:

- **System Information**: OS, Python version, current directory, timestamp
- **Long Term Notes**: Global memory across all sessions
- **Contextual Notes**: Project-specific memory
- **Appendices**: File/directory references from user messages

### 5. Configuration Hierarchy
Prompt components can be configured at multiple levels:

1. **Task-specific**: Overrides in individual LLMTask instances
2. **Configuration files**: Via `CFG` settings (environment variables)
3. **Default prompts**: Built-in files in `default_prompt/` directory

### 6. File Reference System
Zrb automatically processes `@path` references in user messages:

- Extracts file/directory content
- Adds them as appendices to the context
- Replaces references with placeholders in the user message

### 7. Conversation History
- Maintains conversation history across sessions
- Supports history summarization to manage token limits
- Can be persisted to files

## Prompt Construction Flow

1. **Persona Selection**: Task-specific → Config → Default
2. **System Prompt Selection**: Task-specific → Config → Default
3. **Special Instructions**: Task-specific → Config → Default (empty)
4. **Workflow Loading**: Based on task requirements and user request
5. **Context Assembly**: System info + notes + appendices
6. **User Message Processing**: Extract file references, add metadata

## Key Features

### Strengths
1. **Modular Design**: Clear separation of concerns between persona, system prompts, workflows
2. **Hierarchical Configuration**: Flexible override system
3. **Context Awareness**: Built-in support for project context and notes
4. **File Integration**: Automatic handling of file references
5. **Workflow System**: Domain-specific guidance
6. **History Management**: Conversation persistence and summarization

### Areas for Improvement
1. **Default Persona**: Very basic (1 line)
2. **Special Instructions**: Default is empty string
3. **Workflow Integration**: Could be more tightly coupled with context
4. **Prompt Organization**: Multiple prompt files could be consolidated
5. **Context Resolution**: Complex hierarchy might be confusing

## Technical Implementation

### Key Files
- `prompt.py`: Core prompt construction logic
- `llm_config.py`: Configuration management
- `workflow.py`: Workflow loading and management
- `llm_task.py`: LLM task implementation
- `llm-context.md`: Documentation on context system

### Data Flow
```
User Request → Process References → Construct System Prompt → Build Context → Execute Agent
```

### Configuration Points
- `CFG.LLM_PERSONA`: Override default persona
- `CFG.LLM_SYSTEM_PROMPT`: Override system prompt
- `CFG.LLM_WORKFLOWS`: Default workflows to load
- `CFG.LLM_SPECIAL_INSTRUCTION_PROMPT`: Special instructions
- `CFG.LLM_CONTEXT_FILE`: Context file location (default: ZRB.md)

## Usage Patterns

### Basic LLM Task
```python
LLMTask(
    name="analyze",
    description="Analyze code",
    workflows=["coding", "python"],
    message="Analyze this Python code"
)
```

### Custom Prompts
```python
LLMTask(
    name="custom",
    persona="You are a security expert",
    system_prompt="Focus on security vulnerabilities",
    special_instruction_prompt="Check for SQL injection"
)
```

## Summary
Zrb's prompt system provides a robust foundation for LLM interactions with good separation of concerns and configuration flexibility. The workflow system is particularly strong for domain-specific tasks. However, the default prompts are minimal and could benefit from more comprehensive guidance.