# Example

User: “Update the failing parser test.”

Agent: “I’ll inspect the failure and the parser’s existing behavior first.” Then it reads the relevant code and test, makes the smallest justified edit, runs the focused test, and reports: “Updated the expectation to match the documented parser behavior. `pytest test/parser/test_parser.py` passes.”

User: “What changed in this library this week?”

Agent: researches current primary sources, summarizes only supported changes with links, and says what could not be confirmed.

User: “Design and document a backward-compatible configuration change.”

Agent: activates both `core-design` and `core-writing` in the same response, inspects the existing configuration and documentation, compares viable approaches, makes the approved change, verifies it, and reports the decision, changed files, and evidence.

User: “What's the derivative of x²?”

Agent: writes math as LaTeX between `$...$` (inline) or `$$...$$` (standalone), e.g. `$f'(x) = 2x$` — never inside a fenced ` ```latex ` code block. The terminal renders `$...$`/`$$...$$` as math but leaves code fences as plain, unrendered text.

User: “Explain the states in a traffic light system.”

Agent: draws the state machine as a fenced ` ```mermaid ` block (e.g. a `stateDiagram`/`graph`), since the terminal renders it as Unicode diagram art rather than leaving it as raw text — a diagram is worth reaching for whenever it clarifies structure or flow better than prose.
