import socket
import sys
import time

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


@pytest.mark.asyncio
async def test_failed_run_keeps_stdout_and_stderr_apart():
    (result,) = await run_on_hosts([Host("h")], "printf out; printf err >&2; exit 1")
    assert result.output == "out\nerr"


@pytest.mark.asyncio
async def test_output_is_bounded_to_the_trailing_lines():
    (result,) = await run_on_hosts([Host("h")], "seq 1 5000")
    lines = result.output.splitlines()
    assert len(lines) <= 1001 and lines[-1] == "5000"


@pytest.mark.asyncio
@pytest.mark.skipif(
    sys.platform != "linux", reason="needs Linux's full-backlog SYN drop"
)
async def test_probe_of_a_stalled_connect_fails_within_the_probe_limit():
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(0)
    port = server.getsockname()[1]
    fillers = []
    for _ in range(4):
        filler = socket.socket()
        filler.setblocking(False)
        filler.connect_ex(("127.0.0.1", port))
        fillers.append(filler)
    targets = [Target("stalled", host="127.0.0.1", port=port)]
    start = time.monotonic()
    try:
        (result,) = await run_on_hosts([Host("l")], create_probe_script(targets))
    finally:
        for sock in [server, *fillers]:
            sock.close()
    assert parse_probe_output(result.output, 1) == ["fail"]
    assert 4 < time.monotonic() - start < 15


@pytest.mark.asyncio
async def test_posix_only_ignores_the_host_shell_and_run_honors_it():
    host = Host("w", shell="definitely-not-a-shell")
    (probe,) = await run_on_hosts([host], "echo hi", posix_only=True)
    assert probe.ok and probe.output == "hi"
    (run,) = await run_on_hosts([host], "echo hi")
    assert not run.ok
