"""Every model run zrb starts is attributed, or is named here as a known gap.

A line that does not say what spent it is not lost — it is filed under the turn
that happened to be running, which is worse: `/usage` then reads a conversation
as doing its own work while the judge, the reviewer and the namer spend beside
it. This is the same shape as `test/builtin/test_registration_completeness.py`:
the thing that must not be forgotten is found by walking the tree, so forgetting
it fails a test instead of hiding.

`KNOWN_UNATTRIBUTED` is a debt register, not an allowlist to append to. An entry
leaves it when the site records, and a new site never enters it.
"""

import pathlib
import re

SRC = pathlib.Path(__file__).parents[2] / "src" / "zrb"

# A model run finishing, in the three shapes the tree uses: an agent the caller
# built itself, the engine's `run_agent`, and a sub-agent's own run.
_RUNS = re.compile(r"await agent\.run\(|= await run_agent\(|await sub_agent\.run\(")
# What makes such a site attributable: the line writer, or the ambient tag that
# makes the run's own lines inherit a component.
_ATTRIBUTES = re.compile(r"record_agent_usage\(|usage_component\(")

# Path -> why this site does not attribute its run today.
KNOWN_UNATTRIBUTED = {
    "llm/agent/run/runner.py": (
        "the recorder itself: the conversation's rounds are `main_agent` by default"
    ),
    "llm/summarizer/text_summarizer.py": (
        "its calls are folded into the compaction total that writes the line, so a "
        "second line here would count the same tokens twice"
    ),
    "llm/tool/file/analyze.py": (
        "goes through `run_agent`, so it is recorded, but filed as `main_agent`; "
        "naming it needs a component threaded through the tool path"
    ),
    "llm/tool/web/tools.py": "same as `tool/file/analyze.py`",
    "llm/tool/code/analysis.py": "same as `tool/file/analyze.py`",
    "llm/tool/multimodal_describe.py": "same as `tool/file/analyze.py`",
    "llm/dictation/backend/multimodal.py": "same as `tool/file/analyze.py`",
    "llm/task/llm_task.py": (
        "same as `tool/file/analyze.py`: an LLMTask's rounds reach the engine "
        "without saying they are the task's"
    ),
}


def _relative(path: pathlib.Path) -> str:
    return path.relative_to(SRC).as_posix()


def _attribution_state() -> dict[str, tuple[bool, bool]]:
    """Path -> (runs a model, attributes that run) for every module under src."""
    state: dict[str, tuple[bool, bool]] = {}
    for path in SRC.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if _RUNS.search(text) is None:
            continue
        state[_relative(path)] = (True, _ATTRIBUTES.search(text) is not None)
    return state


def test_every_model_run_says_what_spent_it():
    unattributed = sorted(
        path for path, (_, attributed) in _attribution_state().items() if not attributed
    )
    unexpected = [path for path in unattributed if path not in KNOWN_UNATTRIBUTED]
    assert unexpected == [], (
        "These modules run a model without attributing the line. Call "
        "`record_agent_usage(...)` after the run, or wrap it in "
        "`usage_component(...)`; do not add them to KNOWN_UNATTRIBUTED: "
        f"{unexpected}"
    )


def test_the_debt_register_does_not_keep_what_was_fixed():
    """An entry that now attributes its run is a stale excuse, and a stale
    excuse is how a register like this stops being read."""
    state = _attribution_state()
    fixed = sorted(
        path
        for path in KNOWN_UNATTRIBUTED
        if state.get(path, (False, False))[1] or path not in state
    )
    assert fixed == [], (
        "These modules now attribute their run (or no longer run one), so their "
        f"entries in KNOWN_UNATTRIBUTED are stale: {fixed}"
    )
