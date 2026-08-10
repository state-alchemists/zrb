"""Runner: every (experiment, model, arm, probe, rep) cell, resumable.

Results append to ``results/runs.jsonl``. A cell already present in that file is
skipped, so the sweep can be interrupted and restarted freely.

    python run.py --dry-run     # compose every arm, print sizes, call nothing
    python run.py               # run the sweep
    python run.py --experiment X1 --model qwen3:4b
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import textwrap
import time
from pathlib import Path

from probes import (
    BUILD_ERROR,
    CANARY_PROBE,
    HARD_PROBES,
    PROBES,
    PROBES_BY_NAME,
    WORLD,
    X3_PROBES,
    Call,
    Trace,
)
from surface import tool_defs
from treatments import canary_arms, opencode_arms, zrb_arms

RESULTS = Path(__file__).parent / "results" / "runs.jsonl"

#: How a cell defines its tools. The axis exists because a tool definition is
#: prompt text — pydantic-ai serializes every registered tool's description and
#: parameter schema into every request — and zrb puts rules there on purpose
#: (ADR-0045, ADR-0058). Measured on this tree the eager surface is 3,860
#: tokens against 4,827 of composed `full` prompt, so a run on `thin` is a run
#: with 44% of the instruction budget absent.
#:
#: - ``thin``  one-line docstrings, identical for every arm. What the committed
#:             runs used. Kept so those rows stay comparable, not because it is
#:             a fair picture of what zrb sends.
#: - ``prod``  the `full` preset's shipped definitions, identical for every arm.
#:             Prompt text stays the only variable, now at production weight and
#:             with the docstring half of the rules present.
#: - ``preset`` each arm gets the surface its own preset registers. This is the
#:             preset *as shipped* — ADR-0049 binds sections and tools together
#:             — and is the only surface that can answer whether the ladder
#:             works, at the cost of confounding prose with tool availability.
SURFACES = ("thin", "prod", "preset")

#: Requests a cell may spend before it is cut off and recorded as
#: non-convergent. **This is not zrb's request cap** — production defaults
#: `LLM_MAX_REQUEST_PER_RUN` to 300, which the grid cannot afford. So "hit the
#: request limit" is a statement about this budget: read it as "did not converge
#: within N requests", with N stated, never as a production loop rate.
#:
#: A cell cut off mid-task scores as a failure of whatever probe it was on, which
#: biases every arm comparison one way — a shorter prompt with fewer tools needs
#: fewer turns to reach the same place, so it collects passes the rulebook it is
#: compared against never gets to earn. 40 is where the cut-offs stopped
#: dominating, not a principled number. It is recorded on every row and is part
#: of a cell's identity, so a deeper run resumes as new work.
DEFAULT_REQUEST_LIMIT = 40

#: What a row with no ``request_limit`` field was actually run at. Backfilling
#: from `DEFAULT_REQUEST_LIMIT` looks equivalent and is not: raising the default
#: would re-label every historical row as measured at the new value, and
#: `done_keys` would report a grid run at 12 as already done at 40.
LEGACY_REQUEST_LIMIT = 12

#: Which preset's tool surface an arm gets under ``--tools preset``. An arm
#: that is not a zrb preset (the opencode and canary arms) is driving a prompt
#: written for another harness entirely, so it gets `full` — the widest surface
#: — rather than a preset it never claimed.
ARM_PRESET = {"zrb-minimal": "minimal"}

# `pro` and `flash` resolve to `full`; `flash-lite` resolves to `minimal` (see
# `builtin_profile`), so the grid contains the model class the smaller preset was
# written for.
MODELS = [
    "google:gemini-2.5-pro",  # strong tier
    "google:gemini-2.5-flash",  # latency tier, spans weak to strong
    "google:gemini-2.5-flash-lite",  # lightweight tier — zrb resolves it to `minimal`
    "deepseek:deepseek-v4-flash",  # DeepSeek's own API, not ollama's cloud proxy
    "ollama:gemma4:31b-cloud",
]

# Every arm sees the same tool surface, so prompt text is the only variable.
# Stubs exist for tools the prompts name but the probes never need; without
# them a richer prompt would be penalised for naming a tool that is absent.
STUB_TOOLS = {
    "TodoWrite": "Todos updated.",
    "TodoRead": "No todos.",
    "WebFetch": "ERROR: network disabled in this environment.",
    "WebSearch": "ERROR: network disabled in this environment.",
    "ActivateSkill": "ERROR: no such skill.",
    "AskUserQuestion": "The user did not respond. Proceed with your best judgement.",
    "DelegateToAgent": "ERROR: no sub-agent is available in this environment.",
    "MonitorProcess": "No background process is running.",
    "SearchJournal": "No journal entries.",
    "LogActivity": "Logged.",
    "WriteJournalNote": "Note written.",
}


def build_tools(trace: Trace, turn: "list[int]", defs=None, guard=None):
    """Mock tools over a private, mutable copy of WORLD.

    ``turn`` is a one-element cell holding the index of the model response
    currently being executed, so batching can be measured. ``defs`` is the tool
    surface to present — ``None`` for the thin one-line-docstring surface,
    otherwise the shipped ``ToolDefinition``s from `surface.tool_defs`.
    ``guard`` is a `RepeatedCallDetector`, or ``None`` to run without the loop
    guard zrb ships.

    **The writes have to land.** A mock that records the call and changes nothing
    penalises exactly the arms whose prompts insist on verification: a model that
    checks the artifact instead of its memory of writing it reads the file back,
    finds the typo still there, and concludes the filesystem is broken. That is a
    confound pointing straight at the comparison this harness exists to make.

    The copy is per call, and ``build_tools`` is called once per cell, so cells
    cannot see each other's writes. ``WORLD`` itself stays pristine.
    """
    # lazy: pydantic_ai is heavy and only needed once a run actually starts
    from pydantic_ai import Tool

    world = dict(WORLD)
    # The same dict object, not a copy, so the scorer reads the state the cell
    # finished in rather than the state it started in.
    trace.world = world

    def rec(name: str, **args) -> None:
        trace.calls.append(Call(turn=turn[0], tool=name, args=args))

    def resolve(path: str) -> str:
        """Map a path onto the mock world.

        The zrb prompt's system_context announces the *real* cwd, which is not
        where the mock repo lives. Rather than let that contradiction decide the
        experiment, a path outside the world falls back to its basename under
        /project. A genuinely absent file still misses, so
        ``method_no_invented_path`` stays falsifiable.
        """
        if path in world:
            return path
        candidate = "/project/" + path.rsplit("/", 1)[-1]
        return candidate if candidate in world else path

    def Read(path: str) -> str:
        """Read a file from disk."""
        rec("Read", path=path)
        target = resolve(path)
        return world.get(target, f"ERROR: {path}: no such file or directory")

    def Write(path: str, content: str) -> str:
        """Write a whole new file."""
        rec("Write", path=path, bytes=len(content))
        # A write to a path the world has never seen creates it, exactly as it
        # would on disk — `method_deliver_to_disk` turns on that being possible.
        world[resolve(path) if resolve(path) in world else path] = content
        return f"Wrote {path}."

    def Edit(path: str, old_string: str, new_string: str) -> str:
        """Replace a string inside an existing file."""
        rec("Edit", path=path, old=old_string, new=new_string)
        target = resolve(path)
        if target not in world:
            return f"ERROR: {path}: no such file or directory"
        # Strict on a missing anchor, like the shipped tool: reporting success for
        # a replacement that matched nothing is the same lie in a smaller size.
        if old_string not in world[target]:
            return (
                f"ERROR: {path}: old_string not found in file; "
                f"read it and match the exact text"
            )
        world[target] = world[target].replace(old_string, new_string, 1)
        return f"Edited {path}."

    def Glob(pattern: str) -> str:
        """Find files by name pattern."""
        rec("Glob", pattern=pattern)
        stem = pattern.replace("*", "").replace("**", "").strip("/")
        hits = [p for p in world if stem and stem in p]
        return "\n".join(hits) if hits else "No files matched."

    def Grep(pattern: str) -> str:
        """Search for text inside files."""
        rec("Grep", pattern=pattern)
        hits = [
            f"{p}: {ln}"
            for p, body in world.items()
            for ln in body.splitlines()
            if pattern.lower() in ln.lower()
        ]
        return "\n".join(hits) if hits else "No matches found."

    def LS(path: str) -> str:
        """List a directory."""
        rec("LS", path=path)
        base = path.rstrip("/") or "/"
        kids = sorted(
            {
                p[len(base) + 1 :].split("/")[0]
                for p in world
                if p.startswith(base + "/")
            }
        )
        if kids:
            return "\n".join(kids)
        # A root-ish path resolves to the project root for the same reason
        # `resolve` exists: the announced cwd is not where the world lives.
        if base in ("/", ".", os.getcwd(), str(Path.cwd()), "/project"):
            return "\n".join(
                sorted({p[len("/project/") :].split("/")[0] for p in world})
            )
        return f"ERROR: {path}: no such directory"

    def RM(path: str) -> str:
        """Delete a file."""
        rec("RM", path=path)
        target = resolve(path)
        if target not in world:
            return f"ERROR: {path}: no such file or directory"
        del world[target]
        return f"Deleted {path}."

    def MV(source: str, destination: str) -> str:
        """Move or rename a file."""
        rec("MV", source=source, destination=destination)
        target = resolve(source)
        if target not in world:
            return f"ERROR: {source}: no such file or directory"
        world[destination] = world.pop(target)
        return f"Moved {source} to {destination}."

    def Shell(command: str) -> str:
        """Run a shell command."""
        rec("Shell", command=command)
        # This mock cannot emulate arbitrary shell mutation, and returning
        # "(no output)" for a `sed -i` is success-shaped silence. Refuse, and name
        # the tool that works — which is what the shipped `Shell` docstring does.
        if any(
            tok in command
            for tok in ("sed -i", " > ", " >> ", "tee ", "truncate", "dd ")
        ):
            return (
                "ERROR: this shell cannot modify files. "
                "Use Write to replace a file or Edit to change part of one."
            )
        # Order matters: a read-only command is dispatched on its *verb*, so
        # `cat test_auth.py` reads a file instead of being mistaken for a test
        # run by a substring match on "test".
        verbs = [
            w
            for w in command.replace("|", " ").split()
            if w in ("ls", "find", "cat", "head", "tail", "grep", "rg", "wc")
        ]
        if verbs:
            if "wc" in verbs:
                paths = [w.strip("'\"") for w in command.split() if "/" in w]
                bodies = [world[resolve(p)] for p in paths if resolve(p) in world]
                if not bodies:
                    return "wc: no such file"
                return "\n".join(
                    f"{len(b.splitlines()):8d} {p}" for p, b in zip(paths, bodies)
                )
            paths = [w.strip("'\"") for w in command.split() if "/" in w]
            if verbs[0] in ("cat", "head", "tail"):
                bodies = [world[resolve(p)] for p in paths if resolve(p) in world]
                return "".join(bodies) or "(no output)"
            roots = paths or ["/project"]
            hits = sorted(
                p for p in world if any(p.startswith(r.rstrip("/")) for r in roots)
            )
            return "\n".join(hits) or "(no output)"
        if "make" in command:
            return BUILD_ERROR
        if "pytest" in command or "test" in command:
            return "1 passed in 0.04s"
        return "(no output)"

    def make_stub(name: str, reply: str):
        def stub(**kwargs) -> str:
            rec(name, **kwargs)
            return reply

        stub.__name__ = name
        stub.__doc__ = f"{name} tool."
        return stub

    # Surfaces differ only in what the model is *told* the arguments are called,
    # so each is an argument-name adapter over the functions above.
    typed = (Read, Write, Edit, Glob, Grep, LS, RM, MV, Shell)
    if defs is None:
        thin = [Tool(f, name=f.__name__, takes_ctx=False) for f in typed]
        thin += [
            Tool(make_stub(n, r), name=n, takes_ctx=False)
            for n, r in STUB_TOOLS.items()
        ]
        defs = [t.tool_def for t in thin]
        executors = {f.__name__: (lambda f: lambda **kw: f(**kw))(f) for f in typed}
        executors.update(
            {n: make_stub(n, r) for n, r in STUB_TOOLS.items()},
        )
    else:
        # Production parameter names are not the mocks': `Edit` takes
        # `old_text`/`new_text`, `MV` takes `src`/`dst`.
        executors = {
            "Read": lambda **kw: Read(kw.get("path", "")),
            "Write": lambda **kw: Write(kw.get("path", ""), kw.get("content", "")),
            "Edit": lambda **kw: Edit(
                kw.get("path", ""), kw.get("old_text", ""), kw.get("new_text", "")
            ),
            "Glob": lambda **kw: Glob(kw.get("pattern", "")),
            "Grep": lambda **kw: Grep(kw.get("pattern", "")),
            "LS": lambda **kw: LS(kw.get("path", "")),
            "RM": lambda **kw: RM(kw.get("path", "")),
            "MV": lambda **kw: MV(kw.get("src", ""), kw.get("dst", "")),
            "Shell": lambda **kw: Shell(kw.get("command", "")),
        }

    def executor(name: str):
        return executors.get(name) or make_stub(name, MISSING_STUB)

    return [
        Tool.from_schema(
            _guarded(td.name, executor(td.name), guard, rec),
            name=td.name,
            description=td.description,
            json_schema=td.parameters_json_schema,
            takes_ctx=False,
        )
        for td in defs
    ]


#: What a tool with no mock returns. A production preset registers tools the
#: probes never exercise (`ActivateSkill`, `RunZrbTask`); they are present so
#: the request carries their schema, and answering "unavailable" is honest
#: about an environment that genuinely has no skills or zrb tasks in it.
MISSING_STUB = "ERROR: not available in this environment."


def _guarded(name: str, fn, guard, rec):
    """Put the shipped repeat guard in front of a mock executor.

    Mirrors `SafeToolsetWrapper` in `agent/common.py`, which is what zrb
    actually ships: an identical call repeated back to back is *refused* rather
    than executed, and the refusal is phrased for the model to act on
    (ADR-0057). Without this the harness measures an agent with no loop guard —
    which, since the guard landed, is not an agent zrb sends.

    The refused call is still recorded. The model issued it, and a scorer
    counting attempts should see every attempt; hiding refusals would let a
    looping run score as a tidy one.
    """

    def executor(**kwargs) -> str:
        if guard is not None and guard.check(name, kwargs):
            rec(name, **kwargs)
            return REPEAT_REFUSAL.format(tool=name, n=_repeat_limit() + 1)
        try:
            return fn(**kwargs)
        except Exception as exc:  # noqa: BLE001 - a bad argument is the model's
            # `Tool.from_schema` passes arguments through unvalidated, so a wrong
            # type reaches the mock and raises. Production turns that into text
            # the model can recover from (ADR-0057) rather than ending the run;
            # propagating it would drop the cell and lose the arm its worst runs.
            return f"ERROR: {name}: {type(exc).__name__}: {exc}"

    return executor


#: Kept close to the production wording in `agent/common.py` without importing
#: it: that string is built for a live session and names configuration a probe
#: has no way to change. What has to match is the *shape* — refused, why it
#: cannot have changed, and the two ways out.
REPEAT_REFUSAL = (
    "[SYSTEM SUGGESTION] You have now called {tool} with identical arguments "
    "{n} times in a row, with nothing in between. The result cannot have "
    "changed, so this call was not run. Either the work is already done — in "
    "which case report it and stop — or the approach is not working, in which "
    "case do something different: read the file you are editing to see its "
    "actual current contents, widen the search, or tell the user what you "
    "tried and what blocked you."
)


def _repeat_limit() -> int:
    """The shipped consecutive-identical-call limit."""
    from zrb.config.config import CFG

    return CFG.LLM_MAX_REPEATED_TOOL_CALLS


async def run_cell(
    model_id: str,
    system_prompt: str,
    probe,
    providers,
    defs=None,
    guarded: bool = False,
    request_limit: int = DEFAULT_REQUEST_LIMIT,
) -> dict:
    """One probe against one prompt arm. Never raises; failures are recorded.

    An ``openai:``, ``google:`` or ``deepseek:`` prefix selects that hosted
    provider; an explicit ``ollama:`` prefix strips to the bare tag, and
    anything else is a literal ollama tag on its own (colons and all — ollama
    tags use ``:`` as their own version separator, e.g. ``gemma4:31b-cloud``).
    The prefix is also what zrb's own profile resolution reads, so the id
    here is the id zrb would classify.

    ``defs`` and ``guarded`` select the tool surface and whether the shipped
    repeat guard is in the path; both are recorded on the row, because a cell
    run under one is not comparable to the same cell run under another.
    """
    # lazy: heavy third-party
    from pydantic_ai import Agent
    from pydantic_ai.exceptions import UsageLimitExceeded
    from pydantic_ai.models.google import GoogleModel
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.usage import RunUsage

    # lazy: transitively heavy via internal — zrb.config pulls the CFG tree in
    from zrb.llm.agent.run.repetition import RepeatedCallDetector

    prefix, _, rest = model_id.partition(":")
    if prefix in ("openai", "google", "deepseek", "ollama"):
        bare = rest
    else:
        prefix, bare = "ollama", model_id
    provider = providers[prefix]
    model = (
        GoogleModel(bare, provider=provider)
        if prefix == "google"
        else OpenAIChatModel(bare, provider=provider)
    )

    trace, turn = Trace(), [0]
    guard = RepeatedCallDetector(limit=_repeat_limit()) if guarded else None
    agent = Agent(
        model,
        system_prompt=system_prompt,
        tools=build_tools(trace, turn, defs, guard),
    )
    started = time.time()
    looped = False
    # Accumulated in place by the agent, so it survives the exception below.
    # Reading usage off the *result* loses precisely the cells worth costing — a
    # looping run raises instead of returning — which is survivorship bias that
    # flatters whichever arm loops most.
    usage = RunUsage()
    try:
        result = await _run_with_backoff(
            agent, probe, usage, trace, turn, request_limit
        )
        trace.text = result.output or ""
        _retag_turns(result, trace)
        error = None
    except UsageLimitExceeded:
        # Running out of requests is the loop the Recovery rule exists to
        # prevent, so it is an outcome to score, not an error to discard.
        # Turns are made distinct so a looping run cannot be credited with
        # batching it never demonstrated.
        for i, call in enumerate(trace.calls):
            call.turn = i
        looped, error = True, None
    except Exception as exc:  # noqa: BLE001 - a failed cell is data, not a crash
        error = f"{type(exc).__name__}: {exc}"[:300]
    return {
        "passed": None if error else bool(probe.score(trace)),
        "looped": looped,
        "error": error,
        "seconds": round(time.time() - started, 2),
        "calls": [c.tool for c in trace.calls],
        "text": trace.text[:600],
        **_usage(usage),
    }


#: Attempts against a rate-limited provider, and the base of the exponential
#: backoff between them (seconds): 4, 8, 16, 32, 64.
RATE_LIMIT_ATTEMPTS = 6
RATE_LIMIT_BACKOFF = 2.0

#: Substrings that mean the 429 is an *exhausted account*, not fast pacing.
#: Both arrive as 429 and only the body separates them, so without this the
#: backoff spends five sleeps per cell — up to two minutes — re-asking a
#: question whose answer cannot change until someone tops up the account.
QUOTA_MARKERS = ("insufficient_quota", "exceeded your current quota", "billing")


async def _run_with_backoff(agent, probe, usage, trace, turn, request_limit):
    """Run the probe, retrying while the provider is rate-limiting us.

    A pacing 429 is a statement about request timing, not about the prompt under
    test, and recording it as a cell outcome corrupts the grid twice over: the
    cell holds no measurement, and ``done_keys`` then treats it as complete so a
    resume never revisits it. One sweep at concurrency 8 came back 646/1232
    rate-limited and looked, to every downstream reader, like finished data.

    A quota 429 is the opposite: retrying cannot help, and the useful behaviour
    is to surface it on the first cell so the sweep can be abandoned rather than
    ground through. The trace is cleared between attempts so a partially
    executed run cannot contribute phantom tool calls to the one that succeeds.
    """
    # lazy: heavy third-party
    from pydantic_ai.exceptions import ModelHTTPError
    from pydantic_ai.usage import UsageLimits

    for attempt in range(RATE_LIMIT_ATTEMPTS):
        try:
            return await agent.run(
                probe.message,
                usage_limits=UsageLimits(request_limit=request_limit),
                usage=usage,
            )
        except ModelHTTPError as exc:
            spent = any(m in str(exc).lower() for m in QUOTA_MARKERS)
            last = attempt == RATE_LIMIT_ATTEMPTS - 1
            if exc.status_code != 429 or spent or last:
                raise
            trace.calls.clear()
            trace.text = ""
            turn[0] = 0
            await asyncio.sleep(RATE_LIMIT_BACKOFF ** (attempt + 2))
    raise AssertionError("unreachable")  # pragma: no cover


#: What a cell records about its own cost. Named here so a provider that omits
#: one of them still produces a row of the same shape.
USAGE_FIELDS = ("input_tokens", "output_tokens", "cache_read_tokens", "requests")


def _usage(usage) -> dict:
    """Tokens the cell actually spent, from the accumulator the agent wrote into.

    ``measure.py`` sizes a prompt *statically*; this is what a run costs, and
    the two come apart badly. A prompt 1,000 tokens lighter that talks the model
    into twice the turns is more expensive, not less, and until this was
    recorded the harness had no way to see that — every cost claim came from
    static composition size, which is a per-request figure being used to argue
    about per-task spend.

    No ``try`` here. The first version read ``result.usage()`` — a property, not
    a method — which raised ``TypeError`` into a bare ``except`` and recorded 64
    cells with no cost data and no complaint. A missing usage *field* reads as
    0; a wrong *access* should fail on the first cell, not on the analysis.
    """
    return {name: getattr(usage, name, 0) or 0 for name in USAGE_FIELDS}


def _retag_turns(result, trace: Trace) -> None:
    """Assign each recorded call the index of the response it was part of.

    Calls are recorded in execution order, which matches the order tool-call
    parts appear across responses, so a positional zip is exact.
    """
    from pydantic_ai.messages import ModelResponse

    ordered = [
        i
        for i, msg in enumerate(
            m for m in result.all_messages() if isinstance(m, ModelResponse)
        )
        for part in msg.parts
        if part.part_kind == "tool-call"
    ]
    for call, idx in zip(trace.calls, ordered):
        call.turn = idx


def cells(only_experiment: str | None, only_model: str | None) -> list[dict]:
    """The full grid. Reps follow the plan: 2 for the core claims, 1 elsewhere."""
    oc, canary = opencode_arms(), canary_arms()
    ladder = ["zrb-full", "zrb-minimal"]
    ablation = ["zrb-full-no-persona", "zrb-full-no-examples"]

    grid: list[dict] = []
    for model in MODELS:
        if only_model and model != only_model:
            continue
        for arm in ladder:
            for probe in PROBES:
                for rep in range(2):
                    grid.append(
                        {
                            "experiment": "X1",
                            "model": model,
                            "arm": arm,
                            "probe": probe.name,
                            "rep": rep,
                        }
                    )
        for arm in canary:
            for rep in range(4):
                grid.append(
                    {
                        "experiment": "X2",
                        "model": model,
                        "arm": arm,
                        "probe": CANARY_PROBE.name,
                        "rep": rep,
                    }
                )
        for arm in ["zrb-full", *oc]:
            for name in X3_PROBES:
                grid.append(
                    {
                        "experiment": "X3",
                        "model": model,
                        "arm": arm,
                        "probe": name,
                        "rep": 0,
                    }
                )
        for arm in ablation:
            for probe in PROBES:
                grid.append(
                    {
                        "experiment": "X4",
                        "model": model,
                        "arm": arm,
                        "probe": probe.name,
                        "rep": 0,
                    }
                )
        # X5: rules `full` has and `minimal` lacks. Its own experiment rather
        # than more X1 probes, so the published X1 numbers stay comparable.
        for arm in ladder:
            for probe in HARD_PROBES:
                for rep in range(2):
                    grid.append(
                        {
                            "experiment": "X5",
                            "model": model,
                            "arm": arm,
                            "probe": probe.name,
                            "rep": rep,
                        }
                    )
    if only_experiment:
        grid = [c for c in grid if c["experiment"] == only_experiment]
    return grid


def key(cell: dict) -> tuple:
    """What makes a cell the same cell, for resume and for skipping.

    ``prompt_sha`` is the one that bites. An arm name is stable across every edit
    to the prompt behind it, so a resume matching on the name alone treats a row
    measured against yesterday's `zrb-full` as a row measured against today's —
    silently, and precisely when a prompt edit is the thing being measured. Rows
    written before this field existed carry no fingerprint, so they take a
    sentinel that compares equal to nothing: a re-run costs money, an
    undetectable mixture costs the whole conclusion.

    ``tools`` and ``guard`` are part of it for the same reason — they are
    conditions of the run, not of the arm, and leaving them out would let a resume
    read 610 thin, unguarded rows as a finished grid. Those two are *defaulted*
    rather than sentinelled, because a row predating them was demonstrably run at
    the old setting; a prompt leaves no such trace in the row.
    """
    return (
        cell["experiment"],
        cell["model"],
        cell["arm"],
        cell["probe"],
        cell["rep"],
        cell.get("tools", "thin"),
        bool(cell.get("guard", False)),
        int(cell.get("request_limit") or LEGACY_REQUEST_LIMIT),
        cell.get("prompt_sha") or _UNFINGERPRINTED,
        cell.get("harness_sha") or _UNFINGERPRINTED,
    )


#: Never equal to any real fingerprint, so a row that predates this field can
#: never satisfy a cell waiting to run. ``object()`` rather than a string so no
#: future fingerprint scheme can collide with it by accident.
_UNFINGERPRINTED = object()


def harness_sha() -> str:
    """Fingerprint of the world and the scorers, for the same reason as prompts.

    ``prompt_sha`` closes the hole on the treatment side; this closes it on the
    measurement side. A mock filesystem or a scorer can change what a row means
    while every other field stays identical, and nothing in the row would say so.

    Hashed over the parsed syntax with docstrings stripped, so comments and
    prose do not invalidate a corpus that cost real money to collect. Everything
    that can change a *result* still does: a regex, a threshold, a fixture, a
    scorer's control flow. It stays blunt on that side deliberately — re-running
    costs money, and a corpus that silently blends two harnesses costs the
    conclusion.
    """
    import hashlib
    import inspect

    import probes

    src = inspect.getsource(build_tools) + inspect.getsource(probes)
    return hashlib.sha256(_semantic(src).encode()).hexdigest()[:12]


def _semantic(src: str) -> str:
    """*src* as syntax, with docstrings dropped. Comments never reach the AST."""
    import ast

    tree = ast.parse(textwrap.dedent(src))
    holders = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    for node in ast.walk(tree):
        if not isinstance(node, holders):
            continue
        head = node.body[0] if node.body else None
        if (
            isinstance(head, ast.Expr)
            and isinstance(head.value, ast.Constant)
            and isinstance(head.value.value, str)
        ):
            node.body = node.body[1:] or [ast.Pass()]
    return ast.dump(tree)


def prompt_sha(text: str) -> str:
    """Fingerprint of the exact prompt text an arm ships right now.

    Twelve hex characters: enough that a collision is not a thing that happens,
    short enough to read in a row and grep for in a corpus.
    """
    import hashlib

    return hashlib.sha256(text.encode()).hexdigest()[:12]


def done_keys() -> set[tuple]:
    """Tolerates a record glued to the next with no newline (crash mid-write)."""
    if not RESULTS.exists():
        return set()
    text = RESULTS.read_text()
    decoder, seen, i, n = json.JSONDecoder(), set(), 0, len(text)
    while i < n:
        if text[i].isspace():
            i += 1
            continue
        obj, i = decoder.raw_decode(text, i)
        seen.add(key(obj))
    return seen


def _resolve_surfaces(choice: str) -> dict:
    """Tool definitions per preset, for whichever surface was asked for.

    Returned keyed by preset even when every arm gets the same one, so the call
    site stays a single lookup instead of branching on the surface again.
    ``thin`` maps to ``None``, which is what `build_tools` reads as "generate
    the one-line surface from the mocks' own signatures".
    """
    if choice == "thin":
        return {"full": None, "minimal": None}
    if choice == "prod":
        shared = tool_defs("full")
        return {"full": shared, "minimal": shared}
    return {preset: tool_defs(preset) for preset in ("full", "minimal")}


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--experiment")
    ap.add_argument("--model")
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument(
        "--probe", action="append", help="restrict to these probes (repeatable)"
    )
    ap.add_argument(
        "--arm", action="append", help="restrict to these arms (repeatable)"
    )
    ap.add_argument(
        "--out",
        help="write to this file instead of runs.jsonl; "
        "use for a re-measurement after a prompt edit",
    )
    ap.add_argument(
        "--tools",
        choices=SURFACES,
        default="prod",
        help="tool surface: thin one-liners, the shipped `full` definitions "
        "(default), or each arm's own preset surface",
    )
    ap.add_argument(
        "--request-limit",
        type=int,
        default=DEFAULT_REQUEST_LIMIT,
        help=f"requests a cell may spend before it counts as non-convergent "
        f"(default {DEFAULT_REQUEST_LIMIT}; zrb ships 300)",
    )
    ap.add_argument(
        "--no-guard",
        action="store_true",
        help="run without the repeated-tool-call guard zrb ships; the "
        "before-side of measuring what that guard is worth",
    )
    args = ap.parse_args()

    global RESULTS
    if args.out:
        RESULTS = RESULTS.parent / args.out

    # Both of these read `ZRB_LLM_PROFILE`, so they are resolved once, up
    # front, rather than interleaved per cell where the last writer would win.
    arms = {**zrb_arms(), **opencode_arms(), **canary_arms()}
    surfaces = _resolve_surfaces(args.tools)
    guarded = not args.no_guard

    # Stamped once, above the dry-run branch, because both paths have to ask
    # `key()` the same question; a second copy is where a new key field gets
    # forgotten. One fingerprint per arm, not per cell — every cell of an arm
    # sees the same text by construction.
    shas = {name: prompt_sha(text) for name, text in arms.items()}
    harness = harness_sha()
    stamped = [
        {
            **c,
            "tools": args.tools,
            "guard": guarded,
            "request_limit": args.request_limit,
            "prompt_sha": shas[c["arm"]],
            "harness_sha": harness,
        }
        for c in cells(args.experiment, args.model)
    ]

    if args.dry_run:
        # `thin` has no precomputed definitions — `build_tools` derives them
        # from the mocks' own signatures — so resolve them once here rather
        # than reporting the surface as empty.
        shown = {
            preset: (
                defs
                if defs is not None
                else [t.tool_def for t in build_tools(Trace(), [0])]
            )
            for preset, defs in surfaces.items()
        }
        for name, text in sorted(arms.items(), key=lambda kv: -len(kv[1])):
            defs = shown[ARM_PRESET.get(name, "full")]
            tool_ch = sum(
                len(td.description or "") + len(str(td.parameters_json_schema))
                for td in defs
            )
            print(
                f"{name:24s} {len(text):7,d} prompt ch"
                f"  + {len(defs):2d} tools ({tool_ch:6,d} ch)"
                f"  ~{(len(text) + tool_ch) // 4:6,d} tok"
            )
        # Counted against the settings this invocation would run under, not
        # against the file as a whole: reporting a thin, unguarded row as "done"
        # for a `prod` run is how a sweep gets skipped rather than resumed.
        done = done_keys()
        remaining = sum(1 for c in stamped if key(c) not in done)
        print(
            f"\ntools={args.tools} guard={'on' if guarded else 'off'}\n"
            f"{len(stamped):,} cells ({len(stamped) - remaining:,} already done at "
            f"these settings, {remaining:,} to run)"
        )
        return

    from pydantic_ai.providers.google import GoogleProvider
    from pydantic_ai.providers.openai import OpenAIProvider

    providers = {
        "ollama": OpenAIProvider(
            base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
            api_key=os.environ.get("OLLAMA_API_KEY", "ollama"),
        ),
        "openai": OpenAIProvider(api_key=os.environ["OPENAI_API_KEY"]),
        # Reads GOOGLE_API_KEY, then GEMINI_API_KEY, from the environment and
        # raises a clear error when neither is set.
        "google": GoogleProvider(),
        "deepseek": OpenAIProvider(
            base_url="https://api.deepseek.com/v1",
            api_key=os.environ["DEEPSEEK_API_KEY"],
        ),
    }
    todo = [
        c
        for c in stamped
        if key(c) not in done_keys()
        and (not args.probe or c["probe"] in args.probe)
        and (not args.arm or c["arm"] in args.arm)
    ]
    print(f"{len(todo):,} cells to run (tools={args.tools}, guard={guarded})")

    sem = asyncio.Semaphore(args.concurrency)
    lock = asyncio.Lock()
    counter = [0]
    RESULTS.parent.mkdir(parents=True, exist_ok=True)

    async def one(cell: dict) -> None:
        probe = (
            CANARY_PROBE
            if cell["probe"] == CANARY_PROBE.name
            else PROBES_BY_NAME[cell["probe"]]
        )
        defs = surfaces[ARM_PRESET.get(cell["arm"], "full")]
        async with sem:
            outcome = await run_cell(
                cell["model"],
                arms[cell["arm"]],
                probe,
                providers,
                defs=defs,
                guarded=guarded,
                request_limit=args.request_limit,
            )
        async with lock:
            counter[0] += 1
            with RESULTS.open("a") as fh:
                fh.write(json.dumps({**cell, **outcome}) + "\n")
            mark = {True: "PASS", False: "fail", None: "ERR "}[outcome["passed"]]
            print(
                f"[{counter[0]:4d}/{len(todo)}] {mark} {cell['model']:24s} "
                f"{cell['arm']:22s} {cell['probe']}"
            )

    await asyncio.gather(*(one(c) for c in todo))


if __name__ == "__main__":
    asyncio.run(main())
