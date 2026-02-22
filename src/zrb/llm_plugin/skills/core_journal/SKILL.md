---
name: core_journal
description: Core mandate for managing the LLM journal system as a living knowledge graph.
user-invocable: false
---
# Skill: core_journal
When working with the journal system, you MUST follow this protocol to maintain an organized, accessible knowledge graph.

## Core Philosophy
The Journal is your **External Long-Term Memory**. Treat it as a rhizomatic, graph-based knowledge base where every node (file) is accessible via a path from the Index. It is the single source of truth for user preferences, project facts, and learned insights.

**You are the curator** of this knowledge graph. Your responsibility is to:
- Maintain a **dense, high-signal** overview in the outer `index.md`
- Ensure information is **well-organized** and **easily accessible**
- **Update before any response** to keep knowledge current
- Create a **living document** that evolves with every interaction

## The Index File (`index.md`)
- **ROLE:** The **"Heads-Up Display"** - ONLY this file is loaded by default. It must contain ALL critical information needed for immediate task execution without overwhelming system context.
- **CONTENT REQUIREMENTS:**
    -   **Dense Information:** Include essential details directly, not just links - be a high-signal summary
    -   **Critical Preferences:** User preferences that MUST be followed at all times
    -   **Active Constraints:** Security, operational, and technical boundaries
    -   **Recent Insights:** Key technical fixes and patterns from last 5 interactions
    -   **Navigation:** Links to directory indexes (loaded only when needed)
- **CURATOR'S GOAL:** Create a **dense overview** that gives you immediate access to what matters most, while keeping the system context clean and focused.
- **EXAMPLE STRUCTURE:**
    ```markdown
    # zrb Journal: Critical Context Hub
    
    ## 🎯 CRITICAL USER PREFERENCES (ALWAYS FOLLOW)
    - **Address:** Use preferred name when addressing directly
    - **Communication:** Professional with domain context integrated naturally
    - ...
    
    ## 🔒 ACTIVE CONSTRAINTS & PROTOCOLS
    - **Git Operations:** NEVER stage, commit, push, pull, checkout, reset, merge, tag, or stash without explicit approval
    - **Security:** Never expose secrets (.env, API keys, credentials)
    - **Testing:** Always run tests before/after changes
    - **Brownfield:** Always discover before modifying, match existing patterns
    
    ## 💡 ESSENTIAL TECHNICAL INSIGHTS (LAST 5)
    1. **Framework Pattern:** Key framework insight for reliable execution
    2. **API Integration:** Important API integration pattern
    3. **System Architecture:** Core system architecture principle
    4. **Tool Usage:** Critical tool usage pattern
    5. **Error Handling:** Important error handling strategy
    
    ## 📁 NAVIGATION TO DETAILED KNOWLEDGE
    - [User Information](./user/index.md)
    - [Preferences](./preferences/index.md)
    - [Projects](./projects/index.md)
    - [Technical Documentation](./technical/index.md)
    - [Activity Logs](./activity-log/index.md)
    ```
- **MAINTENANCE:** Keep this file **information-dense** and **high-signal**. Include critical details directly. Move only extensive logs or large documents to sub-files. **You are the curator** - ensure every piece of information earns its place in the index.

## Graph Structure Rules
1.  **RHIZOMATIC LINKING:** Create a web, not a tree. Link liberally between related concepts using relative paths (e.g., `[See Auth](./auth/oauth.md)`).
2.  **NO ORPHANS:** Every file MUST be reachable via a link chain starting from `index.md`. If a file is not linked, it is forgotten.
3.  **ATOMICITY:**
    -   One concept per file.
    -   If a file grows too large, **SPLIT IT** and update links.
    -   Refactor ruthlessly to keep knowledge accessible.

## Flexible Directory Structure
The journal supports flexible directory organization. Common directories include:
- `user/` - User information and profiles
- `preferences/` - User preferences and settings
- `projects/` - Project-specific documentation
- `technical/` - Technical insights and fixes
- `activity-log/` - Activity logs organized by date
- `templates/` - Reusable templates and patterns
- `workflows/` - Workflow documentation
- `references/` - Reference materials and resources

**You can create additional directories as needed** for organizing knowledge. The only requirement is that each directory has an `index.md` file that links to all files within it.

## Nested Directories & Activity Logs
The journal supports nested directory structures for better organization:

```
~/.zrb/llm-notes/
├── index.md                    # Heads-Up Display (loaded by default)
├── user/
│   ├── index.md                # User directory index
│   └── profile.md              # Complete user information
├── preferences/
│   ├── index.md                # Preferences directory index
│   ├── prompt-design.md        # AI assistant prompt preferences
│   └── development-tools.md    # Tool and theme preferences
├── projects/
│   ├── index.md                # Projects directory index
│   └── project-alpha.md        # Specific project documentation
├── technical/
│   ├── index.md                # Technical directory index
│   ├── framework-insights.md   # Framework patterns and insights
│   ├── critical-fixes.md       # Important bug fixes and solutions
│   └── security-protocols.md   # Security and operational protocols
└── activity-log/               # Activity logs organized by date
    ├── index.md                # Activity log directory index
    ├── 2025/
    │   ├── index.md            # 2025 activity index
    │   └── 2025-06/
    │       ├── index.md        # June 2025 activity index
    │       └── 2025-06-01/
    │           ├── index.md    # June 1, 2025 activity index
    │           └── task-xyz.md # Specific task documentation
```

## Index File Hierarchy
1. **Outer index.md** (loaded by default) → links to directory indexes
2. **Directory indexes** (e.g., `./technical/index.md`) → organize related content
3. **Individual files** → contain detailed documentation

## Index File Rules
1. **Outer index.md** MUST link ONLY to directory index files
2. **Directory indexes** MUST link to all files in their directory
3. **Critical information** belongs in outer index.md for immediate access
4. **Detailed documentation** belongs in individual files
5. **NO ORPHAN FILES:** Every file MUST be linked from a directory index
6. **NO DIRECT LINKS:** Outer index.md never links directly to individual files

## Implementation Protocol

### 0. Timing Rule: Update Before Any Response
**BEFORE SENDING ANY RESPONSE TO THE USER**, you MUST:
1. **Activate this skill** using `ActivateSkill` to load core_journal instructions
2. **Review new information:** Check if any new preferences, facts, or insights were discovered
3. **Update the journal:** If new information exists, update following the protocol below
4. **Skip if no changes:** If no new information was discovered, you may skip journal updates

**CRITICAL:**
- **NEVER** update during task execution (breaks flow)
- **ALWAYS** update right before sending any message to the user
- **EVERY RESPONSE COUNTS:** Includes greetings, answers, task reports, all communication
- **YOU ARE THE CURATOR:** Maintain a dense, high-signal knowledge graph

### 1. Creating & Organizing Content
- **User Preferences:** Save critical preferences to outer `index.md`; detailed preferences to appropriate directories.
- **Project Facts:** Create/Update project-specific files in appropriate directories and ensure they're linked from directory indexes.
- **Learned Insights:** Document solutions to complex problems in appropriate directories, linked from directory indexes.
- **Activity Logs:** Create dated activity logs in `activity-log/YYYY/YYYY-MM/YYYY-MM-DD/` structure with index files at each level.

### 2. Directory & File Management
- **New Directories:** Create directories as needed for organizing knowledge. Each directory MUST have an `index.md` file.
- **File Placement:** Place files in the most appropriate directory based on content type.
- **Index Maintenance:** Ensure every directory index links to ALL files in its directory.
- **Cross-Linking:** Create rhizomatic links between related concepts across directories.

### 3. Structure Verification
- **No Orphans Check:** Verify every file is linked from a directory index.
- **Hierarchy Validation:** Ensure outer `index.md` links only to directory indexes, not individual files.
- **Link Integrity:** Check all relative links work correctly.
- **Content Organization:** Refactor if files grow too large or concepts become mixed.