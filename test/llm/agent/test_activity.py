from zrb.llm.agent.activity import AgentActivityRegistry, agent_activity_registry


def test_start_tracks_agent_as_active():
    reg = AgentActivityRegistry()
    reg.start("id1", "researcher")
    active = reg.active()
    assert len(active) == 1
    assert active[0].agent_id == "id1"
    assert active[0].name == "researcher"
    assert active[0].last_line == ""


def test_update_sets_last_nonempty_line():
    reg = AgentActivityRegistry()
    reg.start("id1", "researcher")
    reg.update("id1", "reading foo.py\n\n")
    assert reg.active()[0].last_line == "reading foo.py"
    reg.update("id1", "line a\nline b\n")
    assert reg.active()[0].last_line == "line b"


def test_update_unknown_agent_is_noop():
    reg = AgentActivityRegistry()
    reg.update("missing", "anything")  # must not raise
    assert reg.active() == []


def test_finish_drops_agent():
    reg = AgentActivityRegistry()
    reg.start("id1", "researcher")
    reg.finish("id1")
    assert reg.active() == []
    reg.finish("id1")  # idempotent


def test_snapshot_is_serializable():
    reg = AgentActivityRegistry()
    reg.start("id1", "researcher", task="map the codebase")
    reg.update("id1", "working")
    snap = reg.snapshot()
    assert snap == [
        {
            "agent_id": "id1",
            "name": "researcher",
            "ordinal": 1,
            "task": "map the codebase",
            "last_line": "working",
        }
    ]


def test_start_returns_incrementing_ordinal():
    reg = AgentActivityRegistry()
    assert reg.start("a", "x") == 1
    assert reg.start("b", "y") == 2
    assert [a.ordinal for a in reg.active()] == [1, 2]


def test_ordinal_resets_when_batch_drains():
    reg = AgentActivityRegistry()
    reg.start("a", "x")
    reg.start("b", "y")
    reg.finish("a")
    reg.finish("b")  # registry now empty -> counter resets
    assert reg.start("c", "z") == 1


def test_clear_removes_all():
    reg = AgentActivityRegistry()
    reg.start("a", "x")
    reg.start("b", "y")
    reg.clear()
    assert reg.active() == []


def test_buffered_ui_feeds_registry():
    from zrb.llm.tool.delegate import BufferedUI

    class _Sink:
        def append_to_output(self, *values, **kwargs):
            pass

    agent_activity_registry.clear()
    ui = BufferedUI(_Sink())
    ui.set_activity_id("agent-x")
    agent_activity_registry.start("agent-x", "worker")
    ui.append_to_output("doing the thing")
    assert agent_activity_registry.active()[0].last_line == "doing the thing"
    ui.stream_to_parent("status update")
    assert agent_activity_registry.active()[0].last_line == "status update"
    agent_activity_registry.clear()


# ── Session scoping: a process hosting multiple sessions
# (the web runner) must not bleed one session's running sub-agents into
# another's activity panel/listing. ──


def test_sessions_do_not_bleed_into_each_others_active_list():
    reg = AgentActivityRegistry()
    reg.start("a", "researcher", session_id="session-1")
    reg.start("b", "reviewer", session_id="session-2")

    assert [a.agent_id for a in reg.active(session_id="session-1")] == ["a"]
    assert [a.agent_id for a in reg.active(session_id="session-2")] == ["b"]


def test_default_session_id_is_its_own_bucket():
    """The default (empty) session_id is the single-session/CLI case — still
    isolated from any explicitly-named session."""
    reg = AgentActivityRegistry()
    reg.start("a", "researcher")  # no session_id -> default bucket
    reg.start("b", "reviewer", session_id="session-2")

    assert [a.agent_id for a in reg.active()] == ["a"]
    assert [a.agent_id for a in reg.active(session_id="session-2")] == ["b"]


def test_ordinal_numbering_is_independent_per_session():
    reg = AgentActivityRegistry()
    assert reg.start("a", "x", session_id="s1") == 1
    assert reg.start("b", "y", session_id="s2") == 1  # independent counter
    assert reg.start("c", "z", session_id="s1") == 2


def test_update_only_affects_the_matching_session():
    reg = AgentActivityRegistry()
    reg.start("a", "x", session_id="s1")
    reg.start("a", "x", session_id="s2")  # same agent_id, different session

    reg.update("a", "progress in s1", session_id="s1")

    assert reg.active(session_id="s1")[0].last_line == "progress in s1"
    assert reg.active(session_id="s2")[0].last_line == ""


def test_finish_only_drops_from_the_matching_session():
    reg = AgentActivityRegistry()
    reg.start("a", "x", session_id="s1")
    reg.start("a", "x", session_id="s2")

    reg.finish("a", session_id="s1")

    assert reg.active(session_id="s1") == []
    assert [a.agent_id for a in reg.active(session_id="s2")] == ["a"]


def test_snapshot_is_scoped_per_session():
    reg = AgentActivityRegistry()
    reg.start("a", "x", task="s1 work", session_id="s1")
    reg.start("b", "y", task="s2 work", session_id="s2")

    snap = reg.snapshot(session_id="s1")

    assert len(snap) == 1
    assert snap[0]["agent_id"] == "a"
    assert snap[0]["task"] == "s1 work"


def test_clear_one_session_leaves_others_intact():
    reg = AgentActivityRegistry()
    reg.start("a", "x", session_id="s1")
    reg.start("b", "y", session_id="s2")

    reg.clear(session_id="s1")

    assert reg.active(session_id="s1") == []
    assert [a.agent_id for a in reg.active(session_id="s2")] == ["b"]


def test_clear_without_session_id_clears_every_session():
    reg = AgentActivityRegistry()
    reg.start("a", "x", session_id="s1")
    reg.start("b", "y", session_id="s2")

    reg.clear()

    assert reg.active(session_id="s1") == []
    assert reg.active(session_id="s2") == []
