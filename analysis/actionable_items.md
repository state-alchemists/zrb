# Actionable Items for Zrb Prompt System Enhancement

Based on comparative analysis of Zrb, Gemini-CLI, and OpenCode prompt systems, here are actionable items to improve Zrb's default prompt components.

## 1. Environment Variable Configuration System

### Current State
Zrb uses Python configuration hierarchy (task-specific > environment variables > defaults) but lacks fine-grained control over prompt sections.

### Actionable Items

**1.1 Add Environment Variable Support for Prompt Customization**
```python
# Proposed environment variables:
ZRB_SYSTEM_PROMPT_OVERRIDE=/path/to/custom/system.md
ZRB_PERSONA_OVERRIDE=/path/to/custom/persona.md
ZRB_SPECIAL_INSTRUCTION_OVERRIDE=/path/to/custom/instruction.md

# Section disabling (like Gemini-CLI)
ZRB_DISABLE_PROMPT_SECTION_COREMANDATES=0
ZRB_DISABLE_PROMPT_SECTION_WORKFLOWS=false
ZRB_DISABLE_PROMPT_SECTION_CONTEXT=0
```

**1.2 Implement File-Based Customization**
- Support `~/.zrb/system.md`, `~/.zrb/persona.md` for user-level overrides
- Auto-discovery of project-specific prompt files (`.zrb/system.md` in project root)
- Merge logic: User file > Project file > Default

**1.3 Add Prompt Section Toggle System**
- Allow users to enable/disable specific prompt sections via env vars
- Implement conditional prompt assembly based on enabled sections
- Maintain backward compatibility (all sections enabled by default)

## 2. Enhanced Safety and Security Features

### Current State
Zrb has basic security rules but lacks granular control and command explanations.

### Actionable Items

**2.1 Implement Command Explanation Requirement**
- Require explanations for destructive operations (file deletion, system modifications)
- Add safety guidelines for critical commands in default prompts
- Implement pre-execution confirmation for high-risk actions

**2.2 Add Permission System (Inspired by OpenCode)**
```python
class PermissionSystem:
    """Granular permission control for tools and commands."""
    
    def __init__(self):
        self.permissions = {
            "edit": "allow",  # allow, deny, ask
            "bash": {
                "git diff*": "allow",
                "find *": "allow",
                "rm *": "ask",
                "*": "ask"  # default
            },
            "web_fetch": "ask",
            "external_directory": "deny"
        }
```

**2.3 Add Sandbox Environment Detection**
- Detect containerized/sandboxed environments
- Adjust safety guidelines based on execution context
- Add warnings for system-critical operations in sandbox mode

## 3. Tool Integration and Optimization

### Current State
Zrb has static tool configuration but lacks tool-specific guidance.

### Actionable Items

**3.1 Add Tool-Specific Best Practices**
- Include tool usage guidelines in default prompts
- Add examples for each tool in context
- Implement tool efficiency guidelines (token usage, parallel execution)

**3.2 Implement Parallel Execution Guidance**
- Encourage parallel tool calls for independent operations
- Add examples of parallel vs sequential execution
- Include guidelines for when to use parallel execution

**3.3 Add Dynamic Tool Name Injection**
- Inject actual tool names into prompts (like Gemini-CLI)
- Support tool aliases and custom tool names
- Make tool references consistent and clear

## 4. Context Management Enhancements

### Current State
Zrb has comprehensive context (notes, system info) but could benefit from richer environment context.

### Actionable Items

**4.1 Enhance Environment Context Gathering**
```python
def gather_enhanced_context() -> str:
    """Gather comprehensive environment context."""
    context = []
    context.append(f"Working directory: {os.getcwd()}")
    context.append(f"Git repository: {detect_git_repo()}")
    context.append(f"Platform: {platform.system()} {platform.release()}")
    context.append(f"Python: {sys.version}")
    context.append(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if detect_git_repo():
        context.append("\nRecent git status:" + get_git_status())
        context.append("\nFile tree (top 200):\n" + get_git_file_tree(limit=200))
    
    return "\n".join(context)
```

**4.2 Add Automatic Instruction File Discovery**
- Discover project-specific guidance files (`ZRB.md`, `CONTEXT.md`, `AGENTS.md`)
- Support user-level instruction files (`~/.zrb/guidelines.md`)
- Automatically include discovered files as appendices

**4.3 Implement Git Integration**
- Automatic git repository detection
- Include git status and recent changes in context
- Add git-specific guidelines in prompts

## 5. Prompt Optimization and Specialization

### Current State
Zrb has domain-specific workflows but could benefit from model-specific optimizations.

### Actionable Items

**5.1 Implement Provider-Specific Prompt Templates**
```python
PROVIDER_PROMPTS = {
    "openai": {
        "gpt-4": "prompts/providers/openai/gpt4.md",
        "gpt-3.5": "prompts/providers/openai/gpt35.md",
        "o1": "prompts/providers/openai/o1.md",
        "o3": "prompts/providers/openai/o3.md",
    },
    "anthropic": {
        "claude-3": "prompts/providers/anthropic/claude3.md",
        "claude-3.5": "prompts/providers/anthropic/claude35.md",
    },
    "google": {
        "gemini": "prompts/providers/google/gemini.md",
        "gemini-2.0": "prompts/providers/google/gemini2.md",
    }
}
```

**5.2 Add Model-Specific Variations**
- Different guidelines for different model families
- Model capability detection and prompt adjustment
- Workarounds for model-specific quirks

**5.3 Implement Prompt Compression System**
- Conversation history summarization for long sessions
- Structured state snapshot format
- Configurable compression thresholds

## 6. Multi-Agent Architecture (Optional Enhancement)

### Current State
Zrb uses workflow-based specialization but could benefit from agent-based architecture.

### Actionable Items

**6.1 Implement Specialized Sub-Agents**
```python
class ExploreAgent(PromptAgent):
    """Specialized agent for codebase exploration."""
    
    def __init__(self):
        super().__init__(
            name="explore",
            description="Fast agent for exploring codebases",
            prompt_template="agents/explore.md",
            allowed_tools=["glob", "grep", "read", "bash"],
            restricted_tools=["edit", "write"]
        )

class PlanAgent(PromptAgent):
    """Planning-focused agent with restricted permissions."""
    
    def __init__(self):
        super().__init__(
            name="plan",
            description="Agent for creating plans and designs",
            prompt_template="agents/plan.md",
            allowed_tools=["read", "analyze"],
            restricted_tools=["edit", "write", "bash"]
        )
```

**6.2 Add Agent Delegation System**
- Allow agents to delegate to specialized sub-agents
- Implement agent discovery and registration
- Add agent selection based on task requirements

## 7. Default Prompt Improvements

### Current State
Zrb's default prompts are comprehensive but could be more concise and focused.

### Actionable Items

**7.1 Optimize Default System Prompt**
- Reduce verbosity while maintaining clarity
- Focus on most critical guidelines
- Add more practical examples
- Improve readability and scannability

**7.2 Enhance Workflow Prompts**
- Add more domain-specific examples to each workflow
- Include common patterns and anti-patterns
- Add troubleshooting guidelines
- Improve cross-workflow consistency

**7.3 Add Prompt Testing System**
- Implement prompt effectiveness testing
- Add A/B testing framework for prompt variations
- Collect metrics on prompt performance
- Create prompt validation rules

## 8. Implementation Priority

### High Priority (Core Improvements)
1. Environment variable configuration system
2. Enhanced safety features and command explanations
3. Tool-specific guidance and optimization
4. Enhanced context gathering with git integration

### Medium Priority (Advanced Features)
5. Provider-specific prompt templates
6. Prompt compression and history management
7. Instruction file discovery system
8. Default prompt optimization

### Low Priority (Optional Enhancements)
9. Multi-agent architecture
10. Fine-grained permission system
11. Prompt testing and validation
12. Advanced agent delegation

## 9. Migration Strategy

### Phase 1: Backward-Compatible Enhancements
1. Add environment variable support (optional, doesn't break existing usage)
2. Enhance default prompts (improvements, not breaking changes)
3. Add tool guidance (additional context, not required)

### Phase 2: Optional Advanced Features
4. Implement permission system (opt-in via configuration)
5. Add agent specialization (new feature, doesn't affect existing workflows)
6. Provider-specific prompts (automatic detection, fallback to defaults)

### Phase 3: Breaking Changes (If Needed)
7. Major prompt restructuring (version bump, migration guide)
8. API changes for advanced features (clearly documented)

## 10. Expected Benefits

1. **Improved User Experience**: More customization options, better safety
2. **Enhanced Performance**: Optimized prompts for different models and tasks
3. **Better Security**: Granular permissions, command explanations
4. **Richer Context**: Automatic environment and project context
5. **Increased Flexibility**: Multiple configuration methods, specialized agents
6. **Professional Results**: More consistent, high-quality outputs

## 11. Next Steps

1. **Review and prioritize** items based on Zrb's roadmap
2. **Create detailed specifications** for high-priority items
3. **Implement incrementally** with thorough testing
4. **Gather user feedback** on new features
5. **Iterate and improve** based on real-world usage

---

*This document synthesizes insights from analysis of Zrb, Gemini-CLI, and OpenCode prompt systems. Each actionable item includes specific implementation suggestions while maintaining Zrb's Pythonic, workflow-based architecture.*