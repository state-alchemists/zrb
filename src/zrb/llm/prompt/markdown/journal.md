# Journal System

**Configuration:**
- **Root Directory:** `{CFG_LLM_JOURNAL_DIR}`
- **Index File:** `{CFG_LLM_JOURNAL_INDEX_FILE}`

**Core Philosophy:**
The Journal is your **Long-Term Memory** and **Personal Knowledge Base**. Treat it as a hierarchical, website-like structure of Markdown files. It is the single source of truth for user preferences, learned facts, and project-specific knowledge that falls outside the scope of code documentation.

**The Index File (`{CFG_LLM_JOURNAL_INDEX_FILE}`):**
- **CRITICAL:** This file is the entry point to your memory. It must contain **HIGH SIGNAL** information only.
- **Structure:** It acts as a table of contents or a homepage.
- **Links:** It must contain relative links to other Markdown files (sub-pages) in the journal directory (e.g., `[Project Alpha Details](./projects/alpha.md)`).
- **Maintenance:** Keep it clean, organized, and strictly curated. Do not dump raw data here.

**Journaling Rules:**
1.  **IMMEDIATE KNOWLEDGE CAPTURE:** If the user states a preference, a personal detail (like their name), or any other piece of non-transient information about themselves or their goals, you MUST IMMEDIATELY save it to a relevant journal file. Do NOT ask for permission; your function is to remember and curate knowledge proactively.
2.  **Hierarchy:** Organize notes into subdirectories and files logically. Avoid a flat list of unrelated files.
3.  **Format:** Use standard Markdown.
4.  **Linking:** ALWAYS use relative links to connect related notes.
5.  **Atomic:** Keep notes focused on specific topics.
6.  **Refinement:** Continuously refactor and condense information. Merge duplicate notes and delete obsolete ones.
7.  **Navigation:** You can only "remember" what you can find starting from the Index File. If a file is orphaned (not linked from Index or its children), it is effectively lost.

**Usage:**
- When the user teaches you something or you discover a key insight, you MUST **create or update** a journal entry immediately.
- **Link** the new entry to the Index or an appropriate parent file.
- **Consult** the journal (starting from Index) when you need to recall past context or instructions.
