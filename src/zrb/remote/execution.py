import asyncio
import os
import shlex
from collections.abc import Sequence
from dataclasses import dataclass

from zrb.cmd.command import resolve_shell, run_command
from zrb.cmd.remote import get_remote_cmd_script
from zrb.remote.inventory import Host, Target

# Trailing lines kept per stream and host, as `CmdTask` does.
MAX_OUTPUT_LINE = 1000

# Runs under plain `sh`, so a target host needs no bash, python or any one tool:
# TCP uses bash's /dev/tcp, else nc; HTTP uses curl. A missing tool is `n/a`.
# A failure is named by what the tool said: `refused` (host answered, nothing
# listens), `timeout` (no answer, usually a firewall), `dns` (name did not
# resolve), else plain `fail`.
# One scratch file holds every probe's stderr; a trap removes it when the script
# ends or is terminated by the host timeout, so repeated checks leave nothing.
# Without `mktemp` there is no scratch file (never a guessable /tmp name, which a
# local user could pre-create as a symlink) and a failure is a plain `fail`.
_PROBE_FUNCTIONS = r"""
PROBE_ERR=$(mktemp 2>/dev/null) || PROBE_ERR=
trap '[ -z "$PROBE_ERR" ] || rm -f "$PROBE_ERR"' EXIT
trap '[ -z "$PROBE_ERR" ] || rm -f "$PROBE_ERR"; exit 1' HUP INT TERM
classify_failure() {
  case "$1" in
    *[Rr]efused*) echo refused ;;
    *"timed out"*|*[Tt]imeout*) echo timeout ;;
    *"not known"*|*"name resolution"*|*"Unknown host"*|*"nodename nor servname"*|*"Could not resolve"*) echo dns ;;
    *) echo fail ;;
  esac
}
probe_tcp() {
  err=${PROBE_ERR:-/dev/null}
  : >"$err"
  if command -v bash >/dev/null 2>&1; then
    bash -c 'exec 3<>"/dev/tcp/$0/$1"' "$1" "$2" >/dev/null 2>"$err" &
    pid=$!
    (sleep 5; kill $pid) >/dev/null 2>&1 &
    killer=$!
    wait $pid
    rc=$?
    kill $killer >/dev/null 2>&1
    if [ $rc -eq 0 ]; then echo ok
    elif [ $rc -gt 128 ]; then echo timeout
    else classify_failure "$(cat "$err")"; fi
  elif command -v nc >/dev/null 2>&1; then
    if nc -vz -w 5 "$1" "$2" >"$err" 2>&1; then echo ok
    else classify_failure "$(cat "$err")"; fi
  else
    echo n/a
  fi
}
probe_http() {
  if command -v curl >/dev/null 2>&1; then
    err=${PROBE_ERR:-/dev/null}
  : >"$err"
    code=$(curl -sS -o /dev/null -m 5 -w '%{http_code}' "$1" 2>"$err")
    rc=$?
    if [ -n "$code" ] && [ "$code" != 000 ]; then echo "$code"
    elif [ $rc -eq 28 ]; then echo timeout
    elif [ $rc -eq 6 ]; then echo dns
    elif [ $rc -eq 7 ]; then
      # Newer curl words a refusal "Couldn't connect to server".
      case "$(cat "$err")" in *nreachable*|*"No route"*) echo fail ;; *) echo refused ;; esac
    else classify_failure "$(cat "$err")"; fi
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
    hosts: Sequence[Host],
    script: str,
    timeout: float = 60,
    concurrency: int = 10,
    posix_only: bool = False,
) -> list[HostResult]:
    """Run `script` on every host, at most `concurrency` at a time, in host order.

    `posix_only` runs a POSIX script locally under `sh` instead of the host's
    `shell`. A remote host always starts `ssh` under `sh`, whose quoting the
    command line uses; `Host.shell` applies only to a local, non-POSIX-only run.
    """
    if timeout <= 0:
        raise ValueError(f"timeout must be positive, got {timeout}")
    semaphore = asyncio.Semaphore(max(1, concurrency))

    async def run_one(host: Host) -> HostResult:
        async with semaphore:
            return await _run_on_host(host, script, timeout, posix_only)

    return list(await asyncio.gather(*(run_one(h) for h in hosts)))


async def _run_on_host(
    host: Host, script: str, timeout: float, posix_only: bool
) -> HostResult:
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
    use_sh = posix_only or host.remote_host is not None
    shell, flag = resolve_shell("sh" if use_sh else host.shell or "")
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
    """Script printing `<index> <status>` per target.

    Status is `ok`, an HTTP code, `refused`, `timeout`, `dns`, `fail` or `n/a`.
    """
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
