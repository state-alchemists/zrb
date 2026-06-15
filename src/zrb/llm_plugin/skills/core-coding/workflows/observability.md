# Runtime Debugging & Observability

Use when a **running or deployed** system is failing — and you cannot reproduce it locally. The local `workflows/debug.md` loop still owns the root-cause method (reproduce → isolate → hypothesize → fix); this companion covers the **evidence-gathering tools** for systems you can only observe at a distance: crash/core dumps, memory/heap dumps, `kubectl`, Grafana/Prometheus, and Elasticsearch/Kibana.

**Mandate:** observe before you touch. Production diagnosis is read-mostly — capture state first (dumps, metrics, logs), form one hypothesis, then act. Never restart or redeploy a failing pod before capturing its evidence; the restart destroys the only copy of the failure.

**Pick the entry point by symptom:**

| Symptom | Start with |
|---------|-----------|
| Native process crashed (segfault, SIGABRT, exit 139) | [Core dumps](#core-dumps) |
| OOM / memory growth / leak / GC thrash | [Memory & heap dumps](#memory--heap-dumps) |
| Pod restarting, CrashLoopBackOff, OOMKilled, unschedulable | [kubectl triage](#kubectl-triage) |
| Latency spike, error-rate spike, saturation — "when and how bad?" | [Grafana / Prometheus](#grafana--prometheus) |
| Need the actual error/stack trace from a fleet of instances | [Elasticsearch / Kibana](#elasticsearch--kibana) |

A real incident usually chains them: **metrics** (Grafana — narrow the time window) → **logs** (Elastic — find the error and a correlation id) → **runtime** (kubectl — inspect the pod, pull a dump) → **dump** (core/heap — root cause).

---

## Core dumps

A core dump is the process's memory at the instant it crashed — the postmortem for native crashes (C/C++, Rust, Go, or any runtime that segfaulted).

**Enable capture (before the next crash):**
```bash
ulimit -c unlimited                      # current shell
cat /proc/sys/kernel/core_pattern        # where cores go; "|/.../systemd-coredump" = systemd owns them
```
- **systemd-coredump:** `coredumpctl list`, then `coredumpctl info <PID|exe>` and `coredumpctl gdb <exe>`.
- **Containers/k8s:** the kernel `core_pattern` is host-wide (not per-container). Set it on the node and ensure the pod's `ulimit -c` is non-zero; the core lands on the node or via systemd-coredump.

**Analyze with gdb** (`python <skill-dir>/tools/coredump-bt.py <binary> <core>` automates this; also `--systemd <exe|pid>`):
```bash
gdb <binary> <core> -batch \
  -ex "thread apply all bt full" \   # every thread's stack — the crashing one + what else was running
  -ex "info registers" -ex "info sharedlibrary"
```
Read the crashing thread's frame `#0` upward to the last line of *your* code. `thread apply all bt` exposes deadlocks (two threads each waiting on the other's lock).

**Language specifics:**
- **Go:** `dlv core <binary> <core>` → `goroutines`, `goroutine N stack`, `bt`. Set `GOTRACEBACK=crash` to force a core on panic.
- **Python:** `gdb python <core>` then `py-bt` (needs the CPython gdb extension) for the Python-level stack alongside the C stack.
- **C/C++:** build with `-g`; if symbols were stripped, point gdb at the debug-info package (`set debug-file-directory`).

---

## Memory & heap dumps

Use for leaks, unbounded growth, and OOM kills. A heap dump is a snapshot of live objects — it answers "what is holding all this memory?"

- **Java:** trigger on death with `-XX:+HeapDumpOnOutOfMemoryError -XX:HeapDumpPath=/dumps`. On a live PID: `jcmd <pid> GC.heap_dump /dumps/heap.hprof` (or `jmap -dump:format=b,file=heap.hprof <pid>`). Analyze in **Eclipse MAT** ("Leak Suspects" + "Dominator Tree"). For a hang, take a thread dump instead: `jcmd <pid> Thread.print` / `jstack <pid>`. A native crash leaves `hs_err_pid<pid>.log`.
- **Python:** `py-spy dump --pid <pid>` prints every thread's stack with **no code change and no restart** — the first tool to reach for on a stuck or runaway Python process. For allocation sources, `tracemalloc` (snapshot + `compare_to`) or `objgraph.show_most_common_types()`. For hangs, `faulthandler.dump_traceback_later(...)`.
- **Node.js:** start with `--heapsnapshot-signal=SIGUSR2`, then `kill -USR2 <pid>` to write a `.heapsnapshot`; open it in Chrome DevTools → Memory → "Comparison" between two snapshots. `process.report` gives a diagnostic JSON report. `clinic doctor` / `clinic flame` for CPU.
- **Go:** `go tool pprof <binary> http://host:port/debug/pprof/heap`; `curl 'http://host/debug/pprof/goroutine?debug=2'` dumps all goroutine stacks (find leaked goroutines). `inuse_space` vs `alloc_space` distinguishes a live leak from allocation churn.
- **Native C/C++:** `valgrind --leak-check=full --show-leak-kinds=all`, or build with `-fsanitize=address,leak` (ASan/LSan) for low-overhead detection; `massif` for a heap-over-time profile.

In Kubernetes, write the dump to a mounted volume (or `/tmp`) and pull it out with `kubectl cp ns/pod:/dumps/heap.hprof ./heap.hprof` — analyze locally, never inside the failing pod.

---

## kubectl triage

`python <skill-dir>/tools/k8s-triage.py <pod | deploy/name | label=value> [namespace]` runs the read-only sweep below in one shot. The manual essentials:

```bash
kubectl get pods -n <ns> -o wide                       # phase, restarts, node
kubectl describe pod <pod> -n <ns>                      # events, probes, last state, OOMKilled reason
kubectl logs <pod> -n <ns> --previous                   # logs from the CRASHED container (key flag)
kubectl logs <pod> -n <ns> -c <container> --tail=200
kubectl get events -n <ns> --sort-by=.lastTimestamp     # scheduling/eviction/probe failures
kubectl top pod <pod> -n <ns>                           # live CPU/mem vs limits (needs metrics-server)
```

**Read the exit code / reason** (from `describe` → `Last State`):
- `OOMKilled` / exit **137** — container hit its memory limit (SIGKILL). Raise the limit *or* fix the leak (heap dump above); 137 also = any external SIGKILL.
- exit **143** — SIGTERM (graceful shutdown / eviction). **139** — SIGSEGV (get a core dump). **1/2** — app error (read logs).
- `CrashLoopBackOff` — crashing on startup; `--previous` logs hold the cause.
- `Pending` / `Unschedulable` — resource/affinity/taint problem; the `events` list explains it.

**Get a shell into a distroless/crashing pod** without modifying it:
```bash
kubectl debug -it <pod> -n <ns> --image=busybox:1.36 --target=<container>   # ephemeral container, shares namespaces
```

---

## Grafana / Prometheus

Metrics tell you **when it started, how bad, and which resource** — use them to bound the incident window before reading logs.

- **Method:** **RED** (Rate, Errors, Duration) for request-serving services; **USE** (Utilization, Saturation, Errors) for resources (CPU, memory, disk, queues). Overlay the **deploy/annotation markers** — most incidents start at a release.
- **Useful PromQL** (use Grafana *Explore* to iterate):
  ```promql
  sum(rate(http_requests_total{status=~"5.."}[5m])) by (service)          # error rate
  histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))  # p99 latency
  container_memory_working_set_bytes{pod=~"app-.*"}                        # what the OOM-killer measures
  rate(container_cpu_usage_seconds_total{pod=~"app-.*"}[5m])               # CPU vs limit → throttling
  increase(kube_pod_container_status_restarts_total[1h])                   # restart storms
  ```
- `working_set_bytes` (not `rss`) is what the OOM-killer compares to the limit — chart it against `kube_pod_container_resource_limits` to confirm an OOM. Sustained CPU at the limit ⇒ CFS throttling ⇒ latency.

---

## Elasticsearch / Kibana

Logs give the **exact error and stack trace**, aggregated across every instance — go here once metrics have bounded the window.

- **Kibana Discover**, KQL scoped to the incident window:
  ```
  service: "checkout" and level: "error" and @timestamp >= "2024-01-01T10:00:00Z"
  ```
- **Correlate by id:** pull a `trace.id` / `request_id` / `correlation_id` from one error, then re-query on just that id to reconstruct the full request path across services.
- **Find the spike:** aggregate (`terms` on `error.type` or `message.keyword`, date histogram) to see which error surged and exactly when — line it up with the deploy marker from Grafana.
- **Raw query** when Kibana is unavailable:
  ```bash
  curl -s "$ES/logs-*/_search" -H 'Content-Type: application/json' -d '{
    "query": {"bool": {"must": [
      {"match": {"level": "error"}},
      {"range": {"@timestamp": {"gte": "now-1h"}}}]}},
    "sort": [{"@timestamp": "desc"}], "size": 50}'
  ```
- Beware **sampling and retention**: a missing log line may be dropped, not absent. Confirm the logging pipeline is healthy for that window before concluding "no errors."

---

## Output Format

1. **Symptom & window**: what's failing and the exact time range (from metrics).
2. **Evidence chain**: the metric → log → runtime → dump trail, with the concrete signal at each step (PromQL result, log line + correlation id, exit code/reason, dump frame).
3. **Root cause**: one precise sentence — what, where, why.
4. **Fix**: `file_path:line_number` or the config/limit change. If it's a capacity issue (limit too low), say so explicitly rather than calling it a bug.
5. **Verification**: the metric/log that should change after the fix, and confirmation it did.
