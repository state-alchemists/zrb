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
from treatments import canary_arms, opencode_arms, zrb_arms

RESULTS = Path(__file__).parent / "results" / "runs.jsonl"

# Eight models: six frontier/mid families through ollama, plus two hosted
# small-tier OpenAI models. zrb routes every hosted small-tier label to `lean`
# (only a local prefix or a declared <=4B reaches `minimal`), so the two
# `openai:` entries are `lean` tested against the class it was written for.
# `minimal`'s own target class stays unrepresented — see README "Limitations".
MODELS = [
    "gemma4:31b-cloud",  # Google    — smallest declared size available
    "deepseek-v4-flash:cloud",  # DeepSeek  — fast tier
    "deepseek-v4-pro:cloud",  # DeepSeek  — strong tier, same family
    "kimi-k2.6:cloud",  # Moonshot  — opencode ships a kimi.txt
    "glm-5.2:cloud",  # Zhipu
    "mistral-large-3:675b-cloud",  # Mistral — non-reasoning
    "openai:gpt-4o-mini",  # OpenAI    — weak arm; zrb resolves it to `lean`
    "openai:gpt-4.1-nano",  # OpenAI    — weak arm; zrb resolves it to `lean`
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


def build_tools(trace: Trace, turn: "list[int]"):
    """Mock tools over WORLD. `turn` is a one-element cell holding the index of
    the model response currently being executed, so batching can be measured."""
    # lazy: pydantic_ai is heavy and only needed once a run actually starts
    from pydantic_ai import Tool

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
        if path in WORLD:
            return path
        candidate = "/project/" + path.rsplit("/", 1)[-1]
        return candidate if candidate in WORLD else path

    def Read(path: str) -> str:
        """Read a file from disk."""
        rec("Read", path=path)
        target = resolve(path)
        return WORLD.get(target, f"ERROR: {path}: no such file or directory")

    def Write(path: str, content: str) -> str:
        """Write a whole new file."""
        rec("Write", path=path, bytes=len(content))
        return f"Wrote {path}."

    def Edit(path: str, old_string: str, new_string: str) -> str:
        """Replace a string inside an existing file."""
        rec("Edit", path=path, old=old_string, new=new_string)
        if resolve(path) not in WORLD:
            return f"ERROR: {path}: no such file or directory"
        return f"Edited {path}."

    def Glob(pattern: str) -> str:
        """Find files by name pattern."""
        rec("Glob", pattern=pattern)
        stem = pattern.replace("*", "").replace("**", "").strip("/")
        hits = [p for p in WORLD if stem and stem in p]
        return "\n".join(hits) if hits else "No files matched."

    def Grep(pattern: str) -> str:
        """Search for text inside files."""
        rec("Grep", pattern=pattern)
        hits = [
            f"{p}: {ln}"
            for p, body in WORLD.items()
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
                for p in WORLD
                if p.startswith(base + "/")
            }
        )
        if kids:
            return "\n".join(kids)
        # A root-ish path resolves to the project root for the same reason
        # `resolve` exists: the announced cwd is not where the world lives.
        if base in ("/", ".", os.getcwd(), str(Path.cwd()), "/project"):
            return "\n".join(
                sorted({p[len("/project/") :].split("/")[0] for p in WORLD})
            )
        return f"ERROR: {path}: no such directory"

    def RM(path: str) -> str:
        """Delete a file."""
        rec("RM", path=path)
        return f"Deleted {path}."

    def MV(source: str, destination: str) -> str:
        """Move or rename a file."""
        rec("MV", source=source, destination=destination)
        return f"Moved {source} to {destination}."

    def Shell(command: str) -> str:
        """Run a shell command."""
        rec("Shell", command=command)
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
                bodies = [WORLD[resolve(p)] for p in paths if resolve(p) in WORLD]
                if not bodies:
                    return "wc: no such file"
                return "\n".join(
                    f"{len(b.splitlines()):8d} {p}" for p, b in zip(paths, bodies)
                )
            paths = [w.strip("'\"") for w in command.split() if "/" in w]
            if verbs[0] in ("cat", "head", "tail"):
                bodies = [WORLD[resolve(p)] for p in paths if resolve(p) in WORLD]
                return "".join(bodies) or "(no output)"
            roots = paths or ["/project"]
            hits = sorted(
                p for p in WORLD if any(p.startswith(r.rstrip("/")) for r in roots)
            )
            return "\n".join(hits) or "(no output)"
        if "make" in command:
            return BUILD_ERROR
        if "pytest" in command or "test" in command:
            return "1 passed in 0.04s"
        return "(no output)"

    # One-line docstrings, so an arm measures the *prompt*. The production
    # schemas are 39% of the real instruction budget and are not varied here —
    # see ADR-0058 for why that surface has no known slack.
    tools = [
        Tool(f, name=f.__name__, takes_ctx=False)
        for f in (Read, Write, Edit, Glob, Grep, LS, RM, MV, Shell)
    ]

    def make_stub(name: str, reply: str):
        def stub(**kwargs) -> str:
            rec(name, **kwargs)
            return reply

        stub.__name__ = name
        stub.__doc__ = f"{name} tool."
        return stub

    tools += [
        Tool(make_stub(n, r), name=n, takes_ctx=False) for n, r in STUB_TOOLS.items()
    ]
    return tools


async def run_cell(model_id: str, system_prompt: str, probe, providers) -> dict:
    """One probe against one prompt arm. Never raises; failures are recorded.

    An ``openai:`` prefix selects the hosted provider; anything else goes to the
    ollama endpoint. The prefix is also what zrb's own profile resolution reads,
    so the id here is the id zrb would classify.
    """
    # lazy: heavy third-party
    from pydantic_ai import Agent
    from pydantic_ai.exceptions import UsageLimitExceeded
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.usage import UsageLimits

    which, _, bare = (
        model_id.rpartition(":")
        if model_id.startswith("openai:")
        else ("ollama", "", model_id)
    )
    provider = providers[which]

    trace, turn = Trace(), [0]
    agent = Agent(
        OpenAIChatModel(bare, provider=provider),
        system_prompt=system_prompt,
        tools=build_tools(trace, turn),
    )
    started = time.time()
    looped = False
    try:
        result = await agent.run(
            probe.message, usage_limits=UsageLimits(request_limit=12)
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
    }


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
    ladder = ["zrb-full", "zrb-lean", "zrb-minimal"]
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
    return (cell["experiment"], cell["model"], cell["arm"], cell["probe"], cell["rep"])


def done_keys() -> set[tuple]:
    if not RESULTS.exists():
        return set()
    seen = set()
    for line in RESULTS.read_text().splitlines():
        if line.strip():
            seen.add(key(json.loads(line)))
    return seen


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
    args = ap.parse_args()

    global RESULTS
    if args.out:
        RESULTS = RESULTS.parent / args.out

    arms = {**zrb_arms(), **opencode_arms(), **canary_arms()}
    if args.dry_run:
        for name, text in sorted(arms.items(), key=lambda kv: -len(kv[1])):
            print(f"{name:24s} {len(text):7,d} chars  ~{len(text) // 4:6,d} tok")
        print(
            f"\n{len(cells(args.experiment, args.model)):,} cells "
            f"({len(done_keys()):,} already done)"
        )
        return

    from pydantic_ai.providers.openai import OpenAIProvider

    providers = {
        "ollama": OpenAIProvider(
            base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
            api_key=os.environ.get("OLLAMA_API_KEY", "ollama"),
        ),
        "openai": OpenAIProvider(api_key=os.environ["OPENAI_API_KEY"]),
    }
    todo = [
        c
        for c in cells(args.experiment, args.model)
        if key(c) not in done_keys()
        and (not args.probe or c["probe"] in args.probe)
        and (not args.arm or c["arm"] in args.arm)
    ]
    print(f"{len(todo):,} cells to run")

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
        async with sem:
            outcome = await run_cell(cell["model"], arms[cell["arm"]], probe, providers)
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
