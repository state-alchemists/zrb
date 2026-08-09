set -e

# Generate the API reference from docstrings into dist/api (gitignored).
#
# pdoc rather than mkdocstrings: docs/ is plain markdown with no mkdocs.yml, and
# adopting mkdocs to render one reference would be a larger commitment than the
# reference is worth. pdoc needs no config and reads the annotations that
# src/zrb/py.typed now makes visible.
#
# Output is deliberately not committed. It is regenerated from source, so a
# checked-in copy would only ever be a stale second answer to the same question.

# Expect a handful of "Error parsing type annotation ... ToolCallPart" warnings.
# Those are correct: `ResponseHandler`, `ToolPolicy` and `ArgumentFormatter`
# reference pydantic-ai types that AGENTS.md keeps behind TYPE_CHECKING because
# pydantic_ai is a heavy import. The alias is unresolvable at runtime *by
# design*; pdoc still renders the member, just without the expanded annotation.
# Hoisting the import to silence the warning would trade startup time for
# cosmetics.

OUT="${1:-dist/api}"

pdoc --output-directory "$OUT" \
     --docformat google \
     --no-search \
     zrb

echo "API reference written to $OUT/index.html"
