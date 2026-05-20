# LLM Framework Evaluation & Optimization Protocol

**TARGET AUDIENCE:** AI Agents (Zrb, Gemini CLI, etc.) and Maintainers.
**OBJECTIVE:** Run, Evaluate, and Improve the `zrb` LLM framework.

## Mission
Your goal is to ensure `zrb llm chat` can autonomously and correctly solve
complex software engineering tasks. You will run a series of challenges via
[`zrb-llm-evaluator`](https://github.com/state-alchemists/zrb-llm-evaluator),
evaluate the results against strict criteria, and modify the `zrb` source code
(prompts and tool definitions) to fix any failures.

## The Challenges
Located in `challenges/` (relative to this directory). Each subdirectory is a
single test case in the format `zrb-llm-evaluator` expects:

```
challenges/<name>/
├── instruction.txt   # prompt sent to the LLM
├── workdir/          # scaffolding files staged into the trial cwd
└── validator.py      # exposes a `validator` implementing ValidatorProtocol
```

Current challenges:
- `bug-fix`
- `copywriting`
- `feature`
- `integration-bug`
- `refactor`
- `research`

## Execution Protocol

**Prerequisite:** `zrb-llm-evaluator` installed (`pipx install zrb-llm-evaluator`
or `poetry install` from its repo). `zrb` itself must be on PATH and configured
with the appropriate API keys.

### 1. EXECUTE

Run the full grid (all challenges × the models you care about):

```bash
zrb-llm-evaluator run \
  --models openai:gpt-4o,google-gla:gemini-2.5-flash,deepseek:deepseek-chat \
  --test-cases ./challenges/bug-fix,./challenges/copywriting,./challenges/feature,./challenges/integration-bug,./challenges/refactor,./challenges/research \
  --trials 3 \
  --parallelism 4 \
  --timeout 300 \
  --output-dir ./experiment
```

Quick smoke test (single model, single challenge, one trial):

```bash
zrb-llm-evaluator run \
  --models openai:gpt-4o \
  --test-cases ./challenges/bug-fix \
  --trials 1 \
  --parallelism 1 \
  --timeout 120 \
  --output-dir ./experiment
```

The runner will:
1. Build the full grid of model × test_case × trial cells.
2. Stage each test case's `workdir/` into an isolated cell directory under
   `experiment/<model>/<test_case>/trial-N/`.
3. Invoke `zrb chat --interactive false --message <instruction>` in that cell.
4. Invoke the test case's `validator.py` against the cell directory and the
   conversation log.
5. Write `experiment/results.json` atomically after each trial and a
   `experiment/report.md` at the end.

Resume support is automatic — re-running with the same `--output-dir` skips
cells whose status is already terminal (`EXCELLENT | PASS | FAIL | TIMEOUT |
ERROR`).

To regenerate the Markdown report from existing results without re-running:

```bash
zrb-llm-evaluator report --dir ./experiment
```

### 2. ANALYZE

Open `experiment/report.md` (or inspect `experiment/results.json` directly).

| Status      | Meaning                                                          |
|-------------|------------------------------------------------------------------|
| `EXCELLENT` | All checks passed, including the stricter optional ones.         |
| `PASS`      | Core criteria met; stricter bar missed.                          |
| `FAIL`      | Validator rejected the output.                                   |
| `TIMEOUT`   | Subprocess hit `--timeout`; output preserved as far as it got.   |
| `ERROR`     | Validator raised, or `zrb` exited non-zero with no marker.       |

For per-cell forensics, look under `experiment/<model>/<test_case>/trial-N/`:
- `chat.log` — combined stdout/stderr
- `history/<session>.json` — `ZRB_LLM_HISTORY_DIR` recording
- Any files the model produced (validators read from this directory)

### 3. OPTIMIZE

**IF AND ONLY IF** a challenge fails or is solved inefficiently:
1. **Analyze**: Read `chat.log` and `history/<session>.json` for the failing
   trial(s).
2. **Refactor `zrb`**: Modify the core framework files.
   - **Prompts**: `src/zrb/llm/prompt/markdown/`, especially `persona.py` and
     `mandates.py`
   - **Tools**: `src/zrb/llm/tool/`
3. **Retry**: Re-run the evaluator. Resume support lets you target just the
   challenges that regressed by deleting their entries from `results.json`
   (or by using a fresh `--output-dir`).

## Creating New Challenges

To create a new challenge:
1. Create `challenges/<name>/`.
2. Add `instruction.txt` — the prompt for the agent.
3. Add `workdir/` — the initial files the agent will see in its cwd.
4. Add `validator.py` exposing a top-level `validator` object that implements
   `ValidatorProtocol` (see `zrb_llm_evaluator.protocols.ValidatorProtocol`).
   Return a `ValidationResult` with `status`, `score`, and `details`.

Minimal validator template:

```python
from pathlib import Path
from zrb_llm_evaluator.models import ValidationCheck, ValidationResult
from zrb_llm_evaluator.protocols import ValidatorProtocol


class MyValidator:
    def validate(self, output_dir: Path, log_content: str) -> ValidationResult:
        produced = (output_dir / "expected_artifact.md").is_file()
        return ValidationResult(
            status="PASS" if produced else "FAIL",
            score=1.0 if produced else 0.0,
            details=[
                ValidationCheck(
                    name="expected_artifact",
                    passed=produced,
                    message="expected_artifact.md present" if produced
                            else "expected_artifact.md not produced",
                ),
            ],
        )


validator = MyValidator()
```

The framework validates protocol conformance at load time — a `validator.py`
that doesn't implement `ValidatorProtocol` is rejected before any trial runs.

## Rules of Engagement
1. **DO NOT MODIFY CHALLENGES**: You are testing `zrb`, not the test itself.
2. **BE RUTHLESS**: Partial credit is FAILURE.
3. **SELF-CORRECTION**: If `zrb-llm-evaluator` itself fails due to environment
   issues, fix the environment. If it fails due to an evaluator bug, file an
   issue or patch the evaluator — don't paper over it in the validators.
4. **SMOKE TEST FIRST**: Always run a single-trial, single-challenge smoke
   test to validate your setup before launching a full grid.
