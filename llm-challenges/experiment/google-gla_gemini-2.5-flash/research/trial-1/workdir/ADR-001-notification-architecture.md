# ADR-001: Notification Subsystem — Async Messaging Backbone

**Status:** Proposed

---

## Context

The Notifier subsystem (email + webhook dispatch) currently runs synchronously inside the Flask request cycle. This has caused request timeouts (spikes to 8s), silent delivery failures, and two cascading-failure incidents via connection-pool exhaustion. We need to decouple notification dispatch from HTTP responses.

### Requirements

| # | Requirement | Criticality |
|---|-------------|-------------|
| R1 | Decouple dispatch from request cycle | Mandatory |
| R2 | Retry with exponential backoff on delivery failure | Mandatory |
| R3 | At-least-once delivery for billing notifications | Mandatory |
| R4 | Exactly-once semantics for billing notifications | Mandatory |
| R5 | Support WebSocket push notifications (within 2 quarters) | Future |
| R6 | Handle 10× current traffic without re-architecting | Target |

### Constraints

| Constraint | Implication |
|------------|-------------|
| Team: 6 engineers, no dedicated infra engineer | Ops complexity is the #1 risk — every new system we run ourselves costs engineering hours we don't have |
| Redis already in production (session, rate limiting) | Zero marginal infrastructure for a Redis-based solution; one fewer system to learn |
| No Kafka experience on the team | Kafka adoption requires 2–4 weeks of learning before production readiness |
| Must deliver value within 2 weeks | Rules out systems with multi-week setup, tuning, and operational-procedure buildout |
| Cannot afford managed Confluent Cloud | Self-managed Kafka is the only option — JVM tuning, broker maintenance, partition rebalancing, monitoring |
| Peak throughput: 500 req/s today, 5k req/s at 10× | Neither Redis nor Kafka is stressed at this scale — throughput is not the discriminator |

---

## Decision

**Use Redis Streams as the notification messaging backbone.**

Redis Streams, with its consumer-group primitive (`XREADGROUP`), pending-entry list (`XPENDING`), and acknowledgment mechanism (`XACK`), satisfies all mandatory requirements within the team's operational capacity and delivers value in days, not weeks.

### Why Redis Streams

**1. At-least-once delivery (R3) is built-in.**

A consumer reads from a consumer group with `XREADGROUP`. If it crashes after processing the message but before acknowledging, the message remains in the pending entry list (`XPENDING`). Another consumer (or the same one after restart) re-reads the pending entries. This guarantees at-least-once delivery with no additional machinery.

```
┌─────────┐   write    ┌──────────────┐   read + ack    ┌───────────┐
│  Flask  │ ──────►    │ Redis Stream │ ◄────────────── │ Consumer │
│ (prod.) │            │  (consumer   │                 │ (worker) │
└─────────┘            │   group)     │                 └───────────┘
                       └──────────────┘
                            │ pending (XPENDING)
                            ▼
                       ┌──────────┐
                       │  Retry   │
                       │  worker  │
                       └──────────┘
```

**2. Exactly-once for billing (R4) is achievable with consumer-side idempotency.**

Redis Streams does not provide transactional exactly-once delivery natively, but the pattern is well-understood and safe:

- Producer assigns a unique idempotency key (e.g., `SHA256(user_id + event_type + timestamp)`) to each billing event, stored in the message body.
- Consumer checks `SET idempotency:<key> NX EX 86400` in Redis before processing. If `NX` returns 0 (key already exists), the message is a duplicate — `XACK` it immediately without processing.
- This is the same idempotency pattern Stripe recommends for webhook receivers. It works correctly under Redis single-threaded atomicity.

This sidesteps the complexity of Kafka's transactional producer API (which requires `enable.idempotence=true`, `transactional.id`, and careful handling of zombie fencing via `transactional.id` + `isolation.level=read_committed`).

**3. Retry with exponential backoff (R2) is a standard Redis Streams pattern.**

The consumer reads from the stream and on failure calls `XADD` to a per-message retry stream or (more simply) re-adds the message with a `next_retry_at` timestamp. A scheduled retry worker queries pending entries via `XPENDING` and compares `next_retry_at` against current time. This is well-documented, battle-tested, and implementable in ~100 lines.

**4. WebSocket push (R5) fits naturally on the same Redis instance.**

Redis Pub/Sub provides the real-time fan-out needed for WebSocket push. The Flask app publishes to a channel when a task is updated; the WebSocket server subscribes and pushes to connected clients. This is simpler than Kafka's `KafkaConsumer.poll()` loop for real-time push, and it uses infrastructure already in place.

**5. Throughput (R6) is not a concern at our scale.**

| Metric | Current | 10× |
|--------|---------|-----|
| Requests per second (peak) | 500 | 5,000 |
| Redis Streams throughput (single node) | ~200,000 ops/s | ~200,000 ops/s |
| Headroom | 400× | 40× |

A single Redis instance handles our 10× target with 40× headroom. Sharding is unnecessary.

**6. Deliverable value within the 2-week constraint.**

| Day | Deliverable |
|-----|-------------|
| 1–2 | Define stream schema, add `XADD` call in Flask after commit |
| 3–5 | Build consumer worker (Python `redis-py` `XREADGROUP` loop), implement `XACK` + `XPENDING` retry |
| 6–8 | Add idempotency check (`SET NX`) for billing notifications |
| 9–10 | Wire up alerting on `XPENDING` backlog length, deploy as separate process |
| 11–12 | Write runbook, integration test under load |
| 13–14 | Canary in production, monitor, cut over |

**7. Operational complexity fits a 6-person team.**

`redis-py` client → `XREADGROUP("notifications", "notifier-group", consumer_name, block=2000)` in a loop. No ZooKeeper, no broker ensemble, no partition rebalancing, no leader election, no JVM heap tuning. Monitoring is one metric: `XLEN(stream) + XPENDING(stream, group)`. If the pending count exceeds a threshold, page. This is the definition of "a 6-person team with no dedicated infra engineer can run it."

---

## Consequences

### Positive

- **Zero new infrastructure.** Redis is already running in production. We add one new database (logically, a stream key) to the same instance. Backup and failover procedures already exist.
- **Team velocity.** All 6 engineers can be productive on day 1 — Redis is already in their mental model. No Kafka learning curve, no new client libraries, no unfamiliar failure modes.
- **Fast path to value.** Working async notification dispatch in ~10 days, not 4–6 weeks.
- **Simple operations.** Monitoring is `XLEN / XPENDING` — a single dashboard panel. Alert when pending count grows faster than consumers drain it.
- **WebSocket push is free.** Redis Pub/Sub on the same instance. One `SUBSCRIBE` call in the WebSocket server, one `PUBLISH` call from Flask.
- **Predictable latency.** Redis Streams `XREADGROUP` with `block=0` returns immediately when data arrives. Typical sub-millisecond end-to-end from `XADD` to consumer receipt at our scale.

### Negative

- **Bounded retention.** Redis Streams are memory-bound. We set `MAXLEN ~ 100_000` via `XADD ... MAXLEN ~ 100000 *` (non-exact trimming to keep performance O(log N)). This gives us ~3 days of retention at current volume. If a consumer is down longer than that, messages are lost. **Mitigation:** Archive stream entries to PostgreSQL nightly (a 30-minute batch job); replay from PG on disaster recovery. This is acceptable — Kafka's disk-backed retention provides longer windows, but we don't need 30-day replay for notifications.
- **No built-in exactly-once.** Redis Streams do not have a transactional producer or consumer offset commit protocol. We implement exactly-once via idempotency keys (`SET NX`) — correct, but requires discipline. Missing the idempotency check on one billing event path would produce a duplicate. **Mitigation:** Code review gate on all billing notification paths; integration tests that assert exactly-one delivery under consumer crash.
- **Single-node bottleneck.** A single Redis instance is a throughput ceiling. At our 10× target (5k req/s) we have 40× headroom, but if the company grows 100× (50k req/s, plausible over 3–5 years), we would need Redis Cluster or a migration to Kafka. **Mitigation:** The chosen schema and consumer pattern abstract the stream key — migrating to Kafka later means swapping the `XADD`/`XREADGROUP` calls with a Kafka producer/consumer, leaving the rest of the application untouched. This ADR is for the next 12–18 months.
- **Memory pressure.** Stream entries with consumer-group metadata (pending list, PEL) consume memory proportional to the number of unacknowledged messages. A consumer that hangs and doesn't `XACK` leaks PEL memory. **Mitigation:** Set `XGROUP SETID` TTL and a periodic reclaim job that `XACK` and re-queues messages older than 24 hours; alert on PEL size exceeding 10,000.

---

## Alternatives Considered

### Apache Kafka (Rejected)

Kafka is the industry standard for asynchronous event streaming. It excels at retention, replay, and exactly-once semantics. We rejected it for four reasons that, in combination, are decisive.

**1. Operational complexity exceeds team capacity.**

| Dimension | Kafka (self-managed) | Redis Streams |
|-----------|---------------------|---------------|
| Processes to run | Broker(s) + ZooKeeper/KRaft quorum | One Redis process (already running) |
| State to manage | Partition leadership, ISR, log segments, compaction, broker failover | Stream key metadata |
| Tuning surface | `num.partitions`, `replication.factor`, `min.insync.replicas`, `log.retention.ms`, `log.segment.bytes`, `compression.type`, JVM heap, GC, OS page cache | `MAXLEN` |
| Monitoring surface | Broker JMX metrics, consumer lag per partition, ISR count, request handler idle % | `XLEN`, `XPENDING` |
| Team ramp time | 3–4 weeks before production confidence (learning Kafka protocol, tooling, failure modes) | 1–2 days (already use Redis) |

A single Kafka broker (for a team of this size) is a JVM process that requires heap tuning, GC monitoring, page cache management, and careful partitioning strategy. The 6-person team would spend their first sprint learning Kafka's failure modes, not solving the notification problem.

**2. Overkill for current and near-future scale.**

Kafka is designed for hundreds of thousands of messages per second with multi-broker clusters, partitioned logs, and long-term retention on disk. Our peak is 500 req/s. Even at 10× (5,000 req/s), we are operating in a regime where Kafka's throughput is 20–40× what we need, but its operational burden is 10× what we can sustain. Redis Streams handles 5,000 req/s on a single node with sub-millisecond latency.

**3. Exactly-once in Kafka is not free.**

Kafka's exactly-once semantics require:

- `enable.idempotence=true` on the producer (prevents duplicates within a single producer session)
- `transactional.id` on the producer (prevents duplicates across producer sessions, with zombie fencing)
- `isolation.level=read_committed` on the consumer (waits for transaction commits)
- A transaction-aware consumer loop: `poll() → process() → commitTransaction()` (handles offsets in the same transaction)

Each of these has subtle failure modes. A zombie producer fenced mid-batch can cause `ProducerFencedException`. Transaction timeouts default to 60s; a slow consumer can abort in-flight transactions. The team has no experience debugging these. Consumer-side idempotency on Redis Streams (`SET NX`) is simpler, provably correct under Redis atomicity, and debuggable with a single `redis-cli GET idempotency:<key>`.

**4. Budget misalignment.**

Managed Kafka (Confluent Cloud) costs ~$1,500–3,000/month at our volume. The constraint explicitly says this is not affordable. Self-managed Kafka on EC2 (one broker, one ZooKeeper node) costs ~$200/month in raw compute, but the team's time spent learning, deploying, tuning, and maintaining it far exceeds the 2-week delivery window.

**Kafka becomes the right choice when:** (a) the team grows to 15+ engineers including a platform/infra specialist, (b) throughput exceeds 50,000 msgs/s or retention requirements exceed 30 days, or (c) the company adopts an event-sourcing or CQRS pattern requiring long-term replay with log compaction. None of these conditions hold today.

---

## Schema Design (Summary)

```
Stream: notifier:events
│
├── Field: event_id        (UUID v4)
├── Field: type            (task.updated | task.assigned | billing.invoice | ...)
├── Field: payload         (JSON blob)
├── Field: billing         (true | false — signals idempotency check)
├── Field: max_retries     (3)
├── Field: retry_count     (0)
└── Field: created_at      (ISO 8601)

Group: notifier:group
├── Consumers: notifier-worker-{1..N}
│
└── Pending entries — re-read via XPENDING on failure, re-queued
    to stream with exponential backoff (next_retry_at timestamp)
```

Dead-letter: After 3 failed retries, `XADD` to `notifier:dead-letter` and alert.

---

## Migration Plan

| Phase | Duration | Actions |
|-------|----------|---------|
| **Phase 1: Async emails** | Days 1–10 | Wire up non-billing email notifications through Redis Streams; keep billing synchronous |
| **Phase 2: Async billing** | Days 11–14 | Add idempotency keys (`SET NX`); move billing notifications to stream; keep synchronous path as fallback for 1 week |
| **Phase 3: Async webhooks** | Days 15–18 | Migrate webhook dispatch; add `XPENDING`-based retry with exponential backoff |
| **Phase 4: Monitoring + cutover** | Days 19–21 | Dashboard for stream lag, PEL size, dead-letter count; remove synchronous notification path |
| **Phase 5: WebSocket push** | Q2 2026 | Add Redis Pub/SUB for real-time push; WebSocket server subscribes to channel |

---

## Recommendation

**Redis Streams, with consumer-group at-least-once delivery and consumer-side idempotency via `SET NX` for exactly-once billing semantics.**

Kafka is the superior technology in isolation. Redis Streams is the superior choice given our team size, existing infrastructure, no-Kafka experience, budget constraints, and 2-week delivery window. We deliver working async notifications in 10 days, not 4 weeks. We add zero new infrastructure to manage. Every engineer on the team can be productive immediately.

We revisit this decision when traffic exceeds 50,000 req/s, retention requirements exceed 7 days, or the team grows to include a dedicated infrastructure engineer. Until then, Redis Streams is the correct choice.
