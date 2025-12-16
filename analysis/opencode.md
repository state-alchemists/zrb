# OpenCode Prompt System Analysis

## Overview
OpenCode is a modern, extensible AI coding assistant built with TypeScript/Bun, featuring a multi-agent architecture with specialized agents for different tasks.

## Architecture

### Multi-Agent System
OpenCode uses a sophisticated agent-based architecture:

1. **Primary Agents**:
   - `build`: Default general-purpose agent
   - `plan`: Planning-focused agent with restricted permissions
   - `general`: Multi-step task execution agent

2. **Specialized Subagents**:
   - `explore`: File search and codebase exploration specialist
   - `compaction`: Session history compression
   - `title`: Session titling
   - `summary`: Session summarization

### Configuration System (`packages/opencode/src/agent/agent.ts`)

#### Agent Definition Schema
```typescript
const Info = z.object({
  name: z.string(),
  description: z.string().optional(),
  mode: z.enum(["subagent", "primary", "all"]),
  native: z.boolean().optional(),
  hidden: z.boolean().optional(),
  topP: z.number().optional(),
  temperature: z.number().optional(),
  color: z.string().optional(),
  permission: z.object({
    edit: Config.Permission,
    bash: z.record(z.string(), Config.Permission),
    webfetch: Config.Permission.optional(),
    doom_loop: Config.Permission.optional(),
    external_directory: Config.Permission.optional(),
  }),
  model: z.object({
    modelID: z.string(),
    providerID: z.string(),
  }).optional(),
  prompt: z.string().optional(),  // Custom prompt override
  tools: z.record(z.string(), z.boolean()),
  options: z.record(z.string(), z.any()),
  maxSteps: z.number().int().positive().optional(),
})
```

#### Permission System
Granular permission control:
- **edit**: Allow/deny/ask for file editing
- **bash**: Command-specific permissions with wildcard support
- **webfetch**: Web access permissions
- **doom_loop**: Prevention of infinite loops
- **external_directory**: Access to directories outside project

### Prompt System (`packages/opencode/src/session/system.ts`)

#### Provider-Specific Prompts
```typescript
export function provider(model: Provider.Model) {
  if (model.api.id.includes("gpt-5")) return [PROMPT_CODEX]
  if (model.api.id.includes("gpt-") || model.api.id.includes("o1") || model.api.id.includes("o3"))
    return [PROMPT_BEAST]
  if (model.api.id.includes("gemini-")) return [PROMPT_GEMINI]
  if (model.api.id.includes("claude")) return [PROMPT_ANTHROPIC]
  if (model.api.id.includes("polaris-alpha")) return [PROMPT_POLARIS]
  return [PROMPT_ANTHROPIC_WITHOUT_TODO]
}
```

#### Available Prompt Files
- `prompt/anthropic.txt`: Claude-optimized prompt
- `prompt/gemini.txt`: Gemini-optimized prompt  
- `prompt/beast.txt`: GPT/o1/o3 optimized prompt
- `prompt/codex.txt`: GPT-5 optimized prompt
- `prompt/polaris.txt`: Polaris Alpha optimized prompt
- `prompt/qwen.txt`: Qwen/other model prompt
- `prompt/anthropic_spoof.txt`: Claude spoof header
- `prompt/compaction.txt`: Session compression prompt

### Agent-Specific Prompts

#### Explore Agent (`prompt/explore.txt`)
```
You are a file search specialist. You excel at thoroughly navigating and exploring codebases.

Your strengths:
- Rapidly finding files using glob patterns
- Searching code and text with powerful regex patterns
- Reading and analyzing file contents

Guidelines:
- Use Glob for broad file pattern matching
- Use Grep for searching file contents with regex
- Use Read when you know the specific file path you need to read
- Use Bash for file operations like copying, moving, or listing directory contents
- Adapt your search approach based on the thoroughness level specified by the caller
- Return file paths as absolute paths in your final response
- For clear communication, avoid using emojis
- Do not create any files, or run bash commands that modify the user's system state in any way

Complete the user's search request efficiently and report your findings clearly.
```

#### Gemini Prompt (`prompt/gemini.txt`)
Comprehensive 155-line prompt with:
1. **Core Mandates** (15 items)
2. **Primary Workflows** (Software Engineering + New Applications)
3. **Operational Guidelines** (Tone, Security, Tool Usage)
4. **Examples** (8 detailed examples)
5. **Final Reminder**

### Environment Context System

#### Dynamic Environment Information
```typescript
export async function environment() {
  return [
    `Here is some useful information about the environment you are running in:`,
    `<env>`,
    `  Working directory: ${Instance.directory}`,
    `  Is directory a git repo: ${project.vcs === "git" ? "yes" : "no"}`,
    `  Platform: ${process.platform}`,
    `  Today's date: ${new Date().toDateString()}`,
    `</env>`,
    `<files>`,
    `  ${project.vcs === "git" ? await Ripgrep.tree({ cwd: Instance.directory, limit: 200 }) : ""}`,
    `</files>`,
  ].join("\n")
}
```

#### Custom Instruction Files
Automatic discovery of instruction files:
- **Local**: `AGENTS.md`, `CLAUDE.md`, `CONTEXT.md`
- **Global**: `~/.config/opencode/AGENTS.md`, `~/.claude/CLAUDE.md`
- **Config Instructions**: User-defined instruction file paths

### Key Features

#### 1. Multi-Agent Delegation
- Agents can delegate to specialized subagents
- Each agent has specific capabilities and restrictions
- Clear separation of concerns

#### 2. Fine-Grained Permissions
```typescript
// Example bash command permissions
bash: {
  "cut*": "allow",
  "diff*": "allow", 
  "find *": "allow",
  "find * -delete*": "ask",
  "git diff*": "allow",
  "*": "ask"  // Default for unspecified commands
}
```

#### 3. Provider Optimization
- Different prompts for different model families
- Model-specific optimizations and workarounds
- Automatic provider detection

#### 4. Context-Aware
- Git repository detection
- File system context
- Project structure analysis
- Custom instruction integration

#### 5. Extensible Configuration
```typescript
// User configuration merges with defaults
for (const [key, value] of Object.entries(cfg.agent ?? {})) {
  if (value.disable) {
    delete result[key]
    continue
  }
  // Merge user configuration with defaults
}
```

### Strengths

1. **Multi-Agent Architecture**: Specialized agents for different tasks
2. **Fine-Grained Permissions**: Command-level security control
3. **Provider Optimization**: Model-specific prompt tuning
4. **Context Integration**: Automatic environment and file context
5. **Extensible Configuration**: User-customizable agents and prompts
6. **Professional Examples**: Detailed, practical examples in prompts
7. **Instruction File Support**: Project-specific guidance via markdown files

### Weaknesses

1. **Complex Configuration**: Many moving parts and configuration options
2. **TypeScript/Bun Dependency**: Limited to JavaScript ecosystem
3. **Steep Learning Curve**: Understanding agent delegation and permissions
4. **Resource Intensive**: Multiple agents and context gathering
5. **Limited Language Support**: Primarily TypeScript/JavaScript focused

### Comparison with Zrb and Gemini-CLI

| Aspect | OpenCode | Gemini-CLI | Zrb |
|--------|----------|------------|-----|
| **Architecture** | Multi-agent | Single agent | Workflow-based |
| **Language** | TypeScript/Bun | TypeScript | Python |
| **Permissions** | Granular (command-level) | Basic | Basic |
| **Prompt Customization** | Agent-specific + provider | File-based + env vars | Programmatic + files |
| **Context Integration** | Automatic (git, files) | Basic (git, sandbox) | Comprehensive (notes, system) |
| **Specialization** | Task-specific agents | Tool-specific guidance | Domain-specific workflows |
| **Configuration** | JSON config + files | Environment variables | Python config hierarchy |
| **Extensibility** | High (agent definitions) | Limited | High (Python modules) |

### Key Insights for Zrb Enhancement

#### 1. Multi-Agent System
- **Consideration**: Add specialized sub-agents for common tasks
- **Implementation**: Python classes for different agent types
- **Benefits**: Better task specialization, improved results

#### 2. Fine-Grained Permissions
- **Consideration**: Command-level permission system
- **Implementation**: Permission decorators or configuration
- **Benefits**: Enhanced security, user control

#### 3. Provider-Specific Optimization
- **Consideration**: Model-family specific prompts
- **Implementation**: Prompt templates per model provider
- **Benefits**: Better performance with different models

#### 4. Automatic Context Gathering
- **Consideration**: Enhanced environment context
- **Implementation**: Git detection, file tree analysis
- **Benefits**: Richer context, better understanding

#### 5. Instruction File Support
- **Consideration**: Project-specific instruction files
- **Implementation**: Automatic discovery of guidance files
- **Benefits**: Project-specific best practices

### Code Examples

#### Agent Configuration Example
```typescript
const agents = {
  explore: {
    name: "explore",
    tools: {
      todoread: false,
      todowrite: false,
      edit: false,
      write: false,
      ...defaultTools,
    },
    description: `Fast agent specialized for exploring codebases...`,
    prompt: PROMPT_EXPLORE,
    options: {},
    permission: agentPermission,
    mode: "subagent",
    native: true,
  },
  // ... other agents
}
```

#### Permission Merging Logic
```typescript
function mergeAgentPermissions(basePermission: any, overridePermission: any) {
  // Handle string-to-object conversion for bash permissions
  if (typeof basePermission.bash === "string") {
    basePermission.bash = { "*": basePermission.bash }
  }
  // Deep merge permissions
  const merged = mergeDeep(basePermission ?? {}, overridePermission ?? {})
  // ... permission processing
}
```

### Recommendations for Zrb

#### 1. Implement Agent Specialization
```python
class ExploreAgent(PromptAgent):
    """Specialized agent for codebase exploration."""
    def __init__(self):
        super().__init__(
            name="explore",
            description="Fast agent for exploring codebases",
            prompt_template="explore_prompt.txt",
            allowed_tools=["glob", "grep", "read", "bash"],
            restricted_tools=["edit", "write"]
        )
```

#### 2. Add Permission System
```python
class PermissionSystem:
    def __init__(self):
        self.permissions = {
            "edit": "allow",
            "bash": {
                "git diff*": "allow",
                "find *": "allow",
                "*": "ask"  # Default
            },
            "web_fetch": "ask"
        }
    
    def check_permission(self, tool: str, command: str = None) -> bool:
        # Check if tool is allowed
        pass
```

#### 3. Enhance Context System
```python
def gather_environment_context() -> str:
    """Gather comprehensive environment context."""
    context = []
    context.append(f"Working directory: {os.getcwd()}")
    context.append(f"Git repo: {is_git_repo()}")
    context.append(f"Platform: {platform.system()}")
    context.append(f"Date: {datetime.now().date()}")
    
    if is_git_repo():
        context.append("File tree:\n" + get_git_file_tree(limit=200))
    
    return "\n".join(context)
```

#### 4. Add Instruction File Support
```python
def discover_instruction_files() -> List[str]:
    """Discover project-specific instruction files."""
    files = []
    local_files = ["AGENTS.md", "ZRB.md", "CONTEXT.md"]
    global_files = [
        os.path.expanduser("~/.config/zrb/AGENTS.md"),
        os.path.expanduser("~/.zrb/CONTEXT.md")
    ]
    # Check local files
    for file in local_files:
        if os.path.exists(file):
            files.append(file)
    # Check global files
    for file in global_files:
        if os.path.exists(file):
            files.append(file)
    return files
```

#### 5. Provider-Specific Prompts
```python
PROVIDER_PROMPTS = {
    "openai": {
        "gpt-4": "prompts/openai/gpt4.txt",
        "gpt-3.5": "prompts/openai/gpt35.txt",
        "o1": "prompts/openai/o1.txt",
        "o3": "prompts/openai/o3.txt",
    },
    "anthropic": {
        "claude-3": "prompts/anthropic/claude3.txt",
        "claude-3.5": "prompts/anthropic/claude35.txt",
    },
    "google": {
        "gemini": "prompts/google/gemini.txt",
    }
}

def get_provider_prompt(model_name: str) -> str:
    """Get provider-specific prompt for model."""
    for provider, models in PROVIDER_PROMPTS.items():
        for pattern, prompt_file in models.items():
            if pattern in model_name.lower():
                return read_file(prompt_file)
    return read_file("prompts/default.txt")  # Fallback
```

### Conclusion
OpenCode's multi-agent architecture and fine-grained permission system offer sophisticated control and specialization. While complex, its approach to agent delegation and provider optimization provides valuable insights for enhancing Zrb's prompt system with better task specialization, security controls, and model-specific optimizations.

Key takeaways for Zrb:
1. **Specialized agents** improve task performance
2. **Fine-grained permissions** enhance security
3. **Provider-specific prompts** optimize for different models
4. **Automatic context gathering** enriches understanding
5. **Instruction file support** enables project-specific guidance