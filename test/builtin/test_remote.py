from unittest import mock

import pytest

from zrb.builtin.remote import remote_check, remote_run
from zrb.context.shared_context import SharedContext
from zrb.remote.inventory import Host, Target, host_inventory, target_inventory
from zrb.remote.report import create_markdown_table
from zrb.session.session import Session


def get_session():
    return Session(shared_ctx=SharedContext(), state_logger=mock.MagicMock())


@pytest.fixture(autouse=True)
def inventories():
    hosts, targets = host_inventory.get_all(), target_inventory.get_all()
    host_inventory.add(Host("node1", labels=["k8s"]), Host("other"))
    target_inventory.add(Target("closed", host="127.0.0.1", port=1, labels=["t"]))
    yield
    for item in host_inventory.get_all():
        host_inventory.remove(item.name)
    for item in target_inventory.get_all():
        target_inventory.remove(item.name)
    host_inventory.add(*hosts)
    target_inventory.add(*targets)


def _kwargs(**extra):
    base = {
        "host_labels": "k8s",
        "format": "markdown",
        "concurrency": 2,
        "timeout": 30,
    }
    return {**base, **extra}


@pytest.mark.asyncio
async def test_remote_run_returns_markdown_table_for_selected_hosts():
    res = await remote_run.async_run(
        session=get_session(), kwargs=_kwargs(command="echo hello")
    )
    assert res == "| Host | Status | Output |\n|---|---|---|\n| node1 | ✅ | hello |"


@pytest.mark.asyncio
async def test_remote_run_renders_a_table_by_default():
    res = await remote_run.async_run(
        session=get_session(), kwargs=_kwargs(command="echo hello", format="table")
    )
    assert "node1" in res and "hello" in res and "┃" in res


@pytest.mark.asyncio
async def test_remote_check_builds_host_by_target_matrix():
    res = await remote_check.async_run(
        session=get_session(), kwargs=_kwargs(target_labels="t")
    )
    assert res.splitlines()[-1] == "| node1 | ❌ fail |"


@pytest.mark.asyncio
async def test_empty_inventories_raise_a_suggestion():
    for item in host_inventory.get_all():
        host_inventory.remove(item.name)
    with pytest.raises(ValueError, match="SYSTEM SUGGESTION"):
        await remote_run.async_run(
            session=get_session(), kwargs=_kwargs(host_labels="", command="true")
        )
    host_inventory.add(Host("node1"))
    for item in target_inventory.get_all():
        target_inventory.remove(item.name)
    with pytest.raises(ValueError, match="SYSTEM SUGGESTION"):
        await remote_check.async_run(
            session=get_session(), kwargs=_kwargs(target_labels="")
        )


def test_markdown_table_escapes_pipes_and_newlines():
    assert create_markdown_table(["h"], [["a|b\nc"]]).endswith("| a\\|b<br>c |")


def test_label_inputs_offer_the_registered_labels():
    shared = SharedContext()
    html = [i for i in remote_run.inputs if i.name == "host-labels"][0].to_html(shared)
    assert '<option value="k8s"' in html
