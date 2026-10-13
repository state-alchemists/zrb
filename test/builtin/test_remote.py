import json
from types import SimpleNamespace
from unittest import mock

import pytest

from zrb.builtin.remote import remote_check, remote_run
from zrb.context.shared_context import SharedContext
from zrb.remote.inventory import Host, Target, host_inventory, target_inventory
from zrb.remote.report import create_csv, create_markdown_table
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
    assert res == (
        "| Host | Remote Host | Status | Output |\n"
        "|---|---|---|---|\n"
        "| node1 | (local) | ✅ | hello |"
    )


@pytest.mark.asyncio
async def test_remote_run_renders_a_table_by_default():
    res = await remote_run.async_run(
        session=get_session(), kwargs=_kwargs(command="echo hello", format="table")
    )
    assert "node1" in res and "hello" in res and "Host" in res and "{" not in res


@pytest.mark.asyncio
async def test_remote_check_builds_host_by_target_matrix():
    res = await remote_check.async_run(
        session=get_session(), kwargs=_kwargs(target_labels="t")
    )
    assert res.splitlines()[0] == "| Host | Remote Host | closed<br>127.0.0.1:1 |"
    assert res.splitlines()[-1] == "| node1 | (local) | ❌ refused |"


@pytest.mark.asyncio
async def test_empty_inventories_raise_a_suggestion():
    for item in host_inventory.get_all():
        host_inventory.remove(item.name)
    with pytest.raises(ValueError, match="SYSTEM SUGGESTION"):
        await remote_run.async_run(
            session=get_session(), kwargs=_kwargs(host_labels="", command="true")
        )
    host_inventory.add(Host("node1", labels=["k8s"]))
    for item in target_inventory.get_all():
        target_inventory.remove(item.name)
    with pytest.raises(ValueError, match="SYSTEM SUGGESTION"):
        await remote_check.async_run(
            session=get_session(), kwargs=_kwargs(target_labels="")
        )


def test_markdown_table_escapes_pipes_and_newlines():
    assert create_markdown_table(["h"], [["a|b\nc"]]).endswith("| a\\|b<br>c |")


def test_label_inputs_offer_the_registered_labels_and_names():
    shared = SharedContext()
    html = [i for i in remote_run.inputs if i.name == "host-labels"][0].to_html(shared)
    assert '<option value="k8s"' in html and '<option value="node1"' in html


@pytest.mark.asyncio
async def test_a_host_name_selects_it():
    res = await remote_run.async_run(
        session=get_session(), kwargs=_kwargs(host_labels="other", command="echo x")
    )
    assert "| other | (local) | ✅ | x |" in res


@pytest.mark.asyncio
async def test_json_format_returns_raw_statuses():
    run = await remote_run.async_run(
        session=get_session(), kwargs=_kwargs(command="echo hi", format="json")
    )
    assert json.loads(run) == [
        {"host": "node1", "remote_host": None, "ok": True, "output": "hi"}
    ]
    check = await remote_check.async_run(
        session=get_session(), kwargs=_kwargs(target_labels="t", format="json")
    )
    assert json.loads(check) == [
        {
            "host": "node1",
            "remote_host": None,
            "targets": {"closed": "refused"},
            "target_addresses": {"closed": "127.0.0.1:1"},
        }
    ]


@pytest.mark.asyncio
async def test_csv_format_is_plain_and_includes_the_remote_host():
    host = Host("node1", labels=["k8s"], remote_host="10.0.0.1")
    run_result = SimpleNamespace(host=host, ok=True, output="a,b")
    check_result = SimpleNamespace(host=host, ok=True, output="refused")
    with (
        mock.patch("zrb.builtin.remote.copy_text", return_value=True),
        mock.patch(
            "zrb.builtin.remote.run_on_hosts",
            side_effect=[[run_result], [check_result]],
        ),
        mock.patch("zrb.builtin.remote.parse_probe_output", return_value=["refused"]),
    ):
        run = await remote_run.async_run(
            session=get_session(), kwargs=_kwargs(command="x", format="csv")
        )
        check = await remote_check.async_run(
            session=get_session(), kwargs=_kwargs(target_labels="t", format="csv")
        )
    assert run.splitlines() == [
        "Host,Remote Host,Status,Output",
        'node1,10.0.0.1,ok,"a,b"',
    ]
    assert check.splitlines() == [
        "Host,Remote Host,closed (127.0.0.1:1)",
        "node1,10.0.0.1,refused",
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("fmt", ["csv", "json", "markdown"])
async def test_machine_formats_are_copied_to_the_clipboard(fmt):
    with mock.patch("zrb.builtin.remote.copy_text", return_value=True) as copy:
        res = await remote_run.async_run(
            session=get_session(), kwargs=_kwargs(command="echo hi", format=fmt)
        )
    copy.assert_called_once_with(res)


@pytest.mark.asyncio
async def test_table_format_is_not_copied_and_clipboard_failure_is_tolerated():
    with mock.patch("zrb.builtin.remote.copy_text", return_value=False) as copy:
        await remote_run.async_run(
            session=get_session(), kwargs=_kwargs(command="echo hi", format="table")
        )
        copy.assert_not_called()
        res = await remote_run.async_run(
            session=get_session(), kwargs=_kwargs(command="echo hi", format="json")
        )
    assert json.loads(res)[0]["output"] == "hi"


def test_csv_neutralizes_spreadsheet_formulas():
    out = create_csv(["h"], [["=1+1"], ["+x"], ["-x"], ["@x"], ["safe"]])
    assert out.splitlines() == ["h", "'=1+1", "'+x", "'-x", "'@x", "safe"]


def test_target_address_redacts_url_credentials():
    target = Target("api", kind="http", url="https://alice:secret@example.com/health")
    assert target.get_address() == "https://***@example.com/health"
    assert target.get_url() == "https://alice:secret@example.com/health"
    assert Target("plain", kind="http", host="h").get_address() == "http://h:80/"
