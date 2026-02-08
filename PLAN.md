# Zrb Hook System: Claude Code Compatibility Gap Analysis & Implementation Plan

## Executive Summary

Zrb's current hook implementation provides **partial compatibility** with Claude Code's official hook specification. While it supports all 14 hook events and basic execution patterns, there are significant format mismatches, missing features, and architectural differences that prevent 100% compatibility.

**Safety Rating:** 40/100  
**Compatibility Rating:** 30/100

### Current State Assessment

#### ✅ **Strengths (Already Compatible)**

1. **Event Coverage**: 100% coverage of all 14 Claude Code hook events
2. **Exit Code Compatibility**: Proper handling of exit code 0 (success) and 2 (block)
3. **Thread Safety**: Thread-safe execution with timeout controls
4. **Environment Variables**: Basic injection of Claude context variables
5. **Hook Types**: Support for command, prompt, and agent hooks
6. **Configuration Discovery**: Dual directory scanning (`.zrb/` and `.claude/`)

#### ⚠️ **Critical Gaps (Must Fix for 100% Compatibility)**

## Detailed Gap Analysis

### 1. Threading Safety Issues (CRITICAL)
- **Current State:** Zrb uses `fire_and_forget` pattern in `ui.py` for hook execution
- **Risk:** Uncontrolled thread spawning, potential resource exhaustion, no error handling
- **Claude Standard:** Synchronous execution with timeout controls, proper error propagation
- **Gap:** No thread pool management, no graceful shutdown, no exception handling

### 2. Configuration Format Mismatch

**Current Zrb Format** (Flat structure):
```json
[
  {
    "name": "hook-name",
    "events": ["EventName"],
    "type": "command",
    "config": {...},
    "matchers": [...]
  }
]
```

**Claude Code Format** (Nested structure):
```json
{
  "hooks": {
    "EventName": [
      {
        "matcher": "regex-pattern",
        "hooks": [
          {
            "type": "command",
            "command": "...",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

**Key Differences**:
- Claude Code uses `hooks.{event}.{matcher}.hooks[]` nesting
- Zrb uses flat array with `events[]` and `matchers[]` arrays
- Claude Code matchers are simple regex strings, not field-based objects
- Claude Code supports multiple hooks per matcher group

### 3. Matcher System Incompatibility

**Current Zrb Matchers**:
- Field-based with dot notation (`field: "tool_name"`)
- 7 operators (`equals`, `contains`, `regex`, `glob`, etc.)
- Complex evaluation logic with case sensitivity

**Claude Code Matchers**:
- Simple regex patterns that match against event-specific fields
- Different fields per event type (tool name, session source, etc.)
- No field specification - implicit based on event type
- No operators - just regex matching

**Example Claude Code Matcher**:
```json
{
  "matcher": "Bash|Edit|Write",
  "hooks": [...]
}
```

### 4. Hook-Specific Output Format

**Current Zrb Output**:
- Uses `modifications` dictionary with mixed fields
- Some Claude Code fields supported but not standardized

**Claude Code Output**:
- Standardized `hookSpecificOutput` structure per event type
- Event-specific schemas (e.g., `permissionDecision` for PreToolUse)
- Universal fields: `continue`, `stopReason`, `suppressOutput`, `systemMessage`

**Missing Output Schemas**:
- `PreToolUse`: `hookSpecificOutput.permissionDecision` (`allow`/`deny`/`ask`)
- `PermissionRequest`: `hookSpecificOutput.decision.behavior` (`allow`/`deny`)
- `UserPromptSubmit`: Top-level `decision` field
- Proper `updatedInput` modification for tool inputs

### 5. Async Hook Support

**Current Zrb**:
- `is_async: true` flag in configuration
- But execution may not properly handle async semantics

**Claude Code Async Hooks**:
- Only for command hooks (`"async": true`)
- Cannot block or control behavior
- Only `systemMessage` and `additionalContext` have effect
- Output delivered on next conversation turn
- No deduplication across multiple firings

### 6. Plugin/Skill Integration

**Current Zrb**:
- No plugin system integration
- No skill/agent frontmatter support
- No `${CLAUDE_PLUGIN_ROOT}` variable support

**Claude Code Integration**:
- Plugin hooks in `hooks/hooks.json` with `description` field
- Skill/agent hooks in frontmatter (`---` YAML blocks)
- Path variables: `$CLAUDE_PROJECT_DIR`, `${CLAUDE_PLUGIN_ROOT}`
- Environment persistence via `$CLAUDE_ENV_FILE` (SessionStart only)

### 7. Timeout Defaults

**Current Zrb**:
- Default 30-second timeout for all hooks
- Configurable per hook

**Claude Code Defaults**:
- Command hooks: 600 seconds (10 minutes)
- Prompt hooks: 30 seconds
- Agent hooks: 60 seconds
- Async hooks: Same as command hooks (600s)

### 8. Configuration Locations

**Current Zrb Discovery**:
- `~/.zrb/hooks/`, `~/.zrb/hooks.json`
- `./.zrb/hooks/`, `./.zrb/hooks.json`
- `~/.claude/hooks/`, `~/.claude/hooks.json`
- `./.claude/hooks/`, `./.claude/hooks.json`

**Claude Code Locations**:
- `~/.claude/settings.json` (user settings)
- `./.claude/settings.json` (project settings)
- `./.claude/settings.local.json` (local project, gitignored)
- Plugin `hooks/hooks.json` (when plugin enabled)
- Skill/agent frontmatter (while component active)

### 9. Environment Variables

**Missing Claude Code Variables**:
- `$CLAUDE_PROJECT_DIR` (project root directory)
- `${CLAUDE_PLUGIN_ROOT}` (plugin root directory)
- `$CLAUDE_ENV_FILE` (SessionStart only, for persisting env vars)
- `$CLAUDE_CODE_REMOTE` (true in web environments)

### 10. Priority System

**Current Zrb**:
- Priority-based execution (higher priority first)
- Not part of Claude Code specification

**Claude Code**:
- No priority system
- Hooks execute in order defined in configuration
- Multiple hooks per matcher execute sequentially

## Implementation Plan (Completed)

### Phase 1: Safety & Threading Foundation (Completed)
- [x] Thread Safety Implementation
- [x] Hook Result Standardization
- [x] Safety Event Implementation

### Phase 2: Configuration Format Migration (Completed)
- [x] Support nested Claude Code configuration format
- [x] Implement format detection and parsing

### Phase 3: Matcher System Overhaul (Completed)
- [x] Implement regex-based matchers
- [x] Map Claude events to Zrb context fields

### Phase 4: Hook-Specific Output Standardization (Completed)
- [x] Implement `hookSpecificOutput` nesting
- [x] Merge modifications correctly

### Phase 5: Async Hook Implementation (Completed)
- [x] Implement fire-and-forget for async command hooks

### Phase 6: Plugin & Skill Integration (Completed)
- [x] Parse hooks from `SKILL.md` frontmatter
- [x] Register skill-based hooks with HookManager

### Phase 7: Environment & Timeout Alignment (Completed)
- [x] Inject `$CLAUDE_PROJECT_DIR`, `$CLAUDE_PLUGIN_ROOT`, `$CLAUDE_CODE_REMOTE`
- [x] Apply default timeouts (600s/30s/60s)

### Phase 8: Testing & Validation (Completed)
- [x] Verify configuration parsing
- [x] Verify hook registration and execution
- [x] Run full regression test suite

### Phase 9: Python First-Class Support (Completed)

**Goal**: Elevate Python to a first-class citizen for defining Skills, SubAgents, and Hooks, aligning with Zrb's mission. Markdown and JSON should be treated as extensions/adapters.

**Objective:** Enable defining Skills, SubAgents, and Hooks using pure Python (`.py` files) to allow full power of the language (logic, dynamic behavior, existing libraries).

#### 9.1 Dynamic Module Loading Utility
- [x] Create a safe, robust `ModuleLoader` to import Python modules from arbitrary paths.
- [x] Handle error isolation so one broken plugin doesn't crash the system.

#### 9.2 Python-Based Skills
- **Current:** `SKILL.md` (static text).
- **New:** Support `SKILL.py` or `*.skill.py`.
- **Contract:** File exports a `skill` object (instance of `Skill`) or a `get_skill()` function.
- **Benefit:** Dynamic prompts, context-aware skills.
- [x] Implemented in `SkillManager`
- [x] Added `add_skill` method for manual registration

#### 9.3 Python-Based SubAgents
- **Current:** `AGENT.md` (static config).
- **New:** Support `AGENT.py` or `*.agent.py`.
- **Contract:** File exports an `agent` object (`SubAgentDefinition` or `pydantic_ai.Agent`) or a factory function.
- **Benefit:** Dynamic tools, logic-based system prompts, shared state.
- [x] Implemented in `SubAgentManager`
- [x] Added `add_agent` method for manual registration

#### 9.4 Python-Based Hooks
- **Current:** `.json` / `.yaml` (static config).
- **New:** Support `*.hook.py`.
- **Contract:** File exports a `register(hook_manager)` function or a list of hooks.
- **Benefit:** Complex logic in hooks, direct API access, shared libraries.
- [x] Implemented in `HookManager`

## Technical Specifications

### Hook Context Object
```python
@dataclass
class HookContext:
    event: HookEvent
    session_id: str
    user_input: Optional[str] = None
    tool_name: Optional[str] = None
    tool_args: Optional[Dict] = None
    tool_result: Optional[Any] = None
    error: Optional[Exception] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
```

### Hook Configuration Format (Claude Code Compatible)
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "rm -rf.*",
        "hooks": [
          {
            "type": "command",
            "command": "validate_dangerous_command.sh",
            "timeout": 10,
            "async": false
          }
        ]
      }
    ]
  }
}
```

### Execution Flow
1. Event triggered → 2. Find matching hooks → 3. Validate permissions → 4. Execute hooks (sync/async) → 5. Collect results → 6. Apply decisions → 7. Propagate to UI

## Migration Strategy

### Backward Compatibility
1. **Phase 1-3**: Maintain full backward compatibility
2. **Phase 4-6**: Add new features without breaking existing functionality
3. **Phase 7-8**: Optional migration to pure Claude Code format

### Deprecation Timeline
- **Month 1-3**: Support both formats with warnings for Zrb format
- **Month 4-6**: Zrb format deprecated but still functional
- **Month 7+**: Zrb format removed, only Claude Code format supported

### Migration Tools
1. `zrb hooks migrate` - Convert Zrb format to Claude Code format
2. `zrb hooks validate` - Validate hook configuration compatibility
3. `zrb hooks test` - Test hooks against Claude Code spec

## Risk Mitigation

### Immediate Risks (Address in Phase 1)
1. **Thread Safety:** Implement thread pool with size limits
2. **Blocking Mechanism:** Add exit code 2 support for safety
3. **Error Handling:** Proper exception propagation

### Medium-term Risks (Address in Phase 2-5)
1. **Configuration Format Change:** Breaking existing user configurations
2. **Matcher System Overhaul:** Different matching logic may cause unexpected behavior
3. **Async Hook Implementation:** Complex threading and timing issues

### Long-term Risks (Address in Phase 6-8)
1. **Performance:** Optimize hook matching and execution
2. **Scalability:** Support large hook libraries
3. **Maintenance:** Ensure backward compatibility

### Mitigation Strategies
1. **Phased Rollout:** Gradual introduction with backward compatibility
2. **Feature Flags:** Enable/disable new features during transition
3. **Comprehensive Testing:** Extensive test coverage before release
4. **User Communication:** Clear documentation and migration guides

## Success Metrics

### Phase 1 Completion
- [ ] No uncontrolled thread spawning
- [ ] All hooks have timeout protection
- [ ] Critical safety events implemented
- [ ] Blocking mechanism working

### Phase 2-3 Completion
- [ ] 100% configuration format compatibility
- [ ] Matcher system overhaul complete
- [ ] Backward compatibility maintained

### Phase 4-5 Completion
- [ ] Hook-specific output standardized
- [ ] Async hook support implemented
- [ ] Output formats match Claude Code spec

### Phase 6-7 Completion
- [ ] Plugin/skill integration working
- [ ] Environment variables fully supported
- [ ] Timeout defaults aligned with Claude Code

### Phase 8 Completion
- [ ] Test coverage >90%
- [ ] Security audit passed
- [ ] Documentation complete
- [ ] 100% Claude Code compatibility verified

## Resource Requirements

### Development Team
- 2 Senior Python Developers (8 weeks each)
- 1 DevOps Engineer (2 weeks for monitoring)
- 1 QA Engineer (4 weeks for testing)
- 1 Technical Writer (2 weeks for documentation)

### Infrastructure
- CI/CD pipeline for hook testing
- Performance testing environment
- Security scanning tools

### Timeline
- **Total:** 8 weeks
- **Phase 1-4:** 4 weeks (core safety & compatibility)
- **Phase 5-8:** 4 weeks (advanced features & validation)

## Testing Strategy

### Unit Tests
1. Configuration parsing for both formats
2. Matcher evaluation for all event types
3. Output format generation
4. Async hook execution
5. Environment variable injection

### Integration Tests
1. End-to-end hook execution scenarios
2. Plugin/skill integration tests
3. Concurrent hook execution
4. Error handling and recovery

### Compatibility Tests
1. Claude Code official example hooks
2. Third-party plugin hooks
3. Community hook collections
4. Edge cases and error conditions

## Documentation Updates

### Required Documentation
1. **Migration Guide:** Zrb → Claude Code format conversion
2. **Claude Code Compatibility Guide:** Feature matrix and limitations
3. **API Reference:** Updated hook configuration schema
4. **Examples:** Claude Code-compatible hook examples
5. **Troubleshooting:** Common issues and solutions

### Documentation Locations
1. Update `docs/hook-system.md` with compatibility information
2. Create `docs/claude-code-compatibility.md`
3. Update `examples/hooks/` with Claude Code format examples
4. Add API documentation to docstrings

## Conclusion

This comprehensive plan addresses all identified gaps in Zrb's hook implementation. By following this 8-phase approach, we can achieve 100% compatibility with Claude Code's mechanism while ensuring thread safety and robust error handling. The implementation prioritizes safety-critical features first, then compatibility, followed by advanced functionality.

**Final Goal:** Zrb hook system that is both 100% Claude Code-compatible and enterprise-ready with proper safety controls, enabling users to seamlessly use their existing Claude Code hooks while benefiting from Zrb's advanced automation capabilities.

**Key Success Factors:**
1. **Phased approach** to minimize disruption
2. **Backward compatibility** during migration
3. **Comprehensive testing** against Claude Code spec
4. **Clear documentation** and migration tools