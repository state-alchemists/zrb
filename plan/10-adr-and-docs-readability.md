🔖 [Plan](README.md)

# Phase 10 — Make the ADRs readable again

Risk: **none** (prose only, no code). Estimate: 2 days. Ship any time.

## §0 — The scope is narrower than "make the docs readable"

I measured before planning, and two of the three things you might expect to be
broken are not:

```bash
cd /home/gofrendi/zrb
# 1. Are the user docs dense?
python3 -c "
import pathlib, statistics
for f in ['docs/advanced-topics/llm-custom-ui.md','docs/configuration/llm-config.md',
          'docs/advanced-topics/hooks.md','docs/advanced-topics/maintainer-guide.md']:
    t = pathlib.Path(f).read_text()
    paras = [len(b.strip()) for b in t.split('\n\n')
             if b.strip() and not b.strip().startswith(('#','|','-','*','\`','>','🔖','1.','2.'))]
    print(f'{f.split(chr(47))[-1]:<24} paras={len(paras):>4} avg={round(statistics.mean(paras)):>4} max={max(paras):>5} code_blocks={t.count(chr(96)*3)//2}')
"
# 2. Do the long pages have a table of contents?
for f in $(find docs -name '*.md' -not -path '*changelog*' -not -path '*adr*'); do
  l=$(wc -l < "$f"); [ "$l" -gt 150 ] && [ "$(grep -ci 'table of contents' "$f")" = "0" ] && echo "NO TOC: $l lines  $f"
done
```

**The user-facing docs are in good shape.** Average paragraph 154–228 characters,
21–32 code blocks per page, and 26 of the 29 pages over 150 lines already carry a
table of contents. There is no rewrite to do there — three missing TOCs, and
that is it (§B).

**The ADR log is where the problem is**, and it is measurable:

```bash
python3 -c "
import pathlib, statistics
def dens(lo, hi):
    lines, paras = [], []
    for p in pathlib.Path('docs/adr').glob('adr-*.md'):
        n = int(p.stem.split('-')[1])
        if not lo <= n <= hi: continue
        lines.append(len(p.read_text().splitlines()))
        for blk in p.read_text().split('\n\n'):
            b = blk.strip()
            if b and not b.startswith(('#','|','\`','>','🔖','**Status')): paras.append(len(b))
    return len(lines), round(statistics.mean(lines)), round(statistics.mean(paras)), max(paras)
print(f'{\"range\":<12}{\"ADRs\":>6}{\"avg lines\":>11}{\"avg para\":>10}{\"max para\":>10}')
for lo, hi in [(1,30),(31,60),(61,91)]:
    print(('ADR %d-%d' % (lo,hi)).ljust(12) + ''.join(str(x).rjust(w) for x,w in zip(dens(lo,hi),(6,11,10,10))))
"
```

| Range | ADRs | Avg lines | **Avg paragraph** | **Max paragraph** |
| --- | --- | --- | --- | --- |
| ADR-0001–0030 | 30 | 18 | **226 chars** | 1,624 |
| ADR-0031–0060 | 29 | 23 | **480 chars** | 3,365 |
| ADR-0061–0091 | 31 | 29 | **615 chars** | 4,357 |

Average paragraph length **tripled**. The worst single paragraph is 4,357
characters (ADR-0079) — roughly 700 words in one unbroken block.

Across 627 ADR paragraphs, counting every block that is not a heading, table,
fence, quote or breadcrumb:

| Over | Count |
| --- | --- |
| 600 chars | 159 |
| **700 chars** | **125** ← the Part C threshold |
| 900 chars | 71 |
| 1,500 chars | 24 |

Median paragraph is 301 characters, so this is a tail problem: ~20% of
paragraphs carry the whole readability cost. The concentration is useful —
**six files hold a third of the walls**:

| File | Paragraphs > 700 |
| --- | --- |
| `adr-0055.md` | 11 |
| `adr-0083.md` | 10 |
| `adr-0035.md` | 6 |
| `adr-0080.md` | 5 |
| `adr-0079.md` | 4 |
| `adr-0081.md` | 4 |

Fix those six first and the log is most of the way there.

**This is drift, not a broken format.** `docs/adr/README.md` describes the
intended shape, and the early records follow it exactly. Read ADR-0005 (17 lines)
next to ADR-0079 and the difference is obvious:

```bash
cat docs/adr/adr-0005.md          # the target shape
sed -n '1,40p' docs/adr/adr-0079.md   # what the shape became
```

So the job is **reflow, not rewrite**. Every fact stays; it gets air.

## Part A — Reflow the dense ADRs

### A.1 Get the worklist

```bash
python3 - <<'EOF'
import pathlib
from collections import Counter
SKIP = ('#', '|', '`', '>', '🔖', '**Status')
rows = []
for p in sorted(pathlib.Path('docs/adr').glob('adr-*.md')):
    for blk in p.read_text().split('\n\n'):
        b = blk.strip()
        if b and not b.startswith(SKIP) and len(b) > 700:
            rows.append((len(b), p.name, b[:70].replace('\n', ' ')))
rows.sort(reverse=True)
print(f'{len(rows)} paragraphs over 700 chars, in {len(set(f for _, f, _ in rows))} files\n')
print('WORST FILES:')
for f, n in Counter(f for _, f, _ in rows).most_common(10):
    print(f'  {n:>3}  {f}')
print('\nWORST PARAGRAPHS:')
for n, f, head in rows[:20]:
    print(f'{n:5}  {f}  {head}...')
EOF
```

**Baseline: 125 rows.** Work by *file*, not by paragraph — reflowing one record
end-to-end is one coherent edit with one word-loss check (§A.4), whereas hopping
between files by paragraph size means re-reading each record's argument from
scratch. Take the six worst files first.

### A.2 The three reflow moves

Nearly every offender is one of three shapes. Apply the matching move; do not
invent a fourth.

**Move 1 — the numbered list that is really a section.** The dominant pattern in
ADR-0065+ is `1. **Bold claim.** <400 words>` repeated, with no blank line
between items, so the whole list renders as one wall. If each item is a
paragraph or more, it is not a list — it is a set of sub-decisions.

```markdown
<!-- before -->
**Decision.**
1. **Mask before matching.** <300 words>
2. **Fences win over spans.** <250 words>

<!-- after -->
**Decision.**

**1. Mask before matching.** <first 2 sentences: the rule itself>

<the rest, as its own paragraph or paragraphs>

**2. Fences win over spans.** <the rule>

<the reasoning>
```

The bold lead sentence becomes the scannable claim; the reasoning follows it
instead of being welded to it. A reader skimming for "what was decided" reads
only the bold leads.

**Move 2 — the paragraph that is a table.** Where a paragraph enumerates
alternatives, cases, or a mapping in prose ("for X we do A because…, for Y we do
B because…"), it is a table. Convert it. This is the single biggest legibility
win and it loses nothing — a table is *more* precise than the prose, because it
forces every cell to be filled.

**Move 3 — split the sentence chain.** Long paragraphs in this log are usually
4–8 sentences joined by em-dashes and semicolons. Break at the point where the
subject changes. One idea per paragraph, blank line between. No words removed.

### A.3 The rules while reflowing

These matter more than the moves, because this is a record of decisions and a
lossy edit is worse than a dense one:

- **Delete nothing.** Not a hedge, not a caveat, not a parenthetical. If a
  sentence seems redundant, it is probably the sentence that closes a loophole
  someone hit in production. Move it, do not cut it.
- **Do not re-argue.** You are not reviewing the decision; you are formatting it.
  If you think a decision is wrong, that is a separate ADR rewrite, not this
  phase.
- **Keep every file path, symbol name, config key and ADR cross-reference**
  exactly as written. They are the record's index into the code.
- **Preserve the six-section shape** the README documents: Status, Context,
  Decision, Consequences, Alternatives rejected, Where it lives. If a dense
  record has drifted from it, restoring the shape is part of the reflow.
- **Where it lives is not decoration.** Verify each path still exists while you
  are in the file:
  ```bash
  grep -ohE '`src/zrb/[a-z_/]+\.py`' docs/adr/adr-00NN.md | tr -d '`' | while read f; do
    test -e "$f" || echo "STALE PATH in adr-00NN: $f"
  done
  ```
  A stale path is a real finding — fix it in the same commit and note it.

  **Four are already stale**, found by running the sweep in §Verification against
  the current tree:

  | Cited path | Status |
  | --- | --- |
  | `src/zrb/llm/agent/tool_result.py` | gone — find where it moved |
  | `src/zrb/llm/app/layout.py` | gone — `llm/ui/default/app/` is the live path |
  | `src/zrb/llm/task/chat/building.py` | gone — find the surviving part |
  | `src/zrb/zrb_init.py` | **not a defect** — a user-authored file, `.coveragerc`-omitted, correctly cited as a concept |

  Locate each with `git log --diff-filter=D --name-only -- <path>` or a grep for
  the symbol the ADR names, and point the citation at the file that holds the
  behavior now. Do not delete the citation — a decision with no "where it lives"
  is a decision nobody can verify.

### A.4 Verify no content was lost

Reflow is exactly the edit where "it reads better now" hides a dropped clause.
One check, run per file before committing:

```bash
git diff --word-diff=porcelain docs/adr/adr-0079.md | grep '^-' | grep -v '^---'
```

That lists every word the edit removed. Read all of it. A removed word is
acceptable only if it is markdown punctuation, or a word that reappears
elsewhere in the same diff because you moved it. **A removed content word is a
bug** — put it back.

To sweep everything you touched at once:

```bash
for f in $(git diff --name-only docs/adr/); do
  out=$(git diff --word-diff=porcelain "$f" | grep '^-' | grep -v '^---')
  [ -n "$out" ] && { echo "=== $f"; echo "$out"; }
done
```

This is the whole quality gate for Part A. It is fast, it is mechanical, and it
is the only thing standing between a reflow and a silent loss of a decision's
reasoning — so do not skip it on "obviously safe" files.

### A.5 Where a record is genuinely too big

A few records (ADR-0079, ADR-0080, ADR-0090) carry more than one decision, which
is why they ballooned — `docs/adr/README.md` says "one decision per record" and
they do not follow it.

**Do not split them in this phase.** Splitting changes the numbering and every
cross-reference, and it is a decision about the *content* of the log, not its
formatting. Reflow them in place, and add a line to the worklist output naming
each one as a candidate for a later split. Then stop.

## Part B — Three missing tables of contents

```bash
for f in $(find docs -name '*.md' -not -path '*changelog*' -not -path '*adr*'); do
  l=$(wc -l < "$f"); [ "$l" -gt 150 ] && [ "$(grep -ci 'table of contents' "$f")" = "0" ] && echo "$l  $f"
done
```

Measured: `docs/advanced-topics/llm-custom-ui.md` (1,244 lines),
`docs/installation/installation.md` (465), and
`docs/advanced-topics/programming-the-prompt.md` (250).

Add a TOC to each, in the exact format the other 26 pages use — copy it from
`docs/configuration/llm-collections.md`, do not invent a second style.

`llm-custom-ui.md` at 1,244 lines is the longest page in the tree and the entry
point for anyone writing a UI. A TOC is the minimum. **Whether to split it is a
separate question** — it currently reads as one continuous tutorial, and
splitting a tutorial mid-flow usually makes it worse. Add the TOC, then judge
from the TOC whether the sections are independent enough to be pages. If they
are not, leave it as one page; length is not itself a defect.

## Part C — A ratchet so the drift cannot resume

New file `test/architecture/test_doc_density.py`. Prose is not code, so keep
this test forgiving in shape and strict in threshold:

```python
# The ADR log drifted from an average paragraph of 226 chars (ADR-0001-0030) to
# 615 (ADR-0061-0091) before anyone noticed. This holds the line.
MAX_ADR_PARAGRAPH_CHARS = 700
MAX_DOC_PARAGRAPH_CHARS = 900
MIN_LINES_REQUIRING_TOC = 150
```

Three tests:

- `test_no_adr_paragraph_is_a_wall` — parse each `docs/adr/adr-*.md`, split on
  blank lines, skip blocks starting with `#`, `|`, `` ` ``, `>`, `-`, `*`, `🔖`
  or a digit-dot, and assert none exceeds `MAX_ADR_PARAGRAPH_CHARS`. Report every
  offender with file, first 60 characters and length.
- `test_no_doc_paragraph_is_a_wall` — same over
  `docs/**/*.md` excluding `changelog*` and `adr/`. Changelogs are excluded on
  purpose: they are append-only history, never re-read start to finish.
- `test_long_doc_pages_have_a_table_of_contents` — any non-changelog page over
  `MIN_LINES_REQUIRING_TOC` lines contains "Table of Contents".

Set the thresholds **after** Part A lands, not before: 125 paragraphs exceed 700
characters today, so committing this test first just paints the suite red. Land
Part A, re-run the §A.1 worklist, and set `MAX_ADR_PARAGRAPH_CHARS` to whatever
the reflowed maximum is, rounded up to the next hundred.

700 is the target because it is roughly 110 words — long enough for a real
argument, short enough to read without losing the thread — and because the
median ADR paragraph is already 301, so it constrains only the tail. If Part A
leaves something legitimately over it (a long quoted error message, a pinned
config block that is not fenced), exempt that one file by name with a one-line
reason, the shape `test_boundaries.py` already uses for `MONKEYPATCH_EXCEPTIONS`.

## Part D — Tell readers the log is a lookup, not a book

`docs/adr/README.md` is already well-organized — themed index, a "How to read an
entry" section, an explicit rewrite-don't-supersede policy. One thing is missing:
it never says you are not supposed to read all 90.

Add two sentences under `# Architecture Decision Records`:

> **You are not expected to read this log.** It is a lookup table: find the
> record for the thing you are changing, read that one, and follow its "Where it
> lives" into the code. If you are new, start at
> [Which pattern do I reach for?](../advanced-topics/which-pattern.md) — it names
> the right ADR for each kind of change.

That single pointer does more for onboarding than the reflow does, and it costs
two sentences. It depends on Phase 0 §0.4 having landed, so sequence this after
Phase 0.

## Verification

```bash
cd /home/gofrendi/zrb
# no wall paragraphs left
python3 -c "
import pathlib
bad = [(len(b.strip()), p.name) for p in pathlib.Path('docs/adr').glob('adr-*.md')
       for b in p.read_text().split('\n\n')
       if b.strip() and not b.strip().startswith(('#','|','\`','>','🔖','**Status')) and len(b.strip()) > 700]
print('over 700 chars:', len(bad)); [print(' ', n, f) for n, f in sorted(bad, reverse=True)]
"
# no stale paths in Where-it-lives
grep -ohE '\`src/zrb/[a-z_/]+\.py\`' docs/adr/*.md | tr -d '\`' | sort -u | while read f; do test -e "$f" || echo "STALE: $f"; done
# TOCs present
for f in $(find docs -name '*.md' -not -path '*changelog*' -not -path '*adr*'); do
  l=$(wc -l < "$f"); [ "$l" -gt 150 ] && [ "$(grep -ci 'table of contents' "$f")" = "0" ] && echo "NO TOC: $f"
done
pytest test/architecture/test_doc_density.py -q
./zrb-test.sh
```

## Done when

No ADR paragraph exceeds 700 characters, `git diff --word-diff` shows no removed
content word in any reflowed record, every "Where it lives" path resolves, the
three pages have TOCs, `docs/adr/README.md` tells readers it is a lookup table,
and `test_doc_density.py` passes.

🔖 [Plan](README.md)
