---
name: core_mandate_documentation
description: Core mandate for keeping documentation in sync with codebase changes.
user-invocable: false
---
# Skill: core_mandate_documentation
When modifying the codebase, you MUST ensure documentation is kept up-to-date.

## 1. Documentation is First-Class Code
Treat documentation files (`.md`, `.rst`, `.txt`) as integral parts of the codebase. When code changes, documentation MUST be updated to reflect those changes.

## 2. Documentation Updates & Verification
After code changes:
- Update documentation to reflect new functionality, config options, behavior
- Verify examples work, config matches implementation, API is current
- Remove references to deprecated/removed functionality

## 3. Documentation Discovery
During the Discovery phase, you MUST analyze documentation files to understand:
- Project architecture and design patterns
- Configuration options and their defaults
- Usage examples and API documentation
- Any documented constraints or requirements