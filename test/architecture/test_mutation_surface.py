"""Guards a uniform mutation-verb surface across every collection (R5, R6, R7).

The dict literals below are the source of truth for what "uniform" means — a
new collection is added to the relevant dict in the same diff that adds the
collection.

Keyed collections get a reduced 3-verb minimum (`add_X`/`set_X`/`remove_X`)
rather than the full 5, because the query half (`get_X`/`get_Xs`) is not
actually uniform across the codebase and forcing it would be actively wrong
in two places: `SubAgentManager` already has `create_agent` (returns a
runtime agent), so a plain `get_agent` would collide in meaning with
`get_agent_definition`; and hooks are keyed by *event*, not by name, so there
is no `get_hook(name)` to require. See framework-conventions.md's "R7, two
specific cases" section and R6's own row for the reasoning.
"""

import importlib

ORDERED_COLLECTIONS = {
    "zrb.llm.tool.registry:tool_registry": [
        ("tool", "tools"),
        ("tool_factory", "tool_factories"),
        ("toolset_factory", "toolset_factories"),
    ],
    "zrb.llm.prompt.registry:prompt_registry": [("prompt", "prompts")],
    "zrb.builtin.llm.chat:llm_chat": [
        ("tool", "tools"),
        ("tool_factory", "tool_factories"),
        ("toolset", "toolsets"),
        ("toolset_factory", "toolset_factories"),
        ("history_processor", "history_processors"),
        ("trigger", "triggers"),
        ("custom_command", "custom_commands"),
        ("tool_policy", "tool_policies"),
        ("response_handler", "response_handlers"),
        ("argument_formatter", "argument_formatters"),
        ("ui", "uis"),
        ("ui_factory", "ui_factories"),
        ("approval_channel", "approval_channels"),
        ("hook_factory", "hook_factories"),
    ],
}

KEYED_COLLECTIONS = {
    "zrb.llm.skill.registry:skill_registry": [("skill", "skills")],
    "zrb.llm.agent.subagent.registry:sub_agent_registry": [("agent", "agents")],
    "zrb.llm.hook.registry:hook_registry": [("hook", "hooks")],
}

# Every component a user may replace (R8, Phase 4) — a single-value slot
# holding a *Manager/*Config/*Limiter or Any* ABC instance. A `list`/`dict`
# collection (even a settable one, like `ui_factories`) belongs to Phase 3's
# verb-set ratchet above, not here — see framework-conventions.md's R7 note
# on why those two stay settable properties instead of gaining a `set_X()`.
# Adding a slot means adding it here in the same diff.
SLOTS = {
    "zrb.builtin.llm.chat:llm_chat": [
        "prompt_manager",
        "hook_manager",
        "llm_limiter",
        "markdown_theme",
        "history_manager",
        "sandbox",
        "permissions",
        "ui_config",
        "model_getter",
        "model_renderer",
    ],
}


def _load(spec: str):
    module_path, attr = spec.split(":")
    return getattr(importlib.import_module(module_path), attr)


def _has_set(host, plural: str) -> bool:
    """"Replace wholesale" as either a `set_<plural>()` method or an already
    settable `<plural>` property (`ui_factories`, `approval_channels`) — R7
    keeps whichever one already existed rather than adding a second name for
    the same replace-wholesale operation."""
    if callable(getattr(host, f"set_{plural}", None)):
        return True
    prop = getattr(type(host), plural, None)
    return isinstance(prop, property) and prop.fset is not None


def test_every_ordered_collection_has_the_full_verb_set():
    violations = []
    for spec, stems in ORDERED_COLLECTIONS.items():
        host = _load(spec)
        for stem, plural in stems:
            for verb in (f"append_{stem}", f"prepend_{stem}", f"remove_{stem}"):
                if not callable(getattr(host, verb, None)):
                    violations.append(f"{spec} missing {verb} (R5)")
            if not _has_set(host, plural):
                violations.append(f"{spec} missing set_{plural} (R5)")
            if hasattr(host, f"add_{stem}"):
                violations.append(f"{spec} has add_{stem} — R5 forbids the alias")
    assert not violations, "\n".join(violations)


def test_every_keyed_collection_has_the_minimum_verb_set():
    violations = []
    for spec, stems in KEYED_COLLECTIONS.items():
        host = _load(spec)
        for stem, plural in stems:
            for verb in (f"add_{stem}", f"remove_{stem}"):
                if not callable(getattr(host, verb, None)):
                    violations.append(f"{spec} missing {verb} (R6)")
            if not callable(getattr(host, f"set_{plural}", None)):
                violations.append(f"{spec} missing set_{plural} (R6)")
            if hasattr(host, f"append_{stem}"):
                violations.append(f"{spec} has append_{stem} — R6 forbids the alias")
    assert not violations, "\n".join(violations)


# A setter typed against one of these is the exact regression R8 guards
# against — the surface degrading back to "no help from the type checker".
_BARE_ANY = {"Any", "typing.Any", "Any | None", "Optional[Any]"}


def test_every_declared_slot_is_settable_and_typed():
    """R8: every slot in SLOTS is a real settable property, typed as
    something more specific than `Any`.

    Deliberately reads the raw (unresolved) annotation string rather than
    calling `typing.get_type_hints()`: a couple of slot types (e.g.
    `rich.theme.Theme` on `markdown_theme`) are only imported under
    `TYPE_CHECKING` to stay import-cheap — resolving the forward reference
    for real would force that import just to run this test. The raw string
    is enough to catch the one thing this ratchet cares about.
    """
    violations = []
    for spec, slots in SLOTS.items():
        host = _load(spec)
        for slot in slots:
            prop = getattr(type(host), slot, None)
            if not isinstance(prop, property) or prop.fset is None:
                violations.append(f"{spec}.{slot} is not a settable property (R8)")
                continue
            annotation = prop.fset.__annotations__.get("value", "")
            if annotation in _BARE_ANY:
                violations.append(
                    f"{spec}.{slot}'s setter is typed Any — give it a real type (R8)"
                )
    assert not violations, "\n".join(violations)


def _singularize(plural: str) -> str:
    if plural.endswith("ies"):
        return plural[:-3] + "y"
    if plural.endswith("s"):
        return plural[:-1]
    return plural


# TODO(follow-up): web_auth_config is a genuine hybrid — real user-list
# storage plus auth callbacks, not a thin CFG.WEB_AUTH_* wrapper — so folding
# it into CFG is out of scope for Phase 6 (R12, ADR-0090/0091). Exempted here
# until that follow-up lands.
_R12_EXEMPT = {"web_auth_config"}


def test_there_is_exactly_one_configuration_object():
    """`CFG` is the only config object. A second one means a user has to guess."""
    import zrb

    offenders = [
        name
        for name in zrb.__all__
        if name.endswith("_config") and name != "CFG" and name not in _R12_EXEMPT
    ]
    assert not offenders, (
        f"{offenders} are exported alongside CFG. Scalars live on CFG "
        "(ADR-0021/0022); components live in registries or slots (ADR-0090). R12."
    )


def test_no_concept_is_reachable_by_two_names():
    """R7: a settable property `p` never coexists with `set_p`/`set_<singular(p)>`."""
    hosts = {spec: _load(spec) for spec in {**ORDERED_COLLECTIONS, **KEYED_COLLECTIONS}}
    hosts["zrb.builtin.llm.chat:llm_chat"] = _load("zrb.builtin.llm.chat:llm_chat")
    violations = []
    for spec, host in hosts.items():
        cls = type(host)
        for name in dir(cls):
            attr = getattr(cls, name, None)
            if not isinstance(attr, property) or attr.fset is None:
                continue
            singular = _singularize(name)
            for alias in (f"set_{name}", f"set_{singular}"):
                if alias == f"set_{name}" and alias == f"set_{singular}":
                    continue
                if hasattr(host, alias) and callable(getattr(host, alias)):
                    violations.append(
                        f"{spec}: both settable property {name!r} and {alias}() exist (R7)"
                    )
    assert not violations, "\n".join(violations)
