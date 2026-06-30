from zrb.llm.agent.activity import AgentActivityRegistry, agent_activity_registry


def test_start_tracks_agent_as_active():
    reg = AgentActivityRegistry()
    reg.start("id1", "researcher")
    active = reg.active()
    assert len(active) == 1
    assert active[0].agent_id == "id1"
    assert active[0].name == "researcher"
    assert active[0].status == "running"
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
            "task": "map the codebase",
            "status": "running",
            "last_line": "working",
        }
    ]


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
