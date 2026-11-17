"""The `zrb chat` flags that decide one run instead of the deployment.

Each flag names a setting an environment variable and `zrb_init.py` already
own. The rule is the one `--sandbox` follows: an empty flag leaves the
deployment's value alone, a value overrides it for this run. A value is cast and
checked through `CFG`, exactly as `/set` casts it, so the flag and the command
refuse the same strings for the same reasons.

The write is process-wide, which for `zrb chat` is one session: the CLI runs one
conversation and exits. `zrb server` takes no such flag, so a web session is
never told what another one asked for.
"""

from __future__ import annotations

from zrb.config.config import CFG
from zrb.context.any_context import AnyContext
from zrb.llm.prompt.profile import PROFILES

#: input name → the setting it overrides, in the order `--help` lists them.
LAUNCH_SETTINGS: tuple[tuple[str, str], ...] = (
    ("voice", "LLM_VOICE"),
    ("volume", "LLM_SPEECH_VOLUME"),
    ("thinking", "LLM_THINKING"),
    ("profile", "LLM_PROFILE"),
    ("memory", "LLM_MEMORY_ENABLED"),
    ("self-review", "LLM_SELF_REVIEW_ENABLED"),
)

#: What a session may talk with. `auto` is the fourth name `LLM_PROFILE` reads.
PROFILE_NAMES = (*PROFILES, "auto")

#: `--judge`'s third value: a `safe` verdict resolves the approval instead of
#: printing above it. Two words, because the flag's subject (`judge`) supplies
#: who approves and this supplies what happens.
JUDGE_AUTO_APPROVE = "auto-approve"

#: Percentage of the voice's own level, the range `/volume` holds a level to.
MIN_VOLUME = 0
MAX_VOLUME = 200


def apply_launch_flags(ctx: AnyContext) -> None:
    """Write this run's flags into `CFG`, before the session and its hooks build.

    Late is too late for half of them: the speech and dictation presets resolve
    when the session starts, and the memory hooks decide at registration whether
    they join. `LLMChatTask` calls this at the top of a run for that reason.
    """
    for flag, name in LAUNCH_SETTINGS:
        raw = str(ctx.input.get(flag) or "").strip()
        if not raw:
            continue
        _apply_setting(name, raw)
    _apply_judge_flag(ctx)


def _apply_setting(name: str, raw: str) -> None:
    """Cast *raw* the way a read of *name* would, then keep it for this process."""
    if name == "LLM_PROFILE" and raw.lower() not in PROFILE_NAMES:
        raise ValueError(
            f"--profile {raw!r} is not one of: {', '.join(PROFILE_NAMES)}"
        )
    value = CFG.convert_setting_value(name, raw)
    if name == "LLM_SPEECH_VOLUME":
        value = _checked_volume(value)
    setattr(CFG, name, value)


def _checked_volume(level: object) -> int:
    """*level* as a volume, or a refusal naming the range.

    Clamped only at playback, so a mistyped flag would otherwise be read as a
    request for full volume with nothing said about it.
    """
    if not isinstance(level, int) or not MIN_VOLUME <= level <= MAX_VOLUME:
        raise ValueError(
            f"--volume {level} is out of range: speech volume is a percentage "
            f"of the voice's own level, {MIN_VOLUME}-{MAX_VOLUME}."
        )
    return level


def _apply_judge_flag(ctx: AnyContext) -> None:
    """`off`, `on` or `auto-approve`; the third one turns the judge on as well.

    Both halves are written because the second is meaningless without the
    first: a session that skips safe prompts still has to consult the judge to
    know which they are.
    """
    raw = str(ctx.input.get("judge") or "").strip().lower()
    if not raw:
        return
    if raw == JUDGE_AUTO_APPROVE:
        setattr(CFG, "LLM_SHELL_JUDGE_ENABLED", True)
        setattr(CFG, "LLM_SHELL_JUDGE_AUTO_APPROVE_ENABLED", True)
        return
    enabled = CFG.convert_setting_value("LLM_SHELL_JUDGE_ENABLED", raw)
    setattr(CFG, "LLM_SHELL_JUDGE_ENABLED", enabled)
