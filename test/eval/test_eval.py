"""The paid suite: every test is one real agent run against a fixture repository.

Skipped unless `LLM_EVAL_RUN` is set, because each test spends money and minutes.
`./zrb-test.sh eval` sets it; `README.md` here explains the rest.
"""

import pytest
from harness import eval_enabled, format_report, run_task
from tasks import TASKS

pytestmark = [
    pytest.mark.llm_eval,
    pytest.mark.skipif(
        not eval_enabled(),
        reason="paid agent eval; run `./zrb-test.sh eval` to enable it",
    ),
]


@pytest.mark.parametrize("task", TASKS, ids=[task.name for task in TASKS])
@pytest.mark.timeout(420)
def test_task(task, tmp_path):
    """One task: materialize, let the agent work, then judge the workspace."""
    result = run_task(task, tmp_path)
    print("\n" + format_report([result]))
    if not result.passed:
        detail = "\n".join(result.failures) or f"the CLI exited {result.exit_code}"
        pytest.fail(
            f"{task.name}: {detail}\n\nagent output tail:\n{result.output_tail}"
        )
