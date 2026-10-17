"""Every recipe in docs/llm/recipes.md does what the page says.

Each marked snippet runs in a fresh interpreter with a scratch HOME and
working directory, followed by a check of its effect.
"""

import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
RECIPES = REPO_ROOT / "docs" / "llm" / "recipes.md"
_SNIPPET = re.compile(r"<!-- recipe: ([a-z-]+) -->\n```[a-z]*\n(.*?)```", re.DOTALL)


def _get_snippets() -> dict[str, str]:
    return dict(_SNIPPET.findall(RECIPES.read_text(encoding="utf-8")))


def _run(script: str, cwd: Path) -> None:
    env = {
        key: value for key, value in os.environ.items() if not key.startswith("ZRB_")
    }
    env["HOME"] = str(cwd)
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_every_marked_recipe_is_checked():
    assert set(_get_snippets()) == {
        "add-tool",
        "persona",
        "append-prompt",
        "skill",
        "agent",
        "own-chat",
        "emotion",
    }


def test_add_tool(tmp_path):
    check = """
from zrb.llm.permission import Capability, tool_capability
tool = next(t for t in llm_chat.tools if getattr(t, "__name__", "") == "lookup_ticket")
assert tool_capability(tool) == Capability.READ
"""
    _run(_get_snippets()["add-tool"] + check, tmp_path)


def test_persona(tmp_path):
    _write(
        tmp_path / ".zrb" / "llm" / "prompt" / "persona.md", _get_snippets()["persona"]
    )
    _run(
        "from zrb.llm.prompt.prompt import get_prompt\n"
        'assert "Ops Buddy" in get_prompt("persona")\n',
        tmp_path,
    )


def test_append_prompt(tmp_path):
    check = 'assert any("Kubernetes" in p for p in prompt_registry.get_prompts())\n'
    _run(_get_snippets()["append-prompt"] + check, tmp_path)


def test_skill(tmp_path):
    _write(
        tmp_path / ".zrb" / "skills" / "release-notes" / "SKILL.md",
        _get_snippets()["skill"],
    )
    _run(
        "from zrb.llm.skill.manager import skill_manager\n"
        'skill = skill_manager.get_skill("release-notes")\n'
        "assert skill is not None\n"
        'assert "git log" in skill_manager.get_skill_content("release-notes")\n',
        tmp_path,
    )


def test_agent(tmp_path):
    _write(
        tmp_path / ".zrb" / "agents" / "sql-reviewer.agent.md",
        _get_snippets()["agent"],
    )
    _run(
        "from zrb.llm.subagent.manager import sub_agent_manager\n"
        'assert sub_agent_manager.get_agent_definition("sql-reviewer") is not None\n',
        tmp_path,
    )


def test_own_chat(tmp_path):
    check = textwrap.dedent("""
        from zrb.runner.cli import cli as root
        assert root.get_task_by_alias("ops-chat") is ops_chat
        assert ops_chat.tools or ops_chat.tool_factories
        assert [i.name for i in ops_chat.inputs] == ["message"]
        """)
    _run(_get_snippets()["own-chat"] + check, tmp_path)


def test_emotion(tmp_path):
    check = textwrap.dedent("""
        from zrb.llm.dictation.config import DictationConfig
        from zrb.llm.speech.config import SpeechConfig
        dictation, speech = DictationConfig().resolve(), SpeechConfig().resolve()
        assert CFG.LLM_EMOTION_ENABLED
        assert dictation.detect_emotion and dictation.mode == "hands_free"
        assert dictation.backend == "sensevoice"
        assert speech.enabled and speech.backend == "pocket"
        assert speech.emotion_voices["sad"].endswith("sad.wav")
        """)
    _run(_get_snippets()["emotion"] + check, tmp_path)
