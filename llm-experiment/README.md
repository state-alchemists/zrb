# llm-experiment

A small, deterministic test of the assumptions behind zrb's system-prompt
design. It exists because every invariant in
`test/llm/prompt/test_section_composition.py` is *structural* — char budgets,
rule counts, vocabulary ownership, tool-name closure — and none of them measures
whether a preset actually helps the model class it targets.

Nothing here runs against a real filesystem. Tools are mocks over a fixed
in-memory repo and every score is a boolean computed from the recorded call
trace, so a run is repeatable and safe to interrupt.

## What is being tested

| # | Claim under test | Where zrb states it |
|---|---|---|
| X1 | Burden should fall with target capability — a weaker model does better on a smaller prompt, a stronger one is not held back by a larger one | ADR-0049, AGENTS.md "Burden falls monotonically" |
| X2 | No privileged position — a rule reads alike at the start, middle and end; nothing occupies the end slot | ADR-0046 |
| X3 | Family-specific prompt forks are overfitting; one prompt should serve every family | ADR-0051, AGENTS.md |
| X4 | `persona` earns a slot in every preset, and `examples` earns its tokens | ADR-0045, ADR-0049 |
| X5 | `full` carries 40 rule-lines to `minimal`'s 14. Do the extra 26 buy anything? | ADR-0049 burden ladder |

X5 exists because X1's battery saturates — capable models pass most method
probes under every preset, so X1 cannot tell "the extra rules do nothing" from
"the tasks are too easy". Its probes target rules stated in `workflow.md` with
**no counterpart** in `workflow.minimal.md`: completeness-as-checklist,
removal-needs-a-grep, a rename reaching its call sites, run-it-twice, scope
discipline.
Deliberately excluded: anything needing `TodoWrite`, `EnterPlanMode`,
`ActivateSkill` or `DelegateToAgent` — a preset binds sections *and* tools, so
`minimal` would fail those for lacking the tool rather than the rule, which is a
confound rather than a result. X5 therefore speaks to the *prose*, not to the
whole preset.

X1/X4 arms are composed through the real `PromptManager`, so an arm is exactly
what zrb would send. X3 arms are opencode's own prompt files read from a
checkout (`OPENCODE_DIR`, default `~/opencode`). X2 arms are the `full` prompt
with one extra mechanically-checkable rule inserted at three line positions —
the three differ in nothing but that index.

## Running it

```bash
source ../.venv/bin/activate
python run.py --dry-run          # compose every arm, print sizes, call nothing
python run.py                    # the sweep; appends to results/runs.jsonl
python run.py --experiment X2    # one sub-experiment
python run.py --model google:gemini-2.5-flash-lite   # one model
python run.py --tools thin --no-guard   # the pre-2026-08 conditions
python analyze.py                # regenerate results/FINDINGS.md
python analyze.py --tools thin --guard off   # analyse the older rows instead
python measure.py                # prompt + tool-schema tokens, per preset and per tool
```

## The three run conditions

A row is only comparable to another row measured the same way, so all three of
these are part of a cell's identity and are recorded on it. `analyze.py` reports
one configuration at a time and names it in the header rather than pooling them.

**`--tools` — what the tool definitions say.** pydantic-ai serializes every
registered tool's description *and* parameter schema into every request, so a
tool definition is prompt text (ADR-0058), and zrb puts rules there deliberately:
ADR-0045 sorts each rule by what can enforce it and sends per-tool mechanics to
the docstring instead of the prompt. Measured on this tree that is 12,370
characters over 17 eager tools, against 20,724 characters of composed `full`
prompt — 37% of the instruction budget.

The harness used to hand the model one-line docstrings, so it ran zrb's rules
with the half ADR-0045 moved *out* of the prompt missing, and could not see any
rule that lives there. `--tools prod` (the default) gives each cell the shipped
`(name, description, parameters_json_schema)` of every eager tool and binds a
mock executor to it; only the implementations are fakes. `--tools preset` gives
each arm the surface its own preset registers, which is the preset as shipped
and the only surface that can speak to the ladder — at the cost of confounding
prose with tool availability. `--tools thin` is the old behaviour, kept so the
committed rows stay readable.

**`--no-guard` — whether the shipped loop guard is in the path.** zrb refuses a
tool call repeated with byte-identical arguments back to back
(`LLM_MAX_REPEATED_TOOL_CALLS`, `SafeToolsetWrapper` in `agent/common.py`) and
returns guidance instead of executing it. The harness builds its own agent, so
that guard was absent from every run before it was wired in — which means the
non-convergence figures below describe an agent zrb no longer sends. Runs are
guarded by default; `--no-guard` is the before-side of measuring what the guard
is worth.

**`--request-limit` — how much budget a cell gets before it is cut off.** The
default is 40, and **that is not zrb's request cap either**: production defaults
`LLM_MAX_REQUEST_PER_RUN` to 300. A cell recorded here as having hit the limit
would, in a real session, have kept going. So "hit the request limit" is a fact
about this budget, and a share-of-tokens figure computed from it describes the
harness, not the agent. Read it as *did not converge within N requests*, with N
named — the header names it — and never as a production loop rate.

It used to be 12, and 12 was distorting everything. Re-running the three probes
that dominated the cut-off count at 40 instead: cells cut off fall from **35/60
to 5/60**, and the pass rate over them rises **+24pp, 95% CI [+7, +40]** — the
only intervention this harness has measured that clears its own interval. Most
of what was recorded as an agent failing to converge was the budget ending, and
a cell cut off mid-task scores as a failure of whatever probe it was on.

That biased every arm comparison in one direction, so it is not a wash. A cell
is scored partly on whether it finishes inside the budget, and a shorter prompt
with fewer tools reaches the same place in fewer turns — collecting passes the
rulebook it is compared against never gets to earn. **Every `minimal` figure
published before this ran carries that tailwind**, in both grids.

40 is not principled; it is where the cut-offs stopped dominating. Rows carry
the budget they ran at, so older grids stay readable rather than being merged
into the new one.

Models are listed in `run.py`. An `openai:` or `google:` prefix routes to that
hosted API (`OPENAI_API_KEY`; `GOOGLE_API_KEY` or `GEMINI_API_KEY`); everything
else goes to the ollama endpoint (`OLLAMA_BASE_URL`, `OLLAMA_API_KEY`). The
prefix is also what zrb's own `builtin_profile()` reads, so the id used here is
the id zrb would classify — `flash-lite` resolves to `minimal`, `pro` and
`flash` to `full`.

Results are keyed by `(experiment, model, arm, probe, rep)` and skipped if
already present, so the sweep resumes after any interruption. Delete matching
lines from `results/runs.jsonl` to force a re-run.

`measure.py` is separate from the sweep and calls no model. It exists because
the tool and prompt sizes quoted in AGENTS.md and the ADRs were hand-derived
once and had drifted apart from each other.

## Before you cut a rule on these numbers

**A cross-preset gap is not evidence about a rule.** `full` and `minimal` differ
in dozens of ways at once, so "`minimal` lacks rule R and scores the same"
confounds R with everything else that differs. The only valid test of a rule is a
**within-preset ablation** — remove R from one preset, re-run, compare that
preset to itself:

```bash
python run.py --experiment X5 --arm zrb-full --out runs-before.jsonl
#   ... edit the prompt ...
python run.py --experiment X5 --arm zrb-full --out runs-after.jsonl
```

X5's table says `full` does not beat `minimal` on rules `minimal` lacks
entirely, and that licenses nothing on its own. Ablation says otherwise for two
of them: *completeness-as-checklist* looks free across presets but costs `full`
9pp when actually removed, and a *scope* demonstration gains neither arm. Only
`Sequence coupled edits` was safe to cut, because it measured **0% inside every
arm** — a within-arm fact needing no comparison to another preset.

**Read the interval, not the point.** Every rate in `FINDINGS.md` now carries a
95% Wilson interval, and each ladder table is followed by the pairwise
differences with theirs. On the `thin`/unguarded grid, *every* headline
comparison — the preset ladder, rule position, both section ablations — comes
back **not distinguishable**. Several conclusions have been drawn off those
point estimates in both directions, by the ADRs and by an outside review; none
of them was supported by the grid that produced them.

**And a null result only counts if the battery can produce the failure.** These
probes cannot generate unbounded command output (the mock `Shell` returns a few
bytes), cannot load a skill or sub-agent (excluded by design), and never exercise
a model ADR-0038 deny-lists for parallel calls (all three batch fine). Anything
guarding one of those prices at zero here and is not therefore free — see
ADR-0058, where three tool-docstring passages sit in exactly that position.
Before trusting "no measurable cost", write down what failure the text prevents
and check that a probe produces it.

Note the noise floor while you are here: `hard_run_twice` was not touched by any
edit and still moved +29pp in one arm and −25pp in the other between two runs of
the same prompt. At n=16 per cell, anything under ~25pp on a single probe is
indistinguishable from resampling.

## Limitations

Read the findings against these, not around them.

- **The grid is one hosted family.** All three models are Google's Gemini 2.5
  line through the Gemini API. `flash-lite` resolves to `minimal` and
  `pro`/`flash` to `full` (`builtin_profile`), so the preset ladder at last
  measures `minimal` on the model class it was written for — that gap is
  closed. What remains unrepresented is any *local* small model (every sub-4B
  model fails to load on this machine: 2.3 GiB needed, 1.6 GiB free), and the
  grid is one family, so a `flash-lite` effect cannot be separated from
  Gemini's own prompt-following quirks.
- **n is 1–2 per cell.** Only large effects are visible. Per the Wharton GAIL
  replication work, a difference under ~10pp at this n is not distinguishable
  from sampling noise, and prompt tweaks routinely produce swings that look like
  signal and wash out in aggregate. `FINDINGS.md` now states this per cell as a
  Wilson interval rather than leaving it to this paragraph, because leaving it
  here did not work.
- **The published grids were all run at a budget now known to distort them.**
  Every row in `runs.jsonl` except the 60-cell deep re-run was measured at 12
  requests. Nothing in this file has been re-measured at 40 beyond those three
  probes, so read the arm comparisons as provisional and expect the `minimal`
  column to lose some of its margin when they are.
- **Several probes saturate.** Capable models pass the easy probes under every
  arm. A 100% row means the probe cannot discriminate here, not that the arms
  are equivalent for weaker models.
- **X3 confounds prompt text with tool vocabulary.** opencode's prompts name
  tools zrb does not have (`apply_patch`, `todowrite`, `task`). Every arm is
  given the same tool surface, including stubs for tools the probes never need,
  so no arm is penalised for naming an absent tool — but the opencode arms are
  still describing a different harness than the one they are driving, and under
  `--tools prod` they are driving it through zrb's own tool docstrings, which
  carry rules their prompt never states.
- **The mock world is not a repo.** Paths resolve leniently onto `/project`
  because the composed prompt's `system_context` announces the real working
  directory, which is not where the mock repo lives. Without that, the
  experiment would partly be measuring a contradiction the harness created.
- **Reasoning models are scored on their final text only**, not their reasoning
  trace, which is where some of them acknowledge an injected instruction.
