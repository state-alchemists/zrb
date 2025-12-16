# Zrb Prompt System Analysis

## Overview
Zrb is a Python-based LLM task automation framework with a sophisticated prompt management system. The system is designed to be modular, configurable, and extensible with workflows.

## Core Components

### 1. Prompt Configuration System (`llm_config.py`)
The LLM configuration system manages default prompts and allows customization through:
- **Default prompts**: Stored in `src/zrb/config/default_prompt/` directory
- **Configuration hierarchy**: Task-specific > Environment variables > Default prompts
- **Configurable elements**:
  - `default_persona`: AI agent persona/identity
  - `default_system_prompt`: Core system instructions
  - `default_interactive_system_prompt`: For interactive sessions
  - `default_special_instruction_prompt`: Task-specific instructions
  - `default_summarization_prompt`: For conversation history summarization
  - `default_workflows`: List of default workflows to load

### 2. Default Prompt Files
Located in `src/zrb/config/default_prompt/`:

#### `persona.md`
```markdown
You are a helpful and efficient AI agent. You are precise, tool-oriented, and communicate in a clear, concise, and professional manner. Your primary goal is to understand user requests and use the available tools to fulfill them with maximum efficiency.
```

#### `system_prompt.md`
- Designed for single-request sessions
- Emphasizes tool-centric approach without action descriptions
- Core principles: Efficiency, sequential execution, convention adherence
- Security rules for critical commands
- Execution plan with risk assessment

#### `interactive_system_prompt.md`
- For interactive sessions
- Allows describing actions before tool calls
- Includes clarification and planning guidelines
- Similar security rules

#### `summarization_prompt.md`
- Instructions for conversation history summarization
- Specifies format for summary and transcript
- Guidelines for preserving critical context

### 3. Prompt Construction System (`prompt.py`)
The `get_system_and_user_prompt()` function constructs prompts by combining:
1. **Persona**: Task-specific or default persona
2. **Base System Prompt**: Task-specific or default system prompt
3. **Special Instructions**: Task-specific special instructions
4. **Workflows**: Active and available workflows
5. **Context**: System information, long-term notes, contextual notes, appendices

### 4. Workflow System
- Workflows are stored in `src/zrb/task/llm/default_workflow/`
- Each workflow has a `workflow.md` file with specific guidelines
- Workflows can be loaded dynamically based on task requirements
- Built-in workflows include: coding, python, git, shell, golang, java, javascript, html-css, rust, copywriting, researching

### 5. LLM Task Implementation (`llm_task.py`)
The `LLMTask` class:
- Manages conversation history
- Handles prompt construction and agent execution
- Supports summarization for long conversations
- Configurable model settings and tools

## Prompt Structure

The constructed system prompt follows this structure:

```
[Persona]

[Base System Prompt]

📝 SPECIAL INSTRUCTION
[Special Instruction Prompt]
[Active Workflows]

🛠️ AVAILABLE WORKFLOWS
[Inactive Workflows]

📚 CONTEXT
ℹ️ System Information
- OS: ...
- Python Version: ...
- Current Directory: ...
- Current Time: ...

🧠 Long Term Note
[Long term memory]

📝 Contextual Note
[Project-specific memory]

📄 Apendixes
[Referenced file/directory contents]
```

## Key Features

### 1. Modular Prompt Components
- Persona, system prompt, and special instructions are separate components
- Can be overridden at task level or via environment variables

### 2. Workflow-Based Specialization
- Domain-specific workflows provide targeted guidance
- Automatic workflow loading based on task requirements
- Workflow precedence: user-specified > built-in

### 3. Context Management
- **Long-term notes**: Cross-session memory
- **Contextual notes**: Project-specific memory
- **System information**: OS, Python version, directory, time
- **Appendices**: Referenced file/directory contents

### 4. File Reference System
- Supports `@path/to/file` syntax in user messages
- Automatically includes file/directory contents as appendices
- Preserves original references with placeholders

### 5. Conversation History
- Maintains conversation history across sessions
- Supports summarization to manage token limits
- Configurable summarization thresholds

## Configuration Hierarchy

1. **Task-specific settings**: Directly passed to `LLMTask` constructor
2. **Environment variables**: Via `CFG` class (e.g., `LLM_SYSTEM_PROMPT`)
3. **Default prompts**: From `default_prompt/` directory
4. **Hardcoded defaults**: Fallback values in code

## Strengths

1. **Modularity**: Clear separation of concerns between persona, system prompt, and special instructions
2. **Extensibility**: Easy to add new workflows or modify existing ones
3. **Context awareness**: Comprehensive context inclusion (system info, notes, references)
4. **Customization**: Multiple levels of configuration (task, env, defaults)
5. **Memory management**: Built-in conversation history with summarization

## Areas for Improvement

1. **Default prompt complexity**: System prompt is quite detailed (38 lines)
2. **Workflow management**: Could benefit from more granular workflow control
3. **Prompt optimization**: May benefit from more concise default prompts
4. **Template variables**: Limited support for dynamic prompt variables
5. **Testing**: No apparent system for testing prompt effectiveness

## Usage Patterns

### Basic LLM Task Creation
```python
task = LLMTask(
    name="analyze_code",
    description="Analyze codebase",
    message="Analyze the codebase at @/path/to/project",
    workflows=["coding", "python"],
)
```

### Custom Prompts
```python
task = LLMTask(
    name="custom_task",
    persona="You are a security expert...",
    system_prompt="Focus on security vulnerabilities...",
    special_instruction_prompt="Check for SQL injection and XSS...",
)
```

## Conclusion
Zrb's prompt system is well-architected with clear separation of concerns, good extensibility through workflows, and comprehensive context management. The system balances flexibility with sensible defaults, making it suitable for various LLM automation tasks.