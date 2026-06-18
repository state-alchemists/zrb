#!/usr/bin/env python3
"""Read-only Kubernetes workload triage (portable, no shell required).

Gathers in one pass the evidence you usually collect by hand when a pod is
crashing/restarting/OOMKilled: status, scheduling & probe events, the CRASHED
container's logs (--previous), current logs, live resource usage, and the
state/exit-reason lines from `describe`.

READ-ONLY: it never edits, scales, deletes, or restarts anything; it only
shells out to `kubectl get/describe/logs/top/events`.

Target forms:
  <pod-name>          a single pod
  deploy/<name>       all pods of a deployment (resolved via its selector)
  <key>=<value>       a label selector (e.g. app=checkout)

Usage:
  python k8s-triage.py <target> [namespace]      # namespace defaults to "default"
"""

import json
import shutil
import subprocess
import sys

# describe(1) is verbose; keep only the lines that carry the diagnosis.
_DESCRIBE_KEYS = (
    "state",
    "reason",
    "exit code",
    "restart count",
    "oomkilled",
    "last state",
    "message",
    "liveness",
    "readiness",
    "events",
    "warning",
    "back-off",
    "backoff",
)


def _kubectl(ns, *args):
    """Run `kubectl -n <ns> <args>`; return (returncode, stdout, stderr)."""
    try:
        proc = subprocess.run(
            ["kubectl", "-n", ns, *args], capture_output=True, text=True
        )
    except (FileNotFoundError, OSError) as exc:
        return 1, "", str(exc)
    return proc.returncode, proc.stdout, proc.stderr


def _section(title):
    print(f"\n========== {title} ==========")


def _is_selector(target):
    return "=" in target and "/" not in target


def _resolve_pods(ns, target):
    """Return a list of `pod/<name>` references for the target."""
    if target.startswith(("deploy/", "deployment/")):
        rc, out, _ = _kubectl(
            ns, "get", target, "-o", "jsonpath={.spec.selector.matchLabels}"
        )
        if rc != 0 or not out.strip():
            return []
        try:
            labels = json.loads(out)
        except json.JSONDecodeError:
            return []
        selector = ",".join(f"{k}={v}" for k, v in labels.items())
        rc, out, _ = _kubectl(ns, "get", "pods", "-l", selector, "-o", "name")
        return out.split() if rc == 0 else []
    if _is_selector(target):
        rc, out, _ = _kubectl(ns, "get", "pods", "-l", target, "-o", "name")
        return out.split() if rc == 0 else []
    return [f"pod/{target}"]


def _print_overview(ns, target):
    if target.startswith(("deploy/", "deployment/")):
        for spec in (target, "pods"):
            _, out, _ = _kubectl(ns, "get", spec, "-o", "wide")
            print(out, end="")
    elif _is_selector(target):
        _, out, _ = _kubectl(ns, "get", "pods", "-l", target, "-o", "wide")
        print(out, end="")
    else:
        _, out, _ = _kubectl(ns, "get", "pod", target, "-o", "wide")
        print(out, end="")


def _triage_pod(ns, pod):
    name = pod.split("/", 1)[-1]
    _section(f"DESCRIBE — {name} (state / exit reason / probes / events)")
    rc, out, _ = _kubectl(ns, "describe", pod)
    if rc == 0:
        hits = [
            ln
            for ln in out.splitlines()
            if any(key in ln.lower() for key in _DESCRIBE_KEYS)
        ]
        print("\n".join(hits) if hits else "\n".join(out.splitlines()[-25:]))

    _section(f"PREVIOUS LOGS — {name} (crashed container; empty if never crashed)")
    rc, out, _ = _kubectl(
        ns, "logs", name, "--previous", "--tail=100", "--all-containers"
    )
    print(
        out
        if rc == 0 and out.strip()
        else "(no previous container — not restarted, or logs rotated)"
    )

    _section(f"CURRENT LOGS — {name} (tail 100)")
    rc, out, _ = _kubectl(ns, "logs", name, "--tail=100", "--all-containers")
    print(out if rc == 0 and out.strip() else "(no current logs)")


_NEXT_STEPS = (
    "- OOMKilled / exit 137 -> raise memory limit OR capture a heap dump.\n"
    "- exit 139 (SIGSEGV)   -> pull the core (kubectl cp) and run coredump-bt.py.\n"
    "- CrashLoopBackOff      -> the PREVIOUS LOGS above hold the startup failure.\n"
    "- Pending/Unschedulable -> read RECENT EVENTS for the scheduling reason.\n"
    "- Shell into a crashing/distroless pod without changing it:\n"
    "    kubectl debug -it <pod> -n <ns> --image=busybox:1.36 --target=<container>"
)


def main(argv):
    if not argv:
        print(
            "usage: k8s-triage.py <pod | deploy/name | label=value> [namespace]",
            file=sys.stderr,
        )
        return 2
    if shutil.which("kubectl") is None:
        print("error: kubectl not found on PATH", file=sys.stderr)
        return 2

    target = argv[0]
    ns = argv[1] if len(argv) > 1 else "default"

    _section("OVERVIEW (-o wide)")
    _print_overview(ns, target)

    _section("RECENT EVENTS (sorted by time)")
    _, out, _ = _kubectl(ns, "get", "events", "--sort-by=.lastTimestamp")
    print("\n".join(out.splitlines()[-30:]))

    _section("LIVE RESOURCE USAGE (needs metrics-server)")
    rc, out, _ = _kubectl(ns, "top", "pod", target.split("/")[-1])
    print(out if rc == 0 else "(kubectl top unavailable)")

    pods = _resolve_pods(ns, target)
    if not pods:
        print(
            f"\n(no pods resolved for '{target}' in namespace '{ns}')", file=sys.stderr
        )
        return 0
    for pod in pods:
        _triage_pod(ns, pod)

    _section("NEXT STEPS")
    print(_NEXT_STEPS)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
