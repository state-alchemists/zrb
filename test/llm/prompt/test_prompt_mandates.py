"""Tests for the shipped markdown prompt files."""

import pytest

from zrb.config.config import CFG
from zrb.llm.prompt.profile import PROFILES
from zrb.llm.prompt.prompt import get_prompt


def test_persona_renders_the_assistant_name():
    prompt = get_prompt("persona", ASSISTANT_NAME="CustomAssistant")
    assert "CustomAssistant" in prompt
    assert "{ASSISTANT_NAME}" not in prompt


@pytest.mark.parametrize("section", ["principle", "workflow", "example"])
def test_core_markdown_sections_are_non_empty(section):
    assert get_prompt(section).strip()


def test_workflow_carries_evidence_and_safety_guidance():
    prompt = get_prompt("workflow").lower()
    assert "verify" in prompt
    assert "cite" in prompt
    assert "untrusted" in prompt


def test_workflow_explains_parallel_calls_skill_activation_and_journal_follow_up():
    prompt = get_prompt("workflow")
    assert "Batch independent tool calls" in prompt
    assert "ActivateSkill" in prompt
    assert "every matching one" in prompt
    assert "complete final answer" in prompt


def test_example_models_a_multi_methodology_task():
    prompt = get_prompt("example")
    assert "core-design" in prompt
    assert "core-writing" in prompt
    assert "same response" in prompt


@pytest.mark.parametrize("profile", PROFILES)
def test_each_profile_resolves_its_specific_adjustment(profile):
    prompt = get_prompt("profile", profile=profile)
    assert "# Operating Profile" in prompt


def test_unknown_prompt_is_empty():
    assert get_prompt("not-a-prompt-section") == ""
