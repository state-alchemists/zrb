import asyncio
import os
import shlex
from collections.abc import Sequence
from dataclasses import dataclass

from zrb.remote.inventory import Host, Target
from zrb.util.cmd.command import resolve_shell, run_command
from zrb.util.cmd.remote import get_remote_cmd_script

# Trailing lines kept per stream and host, as `CmdTask` does.
MAX_OUTPUT_LINE = 1000

# Runs under plain `sh`, so a target host needs no bash, python or any one tool:
# TCP uses bash's /dev/tcp, else nc; HTTP uses curl. A missing tool is `n/a`.
_PROBE_FUNCTIONS = r"""
probe_tcp() {
  if command -v bash >/dev/null 2>&1; then
    bash -c 'exec 3<>"/dev/tcp/$0/$1"' "$1" "$2" >/dev/null 2>&1 &
    pid=$!
    (sleep 5; kill $pid) >/dev/null 2>&1 &
    killer=$!
    if wait $pid; then echo ok; else echo fail; fi
    kill $killer >/dev/null 2>&1
  elif command -v nc >/dev/null 2>&1; then
    nc -z -w 5 "$1" "$2" >/dev/null 2>&1 && echo ok || echo fail
  else
    echo n/a
  fi
}
probe_http() {
  if command -v curl >/dev/null 2>&1; then
    code=$(curl -s -o /dev/null -m 5 -w '%{http_code}' "$1" 2>/dev/null)
    if [ -z "$code" ] || [ "$code" = 000 ]; then echo fail; else echo "$code"; fi
  else
    echo n/a
  fi
}
"""


@dataclass(frozen=True)
class HostResult:
    host: Host
    ok: bool
    output: str


async def run_on_hosts(
    hosts: Sequence[Host], script: str, timeout: float = 60, concurrency: int = 10
) -> list[HostResult]:
    """Run `script` on every host, at most `concurrency` at a time, in host order."""
    if timeout <= 0:
        raise ValueError(f"timeout must be positive, got {timeout}")
    semaphore = asyncio.Semaphore(max(1, concurrency))

    async def run_one(host: Host) -> HostResult:
        async with semaphore:
            return await _run_on_host(host, script, timeout)

    return list(await asyncio.gather(*(run_one(h) for h in hosts)))


async def _run_on_host(host: Host, script: str, timeout: float) -> HostResult:
    if host.cwd:
        script = f"cd {shlex.quote(host.cwd)} && {script}"
    env_map = None
    if host.remote_host is not None:
        script = get_remote_cmd_script(
            f"sh -c {shlex.quote(script)}",
            host=host.remote_host,
            port=host.remote_port,
            user=host.remote_user,
            use_password=host.remote_password != "",
            ssh_key=host.remote_ssh_key,
            tty=False,
        )
        if host.remote_password != "":
            env_map = {**os.environ, "SSHPASS": host.remote_password}
    shell, flag = resolve_shell(host.shell or "")
    try:
        result, return_code = await run_command(
            [shell, flag, script],
            env_map=env_map,
            print_method=lambda *_, **__: None,
            timeout=timeout,
            max_output_line=MAX_OUTPUT_LINE,
            max_error_line=MAX_OUTPUT_LINE,
        )
    except (TimeoutError, OSError) as e:
        return HostResult(host, False, f"{type(e).__name__}: {e}".strip())
    streams = [result.output] if return_code == 0 else [result.output, result.error]
    output = "\n".join(text for text in streams if text)
    return HostResult(host, return_code == 0, output.replace("\r", "").strip())


def create_probe_script(targets: Sequence[Target]) -> str:
    """Script printing `<index> <status>` per target; status is ok, an HTTP code, fail or n/a."""
    lines = [_PROBE_FUNCTIONS]
    for i, target in enumerate(targets):
        if target.kind == "http":
            probe = f"probe_http {shlex.quote(target.get_url())}"
        else:
            probe = f"probe_tcp {shlex.quote(target.host)} {target.port}"
        lines.append(f'echo "{i} $({probe})"')
    return "\n".join(lines)


def parse_probe_output(output: str, count: int) -> list[str]:
    """Statuses by target index; a target the host never reported is `error`."""
    statuses = ["error"] * count
    for line in output.splitlines():
        index, _, status = line.strip().partition(" ")
        if index.isdigit() and int(index) < count and status:
            statuses[int(index)] = status
    return statuses
