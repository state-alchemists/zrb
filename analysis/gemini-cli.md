# Gemini-CLI Prompt System Analysis

## Overview
Gemini-CLI is a TypeScript-based CLI agent developed by Google, designed for software engineering tasks with a focus on safety, efficiency, and adherence to project conventions.

## Architecture

### Core Prompt System (`packages/core/src/core/prompts.ts`)
The prompt system is highly configurable and modular:

1. **Environment Variable Configuration**:
   - `GEMINI_SYSTEM_MD`: Override base system prompt with custom Markdown file
   - `GEMINI_WRITE_SYSTEM_MD`: Write default system prompt to file for customization
   - `GEMINI_PROMPT_<SECTION>`: Enable/disable specific prompt sections (set to "0" or "false" to disable)

2. **Dynamic Prompt Assembly**:
   - **Conditional Sections**: Prompts are assembled based on:
     - Interactive vs non-interactive mode
     - Available tools (CodebaseInvestigator, WriteTodosTool)
     - Model version (Gemini 3 vs others)
     - Git repository status
     - Sandbox environment

3. **Prompt Structure**:
   ```typescript
   const promptConfig = {
     preamble: "...",
     coreMandates: "...",
     primaryWorkflows_prefix: "...", // Variants based on available tools
     primaryWorkflows_suffix: "...",
     operationalGuidelines: "...",
     sandbox: "...",
     git: "...",
     finalReminder: "..."
   }
   ```

### Key Components

#### 1. Core Mandates
- **Conventions First**: Rigorous adherence to existing project conventions
- **Library Verification**: Never assume libraries/frameworks are available
- **Style Mimicry**: Match existing code style, structure, and patterns
- **Idiomatic Changes**: Ensure changes integrate naturally
- **Minimal Comments**: Focus on "why" not "what"
- **Proactiveness**: Fulfill requests thoroughly including implied follow-ups
- **No Reverts**: Don't revert changes unless explicitly asked

#### 2. Primary Workflows
**Software Engineering Tasks**:
1. **Understand & Strategize**: Use search tools or delegate to CodebaseInvestigator
2. **Plan**: Build coherent plan, share concise summary
3. **Implement**: Use tools while adhering to conventions
4. **Verify (Tests)**: Use project-specific testing procedures
5. **Verify (Standards)**: Run build, linting, type-checking commands
6. **Finalize**: Consider task complete after verification

**New Applications**:
1. **Understand Requirements**: Analyze user request
2. **Propose Plan**: Present high-level summary with technology choices
3. **User Approval**: Obtain approval (interactive mode)
4. **Implementation**: Autonomously implement with placeholders
5. **Verify**: Review against requirements and plan
6. **Solicit Feedback**: Provide startup instructions

#### 3. Operational Guidelines
- **Tone**: Professional, direct, concise (CLI-appropriate)
- **Output**: <3 lines per response (excluding tool use)
- **No Chitchat**: Avoid conversational filler
- **Security**: Explain critical commands before execution
- **Tool Usage**: Parallel execution, absolute paths, background processes

#### 4. Specialized Features
- **CodebaseInvestigator Integration**: For complex refactoring/system analysis
- **WriteTodosTool**: Task breakdown and progress tracking
- **Git Integration**: Automatic git repository detection and guidance
- **Sandbox Awareness**: macOS Seatbelt and container sandbox handling

### Configuration System

#### Environment Variables
```bash
# Custom system prompt
GEMINI_SYSTEM_MD=~/custom/system.md
GEMINI_SYSTEM_MD=1  # Use .gemini/system.md

# Write default prompt to file
GEMINI_WRITE_SYSTEM_MD=~/template.md
GEMINI_WRITE_SYSTEM_MD=1  # Write to .gemini/system.md

# Disable specific sections
GEMINI_PROMPT_COREMANDATES=0
GEMINI_PROMPT_OPERATIONALGUIDELINES=false
```

#### File-Based Customization
Default path: `~/.gemini/system.md`
- Can be overridden via `GEMINI_SYSTEM_MD`
- Must exist when override is enabled
- Supports `~` expansion for home directory

### Tool Integration

#### Tool Names (Dynamic Injection)
- `EDIT_TOOL_NAME`, `GLOB_TOOL_NAME`, `GREP_TOOL_NAME`
- `MEMORY_TOOL_NAME`, `READ_FILE_TOOL_NAME`, `SHELL_TOOL_NAME`
- `WRITE_FILE_TOOL_NAME`, `WRITE_TODOS_TOOL_NAME`
- `DELEGATE_TO_AGENT_TOOL_NAME`

#### Tool-Specific Guidance
- **Shell Output Efficiency**: Critical guidelines to avoid excessive token consumption
- **Parallel Execution**: Multiple independent tool calls in parallel
- **Command Safety**: Explain modifying commands before execution

### Model-Specific Variations

#### Gemini 3 Differences
- **Tool Call Explanations**: Must provide very short natural explanation before calling tools
- **No Chitchat Rule**: Modified for Gemini 3

#### Model Detection
```typescript
const isGemini3 = desiredModel === PREVIEW_GEMINI_MODEL;
const mandatesVariant = isGemini3 ? `\n- **Do not call tools in silence:** ...` : ``;
```

### Compression System

#### History Compression Prompt (`getCompressionPrompt()`)
Specialized prompt for summarizing chat history into structured XML:
- **Overall Goal**: Single concise sentence
- **Key Knowledge**: Crucial facts and constraints
- **File System State**: Files created/read/modified/deleted
- **Recent Actions**: Last few significant agent actions
- **Current Plan**: Step-by-step plan with completion status

### Strengths

1. **Highly Configurable**: Environment variables for fine-grained control
2. **Modular Design**: Conditional inclusion of prompt sections
3. **Safety Focused**: Extensive security and safety guidelines
4. **Tool-Aware**: Dynamic tool name injection and tool-specific guidance
5. **Context-Sensitive**: Adapts based on mode, tools, and environment
6. **Professional Tone**: Optimized for CLI interaction

### Weaknesses

1. **Complex Configuration**: Many environment variables to manage
2. **TypeScript-Specific**: Tightly coupled to TypeScript/JavaScript ecosystem
3. **Limited Extensibility**: Prompt structure is hard-coded
4. **No Built-in Workflows**: Unlike Zrb, lacks domain-specific workflow system
5. **File-Based Only**: Customization requires file system access

### Comparison with Zrb

| Aspect | Gemini-CLI | Zrb |
|--------|------------|-----|
| **Language** | TypeScript | Python |
| **Configuration** | Environment variables | Python configuration hierarchy |
| **Customization** | File-based (Markdown) | Programmatic + file-based |
| **Workflows** | None | Domain-specific workflows |
| **Tool Integration** | Dynamic injection | Static configuration |
| **Context Management** | Basic (git, sandbox) | Comprehensive (notes, system info) |
| **Extensibility** | Limited | High (Python modules) |
| **Safety Features** | Extensive | Moderate |

### Key Insights for Zrb Enhancement

1. **Environment Variable Support**: Add support for prompt customization via env vars
2. **Tool-Specific Guidance**: Include tool usage best practices in prompts
3. **Compression System**: Implement history summarization for long sessions
4. **Model-Specific Variations**: Adapt prompts based on model capabilities
5. **Safety Explanations**: Require explanations for critical commands
6. **Parallel Execution Guidance**: Encourage parallel tool calls when independent
7. **Git Integration**: Automatic git repository detection and guidance
8. **Sandbox Awareness**: Handle different execution environments

### Code Examples

#### Prompt Assembly Logic
```typescript
// Conditional workflow selection
if (enableCodebaseInvestigator && enableWriteTodosTool) {
  orderedPrompts.push('primaryWorkflows_prefix_ci_todo');
} else if (enableCodebaseInvestigator) {
  orderedPrompts.push('primaryWorkflows_prefix_ci');
} else if (enableWriteTodosTool) {
  orderedPrompts.push('primaryWorkflows_todo');
} else {
  orderedPrompts.push('primaryWorkflows_prefix');
}
```

#### Environment Variable Filtering
```typescript
const enabledPrompts = orderedPrompts.filter((key) => {
  const envVar = process.env[`GEMINI_PROMPT_${key.toUpperCase()}`];
  const lowerEnvVar = envVar?.trim().toLowerCase();
  return lowerEnvVar !== '0' && lowerEnvVar !== 'false';
});
```

### Recommendations for Zrb

1. **Add Environment Variable Support**:
   - `ZRB_SYSTEM_PROMPT_OVERRIDE`: Path to custom system prompt
   - `ZRB_DISABLE_PROMPT_SECTION`: Disable specific sections

2. **Implement Compression System**:
   - History summarization for long-running sessions
   - Structured state snapshot format

3. **Enhance Safety Features**:
   - Require explanations for destructive operations
   - Sandbox environment detection
   - Git repository guidance

4. **Add Tool-Specific Guidance**:
   - Best practices for each tool
   - Parallel execution recommendations
   - Token efficiency guidelines

5. **Model Adaptation**:
   - Detect model capabilities
   - Adjust prompts accordingly
   - Handle model-specific quirks
```