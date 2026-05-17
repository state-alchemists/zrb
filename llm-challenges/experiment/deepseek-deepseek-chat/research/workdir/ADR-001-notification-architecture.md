# ADR-001: Notification Subsystem — Async Processing Architecture

**Status**: Proposed

---

## Context

Our SaaS project management platform (85K MAU, ~2M tasks/month, peak 500 req/s) sends email and webhook notifications synchronously within the Flask HTTP request cycle. This causes four systemic problems:

1. **Request timeouts** — email/webhook sends block responses. Average latency 800 ms, spikes to 8 s at peak.
2. **Silent failures** — downstream failures (email provider down, webhook endpoint unreachable) drop notifications with no retry or dead-lettering.
3. **Cascading failures** — two incidents this year where a slow webhook consumer exhausted connection pools, taking down unrelated features.
4. **No delivery guarantees** — billing-critical events ("trial expired", "payment failed") require at-least-once or exactly-once delivery; the current system provides neither.

We need an asynchronous, persistent message backbone that decouples notification production from consumption, supports retry with exponential backoff, scales to 10× current traffic without re-architecture, and fits a 6-person engineering team (3 senior, 3 mid) with no dedicated infrastructure engineer.

**Constraints**:
- Redis is already in production for session storage and rate limiting.
- No team experience with Kafka.
- Must deliver value within 2 weeks of setup/migration work.
- Budget cannot support managed Confluent Cloud at full scale.
- Billing notifications require exactly-once semantics.

---

## Decision

### Chosen: Redis Streams

**Implement a notification pipeline using Redis Streams with consumer groups, a dead-letter stream, and application-level idempotency for exactly-once billing guarantees.**

We reject Apache Kafka despite its superior theoretical properties because the operational burden and learning curve are incompatible with our team size, timeline, and existing infrastructure. Redis Streams delivers 80% of the benefit at 20% of the cost — and the 20% gap (exactly-once, unbounded retention) is addressable through application patterns.

---

## Consequences

### Pros

**1. Zero new infrastructure.** Redis is already deployed, monitored, and understood by the team. Adding Streams support requires no new servers, no new backup strategy, no new monitoring dashboards, and no new on-call procedures. This alone collapses the setup timeline from weeks (Kafka) to days (Redis Streams).

**2. Familiar operational model for a 6-person team.** Redis has one configuration file, one port, one CLI. There is no ZooKeeper ensemble to manage (legacy Kafka) or KRaft controller quorum to tune (modern Kafka). A team of 6 without an infrastructure engineer can operate Redis Streams confidently within the 2-week constraint. Kafka, even in KRaft mode, demands dedicated cluster planning, partition tuning, rebalance monitoring, and log retention management.

**3. Sufficient throughput.** Redis Streams handles ~100K messages/sec per stream. Our peak is 500 req/s, so even a 10× growth gives us 5,000 req/s — two orders of magnitude below Redis Streams' ceiling. Kafka's millions/sec throughput is irrelevant at this scale.

**4. Built-in consumer groups with acknowledgment tracking.** Redis Streams provides `XREADGROUP` for work-queue semantics across competing consumers, `XACK` for explicit acknowledgment, and `XPENDING` + `XAUTOCLAIM` for detecting and recovering failed deliveries. This directly solves the silent-failure and cascading-failure problems. If a consumer crashes mid-processing, the PEL (Pending Entry List) ensures the message is reassigned to another consumer after a configurable timeout.

**5. At-least-once delivery is native.** Every message remains in the stream until explicitly acknowledged. A consumer that crashes before `XACK` will see the message on reconnection (via the PEL). This satisfies the at-least-once requirement for general notifications.

**6. Dead-letter queues are straightforward.** A simple worker can scan `XPENDING` entries exceeding a delivery-count threshold and `XADD` them to a `notifications:dlq` stream, then `XACK` the originals. No external tooling required.

**7. Exactly-once billing semantics via application-level idempotency.** Redis Streams has no native exactly-once delivery. However, billing notifications have natural idempotency keys (e.g., `user_id + event_type + timestamp` or a generated `idempotency_key`). The consumer checks if the notification was already processed (e.g., a `processed_notifications` key in Redis, or a unique constraint in PostgreSQL) before sending. This pattern is well-understood, testable, and gives us exactly-once semantics for the 0.1% of traffic that needs it — without paying the complexity tax of Kafka transactions.

**8. WebSocket push path.** Redis Streams supports blocking reads (`BLOCK`), making them a natural fit for the WebSocket push feature planned in 2 quarters. Workers can maintain long-lived connections to streams and push to WebSocket clients without polling.

**9. Message ordering within a stream is maintained.** All notifications pushed to a single stream are totally ordered. For per-project or per-user ordering guarantees, producers can route by hash key to dedicated streams.

### Cons

**1. No native exactly-once delivery.** This is the most significant technical gap. We must implement idempotency checks at the consumer level for billing notifications (see Pros §7). This adds approximately 1–2 days of engineering work and a small per-message latency cost for the idempotency lookup.

**2. Memory-bound retention.** Redis stores stream data in memory (even with AOF persistence). With `MAXLEN ~ 100K` per stream, we can retain the most recent ~100K notifications per stream. Historical replay beyond this window requires either S3 archiving or a separate long-term store. For our use case (notifications are typically consumed within seconds or minutes), a retention window of hours is sufficient. If we ever need week-long replay, we can add a simple archival job to S3. Kafka's disk-based retention is irrelevant for data that is consumed and acknowledged in under a minute.

**3. No cross-stream ordering guarantee.** Redis Streams provides total ordering within a single stream but offers no ordering across streams. If a single notification producer needs global ordering, it must target a single stream (limiting parallelism). In practice, per-user or per-project ordering is sufficient, and routing by hash key satisfies this.

**4. Consumer groups break ordering.** Redis consumer groups distribute messages round-robin among consumers in the same group, which means a single consumer cannot assume it receives messages in order. For ordered processing within a group, you must pin one consumer per partition (as the Runnel library demonstrates). At our scale, a single consumer per notification type is likely sufficient; multiple consumers can be added for parallelism where ordering is not required (e.g., non-billing email sends).

**5. No built-in rebalancing.** When a consumer joins or leaves a Redis consumer group, messages in the PEL are not automatically reassigned (unlike Kafka's partition rebalance). Consumers must explicitly claim pending messages with `XAUTOCLAIM`. This is manageable for our team size but adds a pattern that must be implemented correctly.

---

## Alternatives Considered

### Apache Kafka (Rejected)

**Why it was considered**: Kafka is the gold standard for distributed event streaming. It offers exactly-once delivery via idempotent producers and transactions, disk-based retention for unbounded replay, per-partition ordering with automatic rebalancing, and throughput exceeding millions of messages per second.

**Why it was rejected**:

1. **Operational complexity dwarfs our team capacity.** Running Kafka means managing a cluster of brokers, monitoring ISR (in-sync replica) counts, configuring partition replication factors, tuning `retention.ms`, managing rebalance timeouts, and monitoring consumer lag. Even KRaft mode (Kafka 3.x+, which eliminates ZooKeeper) still requires a multi-node controller quorum and broker cluster. Our team of 6 with no infrastructure specialist would spend more time keeping Kafka healthy than building product features. The 2-week setup window is unrealistic — a production-ready Kafka deployment with monitoring and backup takes 3–6 weeks for a team learning it from scratch.

2. **Cost is disproportionate to need.** Kafka brokers are JVM-heavy. A 3-node production cluster on AWS (m6i.large or similar) costs ~$600–900/month just for compute. With EBS storage for retained logs, the monthly spend climbs higher. We already pay for Redis. Adding Kafka is a 50–100% increase in our data-infrastructure budget for a feature set far beyond our current scale (500 req/s peak).

3. **Over-engineered for the problem.** Kafka excels at gigabyte-scale event streaming, multi-subscriber fan-out across dozens of services, and long-term event sourcing. Our problem is simpler: decouple notification production from consumption, retry on failure, and maintain a dead-letter queue. Kafka's partitioning, compaction, stream processing (KSQL), and connector ecosystem would go 95% unused. Introducing a distributed system with capabilities we don't need increases cognitive load, deployment surface, and failure modes without proportional benefit.

4. **Learning curve delays delivery.** No one on the team knows Kafka. The Python client (`confluent-kafka-python`) binds to `librdkafka`, a C++ library with its own configuration surface. Debugging consumer offset commits, `__consumer_offsets` topic issues, or rebalance callbacks requires Kafka-specific knowledge that takes months to build. Redis Streams, by contrast, uses the same `redis-py` library the team already uses for session storage. The mental model is "append-only list with consumer tracking" — learnable in an afternoon.

5. **Exactly-once delivery, while native to Kafka, is overkill for the scope.** Kafka's exactly-once requires idempotent producers (set `enable.idempotence=true`) and transactions (`transactional.id`). This works well but adds complexity to the producer code and consumes additional broker resources. For the 0.1% of traffic that needs it (billing notifications), application-level idempotency on Redis Streams achieves the same result with far less infrastructure complexity.

**When Kafka would be the right choice**: If we were processing >100K msg/s, required 7+ day replay windows for audit trails, had 15+ microservices consuming the same events independently, or had 20+ engineers including an infrastructure team — Kafka would be the clear winner. None of these conditions hold.

---

## Recommendation

**Redis Streams.** It solves our four immediate problems (timeouts, silent failures, cascading failures, no delivery guarantees) within our team's operational capacity and 2-week delivery window. The gaps — exactly-once for billing and memory-bound retention — are closed with well-known application patterns (idempotency keys and S3 archiving), not by introducing a second distributed system.

Start with a single notification stream, one consumer group per notification type (email, webhook, billing), a retry worker with exponential backoff capped at 3 attempts, and a `notifications:dlq` dead-letter stream. Add the idempotency check for billing notifications before launch. Measure consumer lag, PEL size, and delivery-count distribution from day one.

This gets us to production in week one, leaves the WebSocket path open for quarter two, and keeps our architecture simple enough that a mid-level engineer can debug a notification issue without calling for help.
