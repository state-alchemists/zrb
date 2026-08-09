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
| X2 | Priority Order goes first and Final Reminders last because of primacy and recency effects | ADR-0046, AGENTS.md |
| X3 | Family-specific prompt forks are overfitting; one prompt should serve every family | ADR-0051, AGENTS.md |
| X4 | `persona` earns a slot in every preset, and `examples` earns its tokens | ADR-0045, ADR-0049 |
| X5 | `full` carries 42 rule-lines to `minimal`'s 18. Do the extra 24 buy anything? | ADR-0049 burden ladder |

X5 exists because X1's battery saturates — capable models pass most method
probes under every preset, so X1 cannot tell "the extra rules do nothing" from
"the tasks are too easy". Its probes target rules stated in `workflow.md` with
**no counterpart** in `workflow.minimal.md`: completeness-as-checklist,
removal-needs-a-grep, sequencing coupled edits, run-it-twice, scope discipline.
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
python run.py --model openai:gpt-4o-mini   # one model
python analyze.py                # regenerate results/FINDINGS.md
python measure.py                # prompt + tool-schema tokens, per preset and per tool
```

Models are listed in `run.py`. An `openai:` prefix routes to the hosted API
(`OPENAI_API_KEY`); everything else goes to the ollama endpoint
(`OLLAMA_BASE_URL`, `OLLAMA_API_KEY`). The prefix is also what zrb's own
`builtin_profile()` reads, so the id used here is the id zrb would classify.

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

X5's table says `full` (44%) does not beat `minimal` (41%) on rules `minimal`
lacks entirely, and that licenses nothing on its own. Ablation says otherwise for
two of them: *completeness-as-checklist* looks free across presets but costs
`full` 9pp and `lean` 12pp when actually removed, and a *scope* demonstration
gains neither arm. Only `Sequence coupled edits` was safe to cut, because it
measured **0% inside every arm** — a within-arm fact needing no comparison to
another preset.

**And a null result only counts if the battery can produce the failure.** These
probes cannot generate unbounded command output (the mock `Shell` returns a few
bytes), cannot load a skill or sub-agent (excluded by design), and never exercise
a model ADR-0038 deny-lists for parallel calls (all eight batch fine). Anything
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

- **`lean`'s target class is represented; `minimal`'s is not.** `gpt-4o-mini`
  and `gpt-4.1-nano` are hosted small-tier models, and zrb resolves both to
  `lean` — a hosted small-tier label alone never reaches `minimal`, which needs
  a local provider prefix or a declared ≤4B size. So the ladder's `full`→`lean`
  rung is tested against the class it was written for, and the `lean`→`minimal`
  rung is not: every local sub-4B model fails to load on this machine (2.3 GiB
  needed, 1.6 GiB free) and every small cloud model on the endpoint has been
  retired. **X1 can speak to `lean`; on `minimal` it can only fail to find an
  effect among models that are not its target.**
- **n is 1–2 per cell.** Only large effects are visible. Per the Wharton GAIL
  replication work, a difference under ~10pp at this n is not distinguishable
  from sampling noise, and prompt tweaks routinely produce swings that look like
  signal and wash out in aggregate.
- **Several probes saturate.** Capable models pass the easy probes under every
  arm. A 100% row means the probe cannot discriminate here, not that the arms
  are equivalent for weaker models.
- **X3 confounds prompt text with tool vocabulary.** opencode's prompts name
  tools zrb does not have (`apply_patch`, `todowrite`, `task`). Every arm is
  given the same tool surface, including stubs for tools the probes never need,
  so no arm is penalised for naming an absent tool — but the opencode arms are
  still describing a different harness than the one they are driving.
- **The mock world is not a repo.** Paths resolve leniently onto `/project`
  because the composed prompt's `system_context` announces the real working
  directory, which is not where the mock repo lives. Without that, the
  experiment would partly be measuring a contradiction the harness created.
- **Reasoning models are scored on their final text only**, not their reasoning
  trace, which is where some of them acknowledge an injected instruction.
