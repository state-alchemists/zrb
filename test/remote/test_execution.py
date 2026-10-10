import pytest

from zrb.remote.execution import (
    create_probe_script,
    parse_probe_output,
    run_on_hosts,
)
from zrb.remote.inventory import Host, Target


@pytest.mark.asyncio
async def test_run_on_hosts_runs_locally_in_order_and_reports_failure():
    hosts = [Host("one"), Host("two")]
    ok = await run_on_hosts(hosts, "echo hi", concurrency=1)
    assert [(r.host.name, r.ok, r.output) for r in ok] == [
        ("one", True, "hi"),
        ("two", True, "hi"),
    ]
    bad = await run_on_hosts(hosts[:1], "echo oops >&2; exit 3")
    assert not bad[0].ok and "oops" in bad[0].output


@pytest.mark.asyncio
async def test_run_on_hosts_reports_timeout_as_failure():
    (result,) = await run_on_hosts([Host("slow")], "sleep 5", timeout=0.2)
    assert not result.ok and "Timeout" in result.output


@pytest.mark.asyncio
async def test_probe_script_checks_a_closed_port_locally():
    targets = [Target("closed", host="127.0.0.1", port=1)]
    (result,) = await run_on_hosts([Host("l")], create_probe_script(targets))
    assert parse_probe_output(result.output, 1) == ["fail"]


def test_parse_probe_output_marks_missing_targets_as_error():
    assert parse_probe_output("0 ok\r\n2 200\njunk", 3) == ["ok", "error", "200"]


@pytest.mark.asyncio
async def test_run_on_hosts_rejects_a_non_positive_timeout():
    with pytest.raises(ValueError, match="timeout"):
        await run_on_hosts([Host("h")], "true", timeout=-1)
