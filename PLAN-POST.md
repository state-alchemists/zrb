# Zrb Hook System: Claude Code Compatibility Gap Analysis & Implementation Plan

## Executive Summary

The current Zrb Hook System provides **partial compatibility** with Claude Code's official hook specification. While it supports all 14 hook events and basic execution patterns, there are significant format mismatches, missing features, and architectural differences that prevent 100% compatibility. This document outlines the gaps and provides a phased implementation plan to achieve full Claude Code compatibility.

## Current State Assessment

### ✅ **Strengths (Already Compatible)**

1. **Event Coverage**: 100% coverage of all 14 Claude Code hook events
2. **Exit Code Compatibility**: Proper handling of exit code 0 (success) and 2 (block)
3. **Thread Safety**: Thread-safe execution with timeout controls
4. **Environment Variables**: Basic injection of Claude context variables
5. **Hook Types**: Support for command, prompt, and agent hooks
6. **Configuration Discovery**: Dual directory scanning (`.zrb/` and `.claude/`)

### ⚠️ **Critical Gaps (Must Fix for 100% Compatibility)**

## 1. Configuration Format Mismatch

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

## 2. Matcher System Incompatibility

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

## 3. Hook-Specific Output Format

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

## 4. Async Hook Support

**Current Zrb**:
- `is_async: true` flag in configuration
- But execution may not properly handle async semantics

**Claude Code Async Hooks**:
- Only for command hooks (`"async": true`)
- Cannot block or control behavior
- Only `systemMessage` and `additionalContext` have effect
- Output delivered on next conversation turn
- No deduplication across multiple firings

## 5. Plugin/Skill Integration

**Current Zrb**:
- No plugin system integration
- No skill/agent frontmatter support
- No `${CLAUDE_PLUGIN_ROOT}` variable support

**Claude Code Integration**:
- Plugin hooks in `hooks/hooks.json` with `description` field
- Skill/agent hooks in frontmatter (`---` YAML blocks)
- Path variables: `$CLAUDE_PROJECT_DIR`, `${CLAUDE_PLUGIN_ROOT}`
- Environment persistence via `$CLAUDE_ENV_FILE` (SessionStart only)

## 6. Timeout Defaults

**Current Zrb**:
- Default 30-second timeout for all hooks
- Configurable per hook

**Claude Code Defaults**:
- Command hooks: 600 seconds (10 minutes)
- Prompt hooks: 30 seconds
- Agent hooks: 60 seconds
- Async hooks: Same as command hooks (600s)

## 7. Configuration Locations

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

## 8. Environment Variables

**Missing Claude Code Variables**:
- `$CLAUDE_PROJECT_DIR` (project root directory)
- `${CLAUDE_PLUGIN_ROOT}` (plugin root directory)
- `$CLAUDE_ENV_FILE` (SessionStart only, for persisting env vars)
- `$CLAUDE_CODE_REMOTE` (true in web environments)

## 9. Event-Specific Input Data

**Current Zrb**:
- Generic `event_data` field
- Some event-specific fields in `HookContext`

**Claude Code Event Data**:
- Structured JSON per event type
- Specific fields for each tool type (Write, Edit, Bash, etc.)
- MCP tool patterns: `mcp__<server>__<tool>`

## 10. Priority System

**Current Zrb**:
- Priority-based execution (higher priority first)
- Not part of Claude Code specification

**Claude Code**:
- No priority system
- Hooks execute in order defined in configuration
- Multiple hooks per matcher execute sequentially

## Implementation Plan (8 Phases)

### Phase 1: Configuration Format Migration (Week 1)
**Goal**: Support both Zrb and Claude Code configuration formats
1. Create format detector and parser for Claude Code nested format
2. Add backward compatibility layer for existing Zrb format
3. Update `HookManager._parse_and_register()` to handle both formats
4. Create migration utility to convert Zrb format to Claude Code format

### Phase 2: Matcher System Overhaul (Week 2)
**Goal**: Implement Claude Code regex-based matcher system
1. Replace field-based matchers with event-specific regex matching
2. Map event types to their matcher fields (tool name, session source, etc.)
3. Support both simple string matching and regex patterns
4. Add MCP tool pattern support (`mcp__.*__.*`)

### Phase 3: Hook-Specific Output Standardization (Week 3)
**Goal**: Implement Claude Code standardized output formats
1. Create event-specific output schema classes
2. Update `HookResult` to generate proper `hookSpecificOutput`
3. Implement universal fields: `continue`, `stopReason`, `suppressOutput`, `systemMessage`
4. Add `updatedInput` modification support for tool inputs

### Phase 4: Async Hook Implementation (Week 4)
**Goal**: Full async hook support per Claude Code spec
1. Implement true async execution for command hooks
2. Add async-specific limitations (no blocking decisions)
3. Handle output delivery on next conversation turn
4. Add timeout defaults (600s for async commands)

### Phase 5: Plugin & Skill Integration (Week 5)
**Goal**: Support hooks in plugins, skills, and agents
1. Add plugin hook discovery (`hooks/hooks.json`)
2. Implement skill/agent frontmatter hook parsing
3. Add `${CLAUDE_PLUGIN_ROOT}` variable support
4. Implement environment persistence (`$CLAUDE_ENV_FILE`)

### Phase 6: Environment & Path Variables (Week 6)
**Goal**: Complete Claude Code environment variable support
1. Add `$CLAUDE_PROJECT_DIR` detection and injection
2. Implement `$CLAUDE_ENV_FILE` for SessionStart hooks
3. Add `$CLAUDE_CODE_REMOTE` detection
4. Update path resolution with proper quoting

### Phase 7: Timeout & Defaults Alignment (Week 7)
**Goal**: Match Claude Code timeout defaults and behavior
1. Update default timeouts: 600s command, 30s prompt, 60s agent
2. Add timeout inheritance and override logic
3. Implement proper timeout error handling per event type
4. Update configuration loading to respect Claude Code defaults

### Phase 8: Testing & Validation (Week 8)
**Goal**: Ensure 100% compatibility through comprehensive testing
1. Create test suite with Claude Code hook examples
2. Test all 14 event types with matcher combinations
3. Validate output formats against Claude Code spec
4. Performance testing with multiple concurrent hooks
5. Create compatibility certification tool

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
1. **Migration Guide**: Zrb → Claude Code format conversion
2. **Claude Code Compatibility Guide**: Feature matrix and limitations
3. **API Reference**: Updated hook configuration schema
4. **Examples**: Claude Code-compatible hook examples
5. **Troubleshooting**: Common issues and solutions

### Documentation Locations
1. Update `docs/hook-system.md` with compatibility information
2. Create `docs/claude-code-compatibility.md`
3. Update `examples/hooks/` with Claude Code format examples
4. Add API documentation to docstrings

## Risk Assessment

### High Risk Areas
1. **Configuration Format Change**: Breaking existing user configurations
2. **Matcher System Overhaul**: Different matching logic may cause unexpected behavior
3. **Async Hook Implementation**: Complex threading and timing issues

### Mitigation Strategies
1. **Phased Rollout**: Gradual introduction with backward compatibility
2. **Feature Flags**: Enable/disable new features during transition
3. **Comprehensive Testing**: Extensive test coverage before release
4. **User Communication**: Clear documentation and migration guides

### Fallback Plan
1. Maintain legacy code path for Zrb format
2. Provide automatic migration tools
3. Offer support for mixed format during transition
4. Rollback capability if critical issues arise

## Success Metrics

### Technical Metrics
1. **100% Event Coverage**: All 14 Claude Code events supported
2. **Format Compatibility**: 100% Claude Code configuration format support
3. **Output Compatibility**: Correct JSON output for all event types
4. **Performance**: < 100ms overhead per hook execution
5. **Reliability**: 99.9% hook execution success rate

### User Experience Metrics
1. **Migration Success**: > 90% of users successfully migrate
2. **Compatibility**: 100% of Claude Code example hooks work
3. **Documentation**: All features documented with examples
4. **Support Tickets**: < 5% increase in hook-related support requests

## Timeline & Resources

### Phase Timeline (8 Weeks Total)
- **Week 1-2**: Core format and matcher changes
- **Week 3-4**: Output standardization and async hooks
- **Week 5-6**: Plugin integration and environment variables
- **Week 7**: Timeout defaults and configuration
- **Week 8**: Testing, documentation, and release

### Resource Requirements
1. **Development**: 2 senior developers (8 weeks each)
2. **Testing**: 1 QA engineer (4 weeks)
3. **Documentation**: 1 technical writer (2 weeks)
4. **Infrastructure**: CI/CD pipeline for compatibility testing

### Deliverables
1. **Code**: Updated hook system with 100% Claude Code compatibility
2. **Tests**: Comprehensive test suite covering all features
3. **Documentation**: Updated user guides and API references
4. **Tools**: Migration and validation utilities
5. **Examples**: Claude Code-compatible hook examples

## Conclusion

Achieving 100% Claude Code hook compatibility is a significant but achievable goal. The current Zrb Hook System provides a solid foundation with 100% event coverage and basic execution patterns. The 8-phase implementation plan addresses all critical gaps while maintaining backward compatibility during the transition.

The key success factors are:
1. **Phased approach** to minimize disruption
2. **Backward compatibility** during migration
3. **Comprehensive testing** against Claude Code spec
4. **Clear documentation** and migration tools

Once completed, Zrb will offer the most comprehensive Claude Code hook compatibility of any automation framework, enabling users to seamlessly use their existing Claude Code hooks while benefiting from Zrb's advanced automation capabilities.
