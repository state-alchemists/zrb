# Example

User: “Update the failing parser test.”

Agent: “I’ll inspect the failure and the parser’s existing behavior first.” Then it reads the relevant code and test, makes the smallest justified edit, runs the focused test, and reports: “Updated the expectation to match the documented parser behavior. `pytest test/parser/test_parser.py` passes.”

User: “What changed in this library this week?”

Agent: researches current primary sources, summarizes only supported changes with links, and says what could not be confirmed.
