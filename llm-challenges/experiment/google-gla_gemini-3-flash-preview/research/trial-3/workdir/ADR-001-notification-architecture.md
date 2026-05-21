# ADR-001: Notification Subsystem — Async Messaging Backbone

**Status:** Proposed

---

## Context

The Notifier subsystem sends emails and webhooks on task events (created, updated, assigned, completed). As the platform has grown to 85k MAU and ~2M tasks/month, the synchronous in-request-cycle model is failing:

- **Latency**: 800ms average, 8s spikes at peak (~500 req/s).
- **Silent drops**: No retry mechanism; failed outbound calls are lost.
- **Cascading failures**: Slow webhook endpoints exhausted the connection pool twice this year, degrading unrelated features.
- **No guarantees**: Billing-critical notifications (trial expiry, payment failures) lack even at-least-once delivery, risking revenue and compliance.

We need an asynchronous message backbone that decouples notification dispatch from the HTTP request cycle, supports retry with exponential backoff, provides at-least-once delivery (exactly-once for billing), and can serve as a foundation for future WebSocket push notifications within two quarters.

### Constraints

| Constraint | Impact |
|---|---|
| 6-person team (3 senior, 3 mid), no dedicated infra engineer | Operationally simple solution preferred |
| Redis already in production for sessions and rate limiting | Existing ops expertise; no new service to run |
| Zero Kafka experience on the team | Steep learning curve counts as a real cost |
| ≤2 weeks setup-to-value | Must ship fast; complex infrastructure delays are unacceptable |
| Budget modest — managed Confluent Cloud not affordable at scale | Self-hosted Kafka is the only Kafka option |
| 10× traffic headroom needed | Current peak 500 req/s → target ~5000 req/s |
| Exactly-once semantics for billing notifications | Hard requirement for a subset of messages |

---

## Decision

**Use Redis Streams** as the notification message backbone.

### Architecture Sketch

```
HTTP Request → Flask handler → XADD to Redis Stream
                                        ↓
                         Consumer Group (worker processes)
                            ↙           ↘
                    Email Worker    Webhook Worker
                    (retry+DLQ)     (retry+DLQ)
```

- Each notification type gets its own stream key (e.g., `notif:email`, `notif:webhook`, `notif:billing`).
- Workers use `XREADGROUP` with consumer groups for at-least-once delivery.
- Failed deliveries are retried via `XCLAIM` after inspecting the Pending Entry List (PEL), with exponential backoff managed by consumer-side logic.
- Billing notifications use an idempotency key (event ID + notification type) stored in Redis or PostgreSQL to achieve exactly-once semantics — the consumer checks `SET NX` before dispatching.
- Streams are capped with `MAXLEN ~100k` per key to bound memory while retaining enough history for recovery windows.
- Future WebSocket push: a dedicated consumer group reads the same streams and pushes to connected clients via Redis Pub/Sub or direct WS. No architectural change needed.

### Why This Wins

1. **Zero new infrastructure.** Redis is already deployed, monitored, and understood by the team. No Zookeeper or KRaft cluster to stand up. No new firewall rules, backup procedures, or monitoring dashboards.

2. **Shallow learning curve.** Redis Streams commands (`XADD`, `XREADGROUP`, `XACK`, `XPENDING`, `XCLAIM`) number fewer than a dozen. Every team member can be productive in a day. Kafka's ecosystem (partitions, offsets, consumer rebalancing protocols, compaction, tiered storage, exactly-once transaction protocol) takes weeks to internalize.

3. **Fast time-to-value.** A working prototype — Flask handler writing to a stream + a Python worker reading with `XREADGROUP` — can ship in a single sprint. Kafka requires provisioning brokers, choosing partition counts, configuring retention, and understanding the rebalance protocol before the first message flows.

4. **Adequate performance headroom.** A single Redis instance handles 100k+ ops/s on modest hardware. Our 10× target (~5000 enqueue/s) is trivial. Kafka's horizontal scaling advantages don't matter until we're well beyond this scale.

5. **Exactly-once for billing via idempotency.** Redis Streams don't provide exactly-once guarantees natively — but neither does Kafka without its transaction API (which adds complexity). The pragmatic approach is idempotent consumers: each billing event carries a unique ID; the consumer checks `SET event:<id> NX` before dispatching. This works identically regardless of the message broker chosen.

6. **Direct path to WebSocket push.** Two quarters from now, a Real-time Worker consumes the same streams and pushes to WebSocket connections. No partitioning, no Kafka consumer group rebalance drama. The stream is already ordered and available.

---

## Consequences

### Pros

- **Operational simplicity.** One fewer stateful system to manage. Redis failure modes (connection loss, OOM, failover) are already understood and handled.
- **Fast shipping.** Can produce value in week 1 instead of week 3-4.
- **Natural retry model.** The PEL tracks unacknowledged messages. XCLAIM lets a recovery worker retry them with backoff. Dead-letter: after N retries, move the message ID to a `notif:dead-letter` stream for manual inspection.
- **Exactly-once parity with Kafka.** Both brokers require consumer-side idempotency for true exactly-once. Neither provides it for free without significant protocol complexity.
- **Future-compatible.** If Redis Streams hit scaling limits (unlikely before 100× growth), the stream abstraction means Kafka can be introduced behind the same producer interface later.

### Cons

- **Memory-bound retention.** Redis streams live in RAM. Even with `MAXLEN`, old messages are evicted by count, not by time. If we need long-term replay (days/weeks), we'd need to archive to S3 or PostgreSQL separately. Kafka's disk-backed log retains by time or size natively.
- **No native partitioning.** A Redis stream is ordered but not partitionable. If a single consumer group can't keep up (unlikely at our scale), you'd shard by stream key or introduce a routing layer. Kafka partitions scale linearly with brokers.
- **Manual rebalancing.** When adding/removing Redis Stream consumers, there's no automatic partition rebalancing — you manage consumer names and claim idle entries manually. Kafka's consumer group coordinator handles this transparently.
- **Consumer failure recovery is explicit.** If a consumer dies without `XACK`, the PEL entries accumulate. A reaper process using `XPENDING` + `XCLAIM` is needed to recover stuck messages. Kafka's consumer rebalance protocol handles partition reassignment automatically.

---

## Alternatives Considered

### Apache Kafka

**Why it was rejected:**

- **Operational burden on a 6-person team.** A production Kafka cluster requires at least 3 brokers, a KRaft quorum (or Zookeeper ensemble), persistent volumes with adequate IOPS, monitoring for consumer lag, ISR status, and disk usage. This is a part-time engineer's worth of ongoing work — we don't have that person.
- **No team Kafka experience.** Every debugging session (consumer offset commits stalled, rebalancing in a storm, unclean leader election) would be a research project. Redis failures are already diagnosed quickly.
- **Setup-to-value exceeds 2 weeks.** Spinning up Kafka, tuning producers/consumers, configuring retention, securing inter-broker communication, and building the first pipeline exceeds our two-week window. Redis Streams can be in production in a day.
- **Managed Kafka is unaffordable.** Confluent Cloud pricing at our scale (~2M messages/month, growing 10×) would strain our budget. Self-hosted is the only option, which brings the operational burden above.
- **Overkill for our scale.** Kafka excels at 100k+ msg/s, multi-subscriber fan-out, and long-term log compaction. We need ~500 msg/s today, at-most a few consumer groups per stream, and retention measured in hours not weeks. Redis Streams are a proportional tool for the problem.

**Where Kafka would win (if constraints were different):**

- If we had 10× the traffic *today* and a dedicated platform team, Kafka's automatic rebalancing, disk-backed retention, and native replay capabilities would make it the better choice.
- If we needed to retain messages for weeks for auditing or replay, Kafka's disk-based log is simpler than Redis Streams + an archiver.

### PostgreSQL LISTEN/NOTIFY

Briefly considered and dismissed. `NOTIFY` payloads are capped at 8k bytes, there's no consumer group mechanism, and undelivered notifications are lost if the connection drops. It solves none of our failure-mode requirements.

### RabbitMQ

A reasonable middle-ground but introduces a new system the team doesn't run today, whereas Redis Streams reuse an existing one. RabbitMQ's AMQP model is more mature for complex routing but adds operational surface area for no marginal benefit over Redis Streams at our scale.
