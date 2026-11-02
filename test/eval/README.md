# Agent evaluation

Sixteen fixture repositories, each with one request a user might make and a set
of checks that read the finished workspace. A task passes only when the run
exits cleanly **and** every check agrees.

This exists because "the agent feels worse" is not a bug report. Coverage of
`src/` says nothing about whether a model edits the right file, leaves a stale
reference, or claims success on code that does not run.

## Running it

```sh
./zrb-test.sh eval                                   # the default configured model
LLM_EVAL_MODEL=deepseek:deepseek-chat ./zrb-test.sh eval
./zrb-test.sh eval -k rename                          # one task
./zrb-test.sh eval -x                                 # stop at the first failure
```

It is opt-in: each test is a real model call, so it is skipped in the normal
suite (`LLM_EVAL_RUN` unset). Expect a few minutes and a small API bill for the
full set.

| Variable | Meaning |
| --- | --- |
| `LLM_EVAL_RUN` | Set by the script. Without it, the 16 tests skip. |
| `LLM_EVAL_MODEL` | Model for the child runs, e.g. `deepseek:deepseek-chat`. Passed through as `ZRB_LLM_MODEL`. |

`LLM_EVAL_MODEL` has a non-`ZRB_` name on purpose: `test/conftest.py` scrubs the
`ZRB_*` namespace before collection, so a `ZRB_LLM_MODEL` exported in your shell
would never reach the harness. Provider API keys are untouched by that scrub and
are inherited normally.

## What it measures

The agent runs through the real entry point — `python -m zrb llm chat --message
… --interactive false --yolo true` — in its own process and directory. Nothing is
stubbed, so the score covers the prompt, the tool surface, the loop, and the
provider integration together. That is deliberate: a harness that calls an
internal API can stay green while the product regresses.

The run also reports input/output tokens per task, which is the number that makes
"efficient" a measurement instead of an opinion.

## What a pass means

Checks import the module or run the suite, because a plausible-looking edit that
does not run is the failure mode worth catching. `no_collateral_damage` hashes an
unrelated file and fails if it moved, and `fix_failing_test` hashes the test file
and fails if the agent "fixed" it by editing the assertion.

## Adding a task

1. Add an `EvalTask` to `tasks.py`: a `name`, a `prompt`, the `files` it starts
   from, and one or more `checks`.
2. A check takes the workspace `Path` and returns a failure reason, or `None`.
   Prefer `run_python` / `run_pytest` / `run_script` from `harness.py` over
   reading text: the point is whether the result works. Use `run_script` when
   the request names a script and its output — an import skips the
   `if __name__ == "__main__"` block, so the code path the task is about may
   never run.
3. **A check must reject a plausible wrong answer**, not just accept the right
   one. For a task whose answer could be faked (`print(42)`), assert the
   behaviour that proves the work was done, and add the wrong answer as an
   offline case in `test_harness.py`: `missing_offset = 0` runs cleanly and
   prints `6`, so a check that only looks for "no exception" passes on it.
4. Keep it small and unambiguous — a task that needs a judgement call measures
   the judge.
5. `test_harness.py` runs offline and keeps the harness honest; extend it when
   you add harness behavior or a check that could go vacuous.

## Known limitations

- One run per task: model nondeterminism means a single failure is a signal, not
  a proof. Re-run a failing task before believing a regression.
- Tasks are Python-only and tiny. They do not cover long-horizon work,
  multi-file refactors of real size, or UI behavior.
- The child process inherits the developer's environment, so a misconfigured
  provider fails every task with the same error rather than one interesting one.
