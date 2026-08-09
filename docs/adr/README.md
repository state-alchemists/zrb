🔖 [Documentation Home](../../README.md)

# Architecture Decision Records

This directory records **why** zrb is built the way it is. Every record
describes a decision **that is currently in force**, with the alternatives that
were rejected and why.

## How to read an entry

Every ADR has the same shape:

- **Status** — normally `Accepted`.
- **Context** — the forces and the problem. Where a decision replaced an
  earlier attempt, the attempt and the evidence against it are part of the
  context, because that is what makes the decision legible.
- **Decision** — what was chosen, concretely.
- **Consequences** — what it buys and what it costs.
- **Alternatives rejected** — each with the reason. This section is the point
  of the record; a decision without its discarded options is just documentation.
- **Where it lives** — the files that implement it.

## How to add one

Record a decision as an ADR when it is **non-trivial** (a reasonable developer
could pick differently), **consequential** (it affects other parts of the
system or how users interact with it), and **persistent** (meant to last, not a
quick hack). One decision per record. Create `docs/adr/adr-NNNN.md` with the
next free number, and add a row to the index below under the relevant theme.

**When a decision changes, rewrite the record that owns it.** This log is
maintained as a description of the system as it stands, not as an append-only
history — a chain of "refines ADR-X, narrows ADR-Y, superseded by ADR-Z" makes
a reader reconstruct the current state from four documents. The superseded
approach belongs in the surviving record's Context or Alternatives, where it
still explains the decision. Git history and the changelog hold the
chronology.

Delete a record when its decision no longer applies anywhere — do not leave a
tombstone.

## Index

### Foundations

- **ADR-0001** — [Pure-Python task definitions, no YAML or DSL](adr-0001.md)
- **ADR-0002** — [Program against `Any*` interfaces, not concrete types](adr-0002.md)
- **ADR-0003** — [Async-first execution engine](adr-0003.md)
- **ADR-0004** — [Ambient state travels in `ContextVar`s](adr-0004.md)
- **ADR-0005** — [String properties render at execution time](adr-0005.md)

### Task model

- **ADR-0006** — [DAG dependencies declared with `>>` and `<<`](adr-0006.md)
- **ADR-0007** — [Specialized task classes over one generic type](adr-0007.md)
- **ADR-0008** — [`@make_task` alongside direct instantiation](adr-0008.md)
- **ADR-0009** — [Inputs and Envs are first-class objects](adr-0009.md)
- **ADR-0010** — [Hierarchical `zrb_init.py` discovery, explicit registration](adr-0010.md)
- **ADR-0011** — [Retry, fallback and successor are tasks](adr-0011.md)
- **ADR-0012** — [Readiness checks are concurrent, task-based probes](adr-0012.md)
- **ADR-0013** — [`execute_condition` skips rather than branches](adr-0013.md)
- **ADR-0014** — [Triggers and the Scheduler are daemon tasks](adr-0014.md)
- **ADR-0015** — [An explicit task lifecycle state machine](adr-0015.md)
- **ADR-0016** — [Capture the declaration site for error attribution](adr-0016.md)
- **ADR-0017** — [Cancellation is re-raised after cleanup](adr-0017.md)

### State and data flow

- **ADR-0018** — [Three-tier context: SharedContext, Session, Context](adr-0018.md)
- **ADR-0019** — [XCom is a per-task FIFO queue with callbacks](adr-0019.md)
- **ADR-0020** — [`DotDict` for attribute-style access](adr-0020.md)

### Configuration

- **ADR-0021** — [`CFG` is one singleton from domain mixins, accessed flat](adr-0021.md)
- **ADR-0022** — [`EnvField` descriptor instead of hand-written properties](adr-0022.md)
- **ADR-0023** — [Resolution order: env, `default_factory`, attribute default](adr-0023.md)
- **ADR-0024** — [Config reads `os.environ` only](adr-0024.md)
- **ADR-0025** — [White-labeling through `_ZRB_ENV_PREFIX` and `ROOT_GROUP_NAME`](adr-0025.md)
- **ADR-0026** — [Boolean config naming: verb-first vs `_ENABLED`](adr-0026.md)
- **ADR-0027** — [Semantic style names and one `ZRB_THEME`](adr-0027.md)

### Runners, packaging and code conventions

- **ADR-0028** — [One task definition, multiple runners](adr-0028.md)
- **ADR-0029** — [FastAPI and Uvicorn for the web runner](adr-0029.md)
- **ADR-0030** — [Nested CLI groups](adr-0030.md)
- **ADR-0031** — [Batteries-included builtin tasks, behind one toggle](adr-0031.md)
- **ADR-0032** — [`Scaffolder` for template-based generation](adr-0032.md)
- **ADR-0033** — [One distribution with disciplined lazy imports](adr-0033.md)
- **ADR-0034** — [Test discipline: ≥90%, public API only, F-only lint](adr-0034.md)
- **ADR-0035** — [Compose from parts on a shared `self`; name the part after its host](adr-0035.md)

### LLM runtime

- **ADR-0036** — [pydantic-ai as the agent framework](adr-0036.md)
- **ADR-0037** — [Provider-agnostic, multi-vendor LLM support](adr-0037.md)
- **ADR-0038** — [Model capabilities are a deny-list; the prompt states the default](adr-0038.md)
- **ADR-0039** — [Stream errors are classified; each class gets a one-shot fix](adr-0039.md)
- **ADR-0040** — [Run-loop guards for corrupted history and degenerate output](adr-0040.md)
- **ADR-0041** — [zrb owns history, with two-tier summarization](adr-0041.md)
- **ADR-0042** — [Keep the cached prefix byte-stable](adr-0042.md)
- **ADR-0043** — [A tool result reaches the model once, via `return_value`](adr-0043.md)

### Prompt

- **ADR-0044** — [Ordered sections; custom sections are config-positioned](adr-0044.md)
- **ADR-0045** — [A rule lives where it is enforced](adr-0045.md)
- **ADR-0046** — [Every section reads whole on its own; one Priority Order](adr-0046.md)
- **ADR-0047** — [Home-level docs are user guidance, not project rules](adr-0047.md)
- **ADR-0048** — [Untrusted-data framing travels with the tool result](adr-0048.md)
- **ADR-0049** — [A profile is a preset over sections, phrasing and tool surface](adr-0049.md)
- **ADR-0050** — [The prompt states the risky runtime state, never its absence](adr-0050.md)
- **ADR-0051** — [Capability and profile are keyed differently and are not merged](adr-0051.md)

### Skills, agents and the journal

- **ADR-0052** — [Skills and agents are discovered from directories](adr-0052.md)
- **ADR-0053** — [Claude-compatible skills; catalogue from the live scan](adr-0053.md)
- **ADR-0054** — [Built-in plugin split into core-skills, skills, agents](adr-0054.md)
- **ADR-0055** — [The journal is a markdown graph that only tools write](adr-0055.md)

### Tools and safety

- **ADR-0056** — [Tools are plain functions with PascalCase names](adr-0056.md)
- **ADR-0057** — [A tool exception becomes text with `[SYSTEM SUGGESTION]`](adr-0057.md)
- **ADR-0058** — [Tool-definition weight is managed by count, not prose](adr-0058.md)
- **ADR-0059** — [Tool output is capped twice: per tool, then globally](adr-0059.md)
- **ADR-0060** — [Tools carry a capability tag](adr-0060.md)
- **ADR-0061** — [Permissions are an ordered ruleset, first match wins](adr-0061.md)
- **ADR-0062** — [One approval chain: permission policy, tool policy, yolo](adr-0062.md)
- **ADR-0063** — [Plan mode is a permission preset](adr-0063.md)
- **ADR-0064** — [Advertised tool options are permission-filtered](adr-0064.md)
- **ADR-0065** — [Opt-in two-layer filesystem sandbox](adr-0065.md)
- **ADR-0066** — [`Shell` is the only shell tool; background is a flag](adr-0066.md)
- **ADR-0067** — [MCP servers are first-class tool sources](adr-0067.md)

### Delegation and concurrency

- **ADR-0068** — [Delegation: envelope, context-shaped criteria, fan-out](adr-0068.md)
- **ADR-0069** — [Background work inherits permissions and can be waited on](adr-0069.md)
- **ADR-0070** — [`BufferedUI` and a confirmation queue](adr-0070.md)

### Hooks and the task API

- **ADR-0071** — [Lifecycle hooks, Claude-compatible, control protocol included](adr-0071.md)
- **ADR-0072** — [`LLMTask` and `LLMChatTask` expose the same knobs](adr-0072.md)

### Interactive UI

- **ADR-0073** — [Todo progress reaches the user through a side channel](adr-0073.md)
- **ADR-0074** — [`ask_user_choice` with a text fallback](adr-0074.md)
- **ADR-0075** — [Shift+Tab cycles the mode, with a Termux fallback](adr-0075.md)
- **ADR-0076** — [Voice dictation as an opt-in UI input method](adr-0076.md)

🔖 [Documentation Home](../../README.md)
