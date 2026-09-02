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


def _singularize(plural: str) -> str:
    if plural.endswith("ies"):
        return plural[:-3] + "y"
    if plural.endswith("s"):
        return plural[:-1]
    return plural


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
