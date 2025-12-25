# Actionable Items: Updating Zrb's Default Prompt Components

Based on comparative analysis with gemini-cli and opencode, here are actionable items to improve Zrb's prompt system.

## Priority Levels
- **P0**: Critical improvements, foundational changes
- **P1**: Important enhancements, significant value add
- **P2**: Nice-to-have features, incremental improvements

## P0: Foundational Improvements

### 1. Enhance Default Persona System
**Current**: Basic 1-line persona definition
**Target**: Specialized, protocol-driven personas like gemini-cli
**Actions**:
1. Create specialized persona files in `default_prompt/`:
   - `persona_code_reviewer.md`
   - `persona_documentation.md`
   - `persona_debugger.md`
   - `persona_architect.md`
2. Add protocol enforcement (e.g., must use scratchpad, must call completion tool)
3. Implement persona selection based on task type

### 2. Implement Dynamic Context Injection
**Current**: Static context assembly
**Target**: Runtime context injection like gemini-cli's `getCoreSystemPrompt()`
**Actions**:
1. Modify `prompt.py` to inject runtime state:
   - Current working directory context
   - Git status and branch information
   - Active virtual environment
   - Available tools and their status
2. Create context variables for common runtime information
3. Add template variables to prompt files (e.g., `{{git_branch}}`, `{{python_version}}`)

### 3. Add Project-Level Customization
**Current**: Global workflows only
**Target**: Project-specific workflows like opencode's `.opencode/agent/`
**Actions**:
1. Add support for `.zrb/workflows/` directory in projects
2. Implement workflow discovery hierarchy:
   - Project workflows (highest priority)
   - User workflows (`~/.zrb/workflows/`)
   - System workflows (lowest priority)
3. Create workflow inheritance/override system

## P1: Enhanced Features

### 4. Improve Workflow Definition Format
**Current**: Plain Markdown files
**Target**: YAML+Markdown format like opencode
**Actions**:
1. Adopt YAML frontmatter for workflow metadata:
   ```yaml
   ---
   name: coding
   description: Software engineering workflow
   priority: 10
   tools:
     - read_file
     - write_file
     - run_shell_command
   model: gpt-4-turbo
   ---
   ```
2. Maintain backward compatibility with existing `.md` files
3. Add validation for YAML frontmatter

### 5. Add Tool Governance System
**Current**: No tool execution policies
**Target**: Policy engine like gemini-cli
**Actions**:
1. Create `tool_policy.py` with rule evaluation
2. Implement policy rules in TOML/YAML format
3. Add user confirmation workflows for dangerous operations
4. Create sandbox mode for file operations

### 6. Implement Model Routing
**Current**: Single model configuration
**Target**: Intelligent model routing like gemini-cli
**Actions**:
1. Create `model_router.py` with routing strategies
2. Implement task complexity analysis
3. Add model fallback mechanisms
4. Create cost optimization strategies

### 7. Enhance IDE Integration
**Current**: Limited editor support
**Target**: Visual diff workflows like gemini-cli
**Actions**:
1. Add support for editor-specific diff formats
2. Implement change review workflows
3. Create IDE extension points
4. Add file watcher integration

## P2: Incremental Improvements

### 8. Improve Context Management
**Current**: Basic hierarchical context
**Target**: Multi-source context like gemini-cli
**Actions**:
1. Add context source discovery
2. Implement context import/export system
3. Add context compression for long conversations
4. Create context templates for common scenarios

### 9. Add Specialized Agent Protocols
**Current**: General assistant behavior
**Target**: Protocol-driven agents like gemini-cli's Codebase Investigator
**Actions**:
1. Create protocol definitions for common tasks
2. Implement protocol enforcement middleware
3. Add agent delegation system
4. Create agent result validation

### 10. Enhance Configuration System
**Current**: Environment variables + task overrides
**Target**: Layered configuration like modern apps
**Actions**:
1. Implement configuration hierarchy:
   - Command-line arguments
   - Environment variables
   - Project configuration (`.zrb/config.yaml`)
   - User configuration (`~/.zrb/config.yaml`)
   - System defaults
2. Add configuration validation
3. Create configuration templates

### 11. Add Telemetry and Observability
**Current**: Limited logging
**Target**: Comprehensive telemetry like gemini-cli
**Actions**:
1. Implement OpenTelemetry integration
2. Add performance metrics collection
3. Create usage analytics
4. Add error tracking and reporting

### 12. Improve File Reference System
**Current**: Basic `@path` processing
**Target**: Advanced file context management
**Actions**:
1. Add file content summarization
2. Implement file change detection
3. Create file dependency analysis
4. Add file permission checking

## Implementation Roadmap

### Phase 1 (Next 2 weeks): Foundation
1. Implement dynamic context injection (P0)
2. Enhance default persona system (P0)
3. Add project-level customization (P0)

### Phase 2 (Next month): Core Features
1. Improve workflow definition format (P1)
2. Add tool governance system (P1)
3. Implement model routing (P1)

### Phase 3 (Next 2 months): Advanced Features
1. Enhance IDE integration (P1)
2. Add specialized agent protocols (P2)
3. Improve context management (P2)

### Phase 4 (Ongoing): Polish and Optimization
1. Enhance configuration system (P2)
2. Add telemetry (P2)
3. Improve file reference system (P2)

## Specific File Changes

### 1. `src/zrb/task/llm/prompt.py`
- Add `inject_runtime_context()` function
- Modify `_construct_system_prompt()` to use dynamic context
- Add template variable substitution

### 2. `src/zrb/config/default_prompt/`
- Create specialized persona files
- Add YAML frontmatter to existing workflow files
- Create template variable examples

### 3. `src/zrb/task/llm/workflow.py`
- Add workflow discovery hierarchy
- Implement YAML frontmatter parsing
- Add project workflow directory support

### 4. New Files to Create
- `src/zrb/task/llm/tool_policy.py`
- `src/zrb/task/llm/model_router.py`
- `src/zrb/task/llm/context_injector.py`
- `src/zrb/config/workflow_config.py`

## Testing Strategy

### Unit Tests
1. Test dynamic context injection
2. Test workflow discovery hierarchy
3. Test YAML frontmatter parsing
4. Test tool policy evaluation

### Integration Tests
1. Test end-to-end prompt construction
2. Test project workflow override
3. Test model routing decisions
4. Test tool governance workflows

### User Acceptance Tests
1. Test backward compatibility
2. Test performance impact
3. Test user experience improvements
4. Test configuration migration

## Success Metrics

1. **Reduced prompt engineering time**: Users spend less time crafting prompts
2. **Improved task success rate**: Higher completion rates for complex tasks
3. **Better model utilization**: Appropriate models for appropriate tasks
4. **Increased user satisfaction**: Better developer experience
5. **Reduced errors**: Fewer tool execution mistakes

## Risks and Mitigations

### Risk 1: Breaking Changes
**Mitigation**: Maintain backward compatibility, provide migration tools

### Risk 2: Performance Impact
**Mitigation**: Profile changes, add caching, optimize hot paths

### Risk 3: Complexity Increase
**Mitigation**: Keep simple defaults, progressive disclosure of features

### Risk 4: Configuration Bloat
**Mitigation**: Sensible defaults, configuration validation, examples

## Conclusion
These actionable items will transform Zrb from a simple prompt assembly system into a sophisticated, production-ready AI development platform. The improvements draw inspiration from both gemini-cli's dynamic, protocol-driven approach and opencode's human-readable, project-customizable system, while maintaining Zrb's core strengths of simplicity and modularity.