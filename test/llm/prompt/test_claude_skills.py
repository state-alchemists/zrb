"""Tests for `build_skill_replacements` — the skill-catalogue placeholders."""

from zrb.llm.prompt.claude import build_skill_replacements
from zrb.llm.skill.manager import Skill, SkillManager


# ---------------------------------------------------------------------------
# build_skill_replacements tests
# ---------------------------------------------------------------------------


def _scan(tmp_path):
    sm = SkillManager(root_dir=str(tmp_path))
    sm.scan(search_dirs=[tmp_path])
    return sm


def test_build_skill_replacements_returns_all_placeholders(tmp_path):
    """All three placeholders are always present, even with no skills."""
    sm = SkillManager(root_dir=str(tmp_path))
    sm.scan(search_dirs=[])

    r = build_skill_replacements(sm)

    assert set(r) == {"CORE_SKILLS", "AVAILABLE_SKILLS", "PREACTIVATED_SKILLS"}


def test_build_skill_replacements_lists_available_skill(tmp_path):
    """A non-core model-invocable skill lands in AVAILABLE_SKILLS."""
    (tmp_path / "test.skill.md").write_text(
        "---\nname: test-skill\ndescription: A test skill\n---\n# Content"
    )

    r = build_skill_replacements(_scan(tmp_path))

    assert "test-skill" in r["AVAILABLE_SKILLS"]
    assert "A test skill" in r["AVAILABLE_SKILLS"]
    assert "test-skill" not in r["CORE_SKILLS"]


def test_build_skill_replacements_separates_core_from_other(tmp_path):
    """A skill under a core_skills/ dir is classified as core, not available."""
    core_dir = tmp_path / "core_skills" / "core-thing"
    core_dir.mkdir(parents=True)
    (core_dir / "SKILL.md").write_text(
        "---\nname: core-thing\ndescription: A core skill\n---\n# Content"
    )
    (tmp_path / "other.skill.md").write_text(
        "---\nname: other\ndescription: Another skill\n---\n# Content"
    )

    r = build_skill_replacements(_scan(tmp_path))

    assert "core-thing" in r["CORE_SKILLS"]
    assert "core-thing" not in r["AVAILABLE_SKILLS"]
    assert "other" in r["AVAILABLE_SKILLS"]


def test_build_skill_replacements_available_is_empty_when_none_registered(tmp_path):
    """No available skills means no section at all — heading included.

    A stock install has none: every built-in utility skill under
    ``llm_plugin/skills/`` is ``disable-model-invocation`` (a slash command the
    user reaches, not an agent skill), so this used to render an "Available
    Skills" heading over the words "(none registered)". Paying for a heading that
    introduces nothing teaches the model that catalogue entries are decorative.
    """
    sm = SkillManager(root_dir=str(tmp_path))
    sm.scan(search_dirs=[])

    r = build_skill_replacements(sm)

    assert r["AVAILABLE_SKILLS"] == ""


def test_build_skill_replacements_available_carries_its_own_heading(tmp_path):
    """The heading rides with the list so it can disappear with it."""
    (tmp_path / "test.skill.md").write_text(
        "---\nname: test-skill\ndescription: A test skill\n---\n# Content"
    )

    r = build_skill_replacements(_scan(tmp_path))

    assert "### Available Skills" in r["AVAILABLE_SKILLS"]
    assert "test-skill" in r["AVAILABLE_SKILLS"]


def test_build_skill_replacements_active_skill_content_loaded(tmp_path):
    """Active skills are rendered with their full content."""
    (tmp_path / "deep.skill.md").write_text(
        "---\nname: deep-skill\ndescription: Deep skill\n---\nDeep skill body text"
    )

    r = build_skill_replacements(_scan(tmp_path), active_skills=["deep-skill"])

    assert "Deep skill body text" in r["PREACTIVATED_SKILLS"]
    assert "Active Skills (Fully Loaded)" in r["PREACTIVATED_SKILLS"]


def test_build_skill_replacements_active_skill_excluded_from_lists(tmp_path):
    """An active skill is not also advertised in the catalogue lists."""
    (tmp_path / "act.skill.md").write_text(
        "---\nname: act\ndescription: Active one\n---\nbody"
    )

    r = build_skill_replacements(_scan(tmp_path), active_skills=["act"])

    assert "act" not in r["AVAILABLE_SKILLS"]


def test_build_skill_replacements_no_active_skills_empty(tmp_path):
    """PREACTIVATED_SKILLS is empty when nothing is pre-activated."""
    (tmp_path / "test.skill.md").write_text(
        "---\nname: test-skill\ndescription: A test skill\n---\n# Content"
    )

    r = build_skill_replacements(_scan(tmp_path))

    assert r["PREACTIVATED_SKILLS"] == ""


def test_build_skill_replacements_missing_active_skill_does_not_crash(tmp_path):
    """Requesting a non-existent active skill is ignored, not fatal."""
    sm = SkillManager(root_dir=str(tmp_path))
    sm.scan(search_dirs=[tmp_path])

    r = build_skill_replacements(sm, active_skills=["nonexistent-skill"])

    assert r["PREACTIVATED_SKILLS"] == ""


def test_build_skill_replacements_skips_non_invocable(tmp_path):
    """Skills with disable-model-invocation are not listed."""
    (tmp_path / "hidden.skill.md").write_text(
        "---\nname: hidden\ndescription: Hidden\n"
        "disable-model-invocation: true\n---\n# Content"
    )

    r = build_skill_replacements(_scan(tmp_path))

    assert "hidden" not in r["AVAILABLE_SKILLS"]


def _many_skill_manager(tmp_path, count: int) -> SkillManager:
    """A SkillManager with *count* programmatically-registered skills."""
    sm = SkillManager(root_dir=str(tmp_path))
    sm.scan(search_dirs=[])
    for i in range(count):
        sm.add_skill(
            Skill(
                name=f"skill-{i:02d}",
                path=str(tmp_path),
                description=f"Description {i:02d}",
            )
        )
    return sm


def test_build_skill_replacements_truncates_available_skills(tmp_path, monkeypatch):
    """A catalogue over the cap lists only the first entries, with a pointer
    to SearchSkill for the rest — the overflow stays reachable on demand."""
    monkeypatch.setenv("ZRB_LLM_MAX_SKILLS_IN_CATALOG", "10")

    r = build_skill_replacements(_many_skill_manager(tmp_path, 15))

    assert "skill-09" in r["AVAILABLE_SKILLS"]
    assert "skill-10" not in r["AVAILABLE_SKILLS"]
    assert "5 more" in r["AVAILABLE_SKILLS"]
    assert "SearchSkill" in r["AVAILABLE_SKILLS"]


def test_build_skill_replacements_does_not_truncate_under_cap(tmp_path, monkeypatch):
    """A small catalogue stays complete — no truncation note."""
    monkeypatch.setenv("ZRB_LLM_MAX_SKILLS_IN_CATALOG", "10")

    r = build_skill_replacements(_many_skill_manager(tmp_path, 3))

    assert "skill-02" in r["AVAILABLE_SKILLS"]
    assert "more" not in r["AVAILABLE_SKILLS"]


def test_build_skill_replacements_cap_zero_is_unlimited(tmp_path, monkeypatch):
    """0 disables the cap: the whole catalogue is listed, no truncation note."""
    monkeypatch.setenv("ZRB_LLM_MAX_SKILLS_IN_CATALOG", "0")

    r = build_skill_replacements(_many_skill_manager(tmp_path, 15))

    assert "skill-14" in r["AVAILABLE_SKILLS"]
    assert "more" not in r["AVAILABLE_SKILLS"]


def test_build_skill_replacements_truncates_core_skills(tmp_path, monkeypatch):
    """Core methodologies are capped the same way."""
    monkeypatch.setenv("ZRB_LLM_MAX_SKILLS_IN_CATALOG", "2")
    for i in range(5):
        skill_dir = tmp_path / "core_skills" / f"core-{i}"
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(
            f"---\nname: core-{i}\ndescription: Core {i}\n---\n# body"
        )

    r = build_skill_replacements(_scan(tmp_path))

    assert "core-0" in r["CORE_SKILLS"]
    assert "core-1" in r["CORE_SKILLS"]
    assert "core-2" not in r["CORE_SKILLS"]
    assert "3 more" in r["CORE_SKILLS"]
    assert "SearchSkill" in r["CORE_SKILLS"]
