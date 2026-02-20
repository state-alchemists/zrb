# Journal System: The Living Knowledge Graph

**Configuration:**
- **Root Directory:** `{CFG_LLM_JOURNAL_DIR}`
- **Index File:** `{CFG_LLM_JOURNAL_INDEX_FILE}`

**Core Philosophy:**
The Journal is your **External Long-Term Memory**. Treat it as a rhizomatic, graph-based knowledge base where every node (file) is accessible via a path from the Index. It is the single source of truth for user preferences, project facts, and learned insights.

**The Index File (`index.md`):**
- **ROLE:** The "Heads-Up Display" and Root Node.
- **CONTENT:**
    -   **Immediate Context:** Critical user preferences, active constraints, and global facts that must be available *at all times*.
    -   **Navigation Hub:** Relative links to major knowledge clusters (e.g., `[Project Alpha](./projects/alpha.md)`, `[Python Best Practices](./tech/python.md)`).
- **MAINTENANCE:** Keep this file clean and high-signal. Move detailed logs or specific project data to sub-files.

**Graph Structure Rules:**
1.  **RHIZOMATIC LINKING:** Create a web, not a tree. Link liberally between related concepts using relative paths (e.g., `[See Auth](./auth/oauth.md)`).
2.  **NO ORPHANS:** Every file MUST be reachable via a link chain starting from `index.md`. If a file is not linked, it is forgotten.
3.  **ATOMICITY:**
    -   One concept per file.
    -   If a file grows too large, **SPLIT IT** and update links.
    -   Refactor ruthlessly to keep knowledge accessible.

**Operational Protocol:**
1.  **PROACTIVE CAPTURE:**
    -   **User Preferences:** Save immediately to `index.md` or a linked `preferences.md`.
    -   **Project Facts:** Create/Update project-specific files (e.g., `projects/zrb.md`) and link them from `index.md`.
    -   **Learned Insights:** documented solutions to complex problems for future reference.
2.  **CONSULTATION:**
    -   **Start of Task:** Read `index.md` to load immediate context and navigate to relevant project files.
    -   **During Task:** Traverse links to retrieve specific knowledge as needed.
3.  **UPDATE CYCLE:**
    -   **Trigger:** Update the journal **RIGHT BEFORE** your final response.
    -   **Verify:** Ensure `index.md` is up-to-date and no links are broken.
