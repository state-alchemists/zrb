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

## Implementation Plan (8 Phases)

### Phase 1: Safety & Threading Foundation (Week 1)

#### 1.1 Thread Safety Implementation
```python
# New: ThreadPoolHookExecutor
class ThreadPoolHookExecutor:
    def __init__(self, max_workers=10):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.timeout = 30  # seconds
    
    async def execute_hook(self, hook: Hook, context: HookContext) -> HookResult:
        # Implement with timeout and proper error handling
        pass
    
    def shutdown(self, wait=True):
        self.executor.shutdown(wait=wait)
```

#### 1.2 Hook Result Standardization
```python
# New: Standardized HookResult class
@dataclass
class HookResult:
    success: bool
    blocked: bool = False
    message: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    exit_code: int = 0
```

#### 1.3 Safety Event Implementation
- Implement `PreToolUse` event with blocking capability
- Add `PermissionRequest` event for security-critical operations
- Implement `PostToolUseFailure` for error recovery

### Phase 2: Configuration Format Migration (Week 2)

**Goal**: Support both Zrb and Claude Code configuration formats
1. Create format detector and parser for Claude Code nested format
2. Add backward compatibility layer for existing Zrb format
3. Update `HookManager._parse_and_register()` to handle both formats
4. Create migration utility to convert Zrb format to Claude Code format

### Phase 3: Matcher System Overhaul (Week 3)

**Goal**: Implement Claude Code regex-based matcher system
1. Replace field-based matchers with event-specific regex matching
2. Map event types to their matcher fields (tool name, session source, etc.)
3. Support both simple string matching and regex patterns
4. Add MCP tool pattern support (`mcp__.*__.*`)

### Phase 4: Hook-Specific Output Standardization (Week 4)

**Goal**: Implement Claude Code standardized output formats
1. Create event-specific output schema classes
2. Update `HookResult` to generate proper `hookSpecificOutput`
3. Implement universal fields: `continue`, `stopReason`, `suppressOutput`, `systemMessage`
4. Add `updatedInput` modification support for tool inputs

### Phase 5: Async Hook Implementation (Week 5)

**Goal**: Full async hook support per Claude Code spec
1. Implement true async execution for command hooks
2. Add async-specific limitations (no blocking decisions)
3. Handle output delivery on next conversation turn
4. Add timeout defaults (600s for async commands)

### Phase 6: Plugin & Skill Integration (Week 6)

**Goal**: Support hooks in plugins, skills, and agents
1. Add plugin hook discovery (`hooks/hooks.json`)
2. Implement skill/agent frontmatter hook parsing
3. Add `${CLAUDE_PLUGIN_ROOT}` variable support
4. Implement environment persistence (`$CLAUDE_ENV_FILE`)

### Phase 7: Environment & Timeout Alignment (Week 7)

**Goal**: Complete Claude Code environment variable support and timeout defaults
1. Add `$CLAUDE_PROJECT_DIR` detection and injection
2. Implement `$CLAUDE_ENV_FILE` for SessionStart hooks
3. Add `$CLAUDE_CODE_REMOTE` detection
4. Update default timeouts: 600s command, 30s prompt, 60s agent
5. Implement proper timeout error handling per event type

### Phase 8: Testing & Validation (Week 8)

**Goal**: Ensure 100% compatibility through comprehensive testing
1. Create test suite with Claude Code hook examples
2. Test all 14 event types with matcher combinations
3. Validate output formats against Claude Code spec
4. Performance testing with multiple concurrent hooks
5. Create compatibility certification tool

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