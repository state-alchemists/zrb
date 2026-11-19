"""Every model run zrb starts is attributed, or is named here as a known gap.

A line that does not say what spent it is not lost — it is filed under the turn
that happened to be running, which is worse: `/usage` then reads a conversation
as doing its own work while the judge, the reviewer and the namer spend beside
it. This is the same shape as `test/builtin/test_registration_completeness.py`:
the thing that must not be forgotten is found by walking the tree, so forgetting
it fails a test instead of hiding.

A row is the second half of that promise. The summed line says what a run cost;
`request-YYYY-MM.jsonl` says what the run was made of. A site that writes the
first and not the second leaves the two logs disagreeing about the same call,
which is how the summarizer's chunks and the changelog were found unwired — each
one in review, each one a file nobody had looked at twice.

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
# The writers that make a site answerable at request level too: its own rows, or
# the turn loop's, which are the cursor's and are written once per round.
_ROWS = re.compile(r"record_standalone_requests\(|record_round_requests\(")
# The modules that define the writers rather than call them.
_WRITER_MODULES = {
    "llm/contracts/shared/request_log.py",
    "llm/contracts/shared/usage_log.py",
}
# A wrapper that hands its run to the turn loop: its rows are the cursor's, and
# the line here only names the component the run inherits.
_ROWS_COME_FROM_THE_RUN = {"llm/contracts/shared/subagent_turn.py"}

# Path -> why this site does not attribute its run today.
KNOWN_UNATTRIBUTED = {
    "llm/engine/agent/run/runner.py": (
        "the recorder itself: the conversation's rounds are `main_agent` by default"
    ),
    "llm/engine/summarizer/text_summarizer.py": (
        "its calls are folded into the compaction total that writes the line, so a "
        "second line here would count the same tokens twice"
    ),
    "llm/capabilities/tool/file/analyze.py": (
        "goes through `run_agent`, so it is recorded, but filed as `main_agent`; "
        "naming it needs a component threaded through the tool path"
    ),
    "llm/capabilities/tool/web/tools.py": "same as `tool/file/analyze.py`",
    "llm/capabilities/tool/code/analysis.py": "same as `tool/file/analyze.py`",
    "llm/capabilities/tool/multimodal_describe.py": "same as `tool/file/analyze.py`",
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


def test_every_summed_line_also_writes_its_request_rows():
    """A site that says what a run cost must say what the run was made of.

    The turn loop is answered for by `record_round_requests`, written once per
    round from the cursor; every other site that writes a line of its own writes
    its rows through `record_standalone_requests`. A site that does neither
    leaves the two logs disagreeing about the same call, which is how the
    summarizer's chunks and the changelog were found unwired.
    """
    missing: list[str] = []
    for path in SRC.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if _ATTRIBUTES.search(text) is None:
            continue
        if _relative(path) in _WRITER_MODULES | _ROWS_COME_FROM_THE_RUN:
            continue
        if _ROWS.search(text) is None:
            missing.append(_relative(path))

    assert missing == [], (
        "These modules write a usage line without request rows. Add "
        "`record_standalone_requests(result, reason, component=...)` after the "
        f"run, with the same component the line carries: {sorted(missing)}"
    )


def test_every_reason_names_a_call_site():
    """A reason defined and never passed is the fingerprint of a missed site.

    `REASON_SUMMARIZER` was written with the vocabulary and never reached a call
    site, and the compaction's requests went unrecorded until a review found them.
    A name has to appear at least twice: where it is defined, and where it is
    used.
    """
    sources = [path.read_text(encoding="utf-8") for path in SRC.rglob("*.py")]
    definitions = (SRC / "llm/contracts/shared/request_log.py").read_text(
        encoding="utf-8"
    )
    unused = [
        name
        for name in re.findall(r"^(REASON_[A-Z_]+) = ", definitions, re.M)
        if sum(text.count(name) for text in sources) < 2
    ]

    assert unused == [], f"These reasons name no call site: {unused}"
