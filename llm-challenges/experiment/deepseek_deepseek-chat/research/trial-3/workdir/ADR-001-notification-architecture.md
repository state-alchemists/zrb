# ADR-001: Notification Subsystem — Async Processing Architecture

**Status:** Proposed

---

## Context

The notifications module sends emails and webhooks when tasks are updated, assigned, or completed. It currently runs synchronously inside the HTTP request cycle, causing three classes of production incidents: request timeouts (800ms avg, 8s spikes), silent failures when external providers are down, and cascading failures from connection pool exhaustion. Billing-critical notifications ("trial expired", "payment failed") have no delivery guarantee.

**System properties:**
- 85,000 MAU, 2M tasks/month, 500 req/s peak
- Python/Flask monolith, PostgreSQL, Redis (session + rate limiting), 4 AWS web servers
- 6-person engineering team (3 senior, 3 mid), no dedicated infrastructure engineer

**Non-negotiable constraints:**
1. Notifications must be decoupled from the HTTP request cycle (async).
2. Retry with exponential backoff and a dead-letter queue.
3. At-least-once delivery for all notifications; exactly-once processing for billing events.
4. WebSocket push support within 2 quarters.
5. Handle 10x traffic growth without re-architecting.
6. Must deliver production value within 2 weeks.
7. No team Kafka experience today.
8. Budget cannot support managed Confluent Cloud at full scale.

---

## Decision

**Use Redis Streams** as the async message bus for notifications.

Redis Streams provide a native, ordered message log with consumer groups, acknowledgment tracking via a Pending Entry List (PEL), and blocking reads. We already run Redis in production. This decision lets us decouple notifications in days, not weeks, using infrastructure the team already operates.

The exactly-once processing requirement will be met with a consumer-side idempotency pattern (deduplication key stored in PostgreSQL), not a broker-level feature — because Redis Streams do not natively offer exactly-once semantics, and the team should own the guarantee at the application layer where it can be tested and audited.

---

## Consequences

### Pros

- **Zero new infrastructure.** Redis is already deployed for session storage and rate limiting. Adding streams requires no new servers, no new persistence layer, and no new operational runbooks. This alone satisfies the 2-week delivery constraint.

- **Fast time-to-value.** A producer can `XADD` a stream entry in ~10 lines of Python. A consumer worker can `XREADGROUP` in another ~15 lines. An intern or mid-level engineer can have a working prototype by the end of day one. Production-hardened delivery with retry, DLQ, and idempotency is achievable inside week one.

- **Team familiarity.** All 6 engineers have worked with Redis. The operational surface area (memory monitoring, key eviction, failover) is already understood. No learning curve on broker topology, partition rebalancing, or offset management.

- **Sufficient throughput.** A single Redis node handles 100k–200k ops/s. Our peak is 500 req/s, with perhaps 2–4 stream entries per request (task-created, assignee-notified, billing-checked) — well within 2k entries/s at peak. 10x target growth (~5k entries/s) is still well within a modest Redis Cluster's capability.

- **Consumer groups with PEL** give us at-least-once delivery out of the box. If a consumer crashes after receiving a message but before acknowledging it, the message remains in the PEL and can be claimed by another consumer via `XCLAIM`. This maps directly to our retry requirement.

- **Exactly-once processing** is achieved via consumer-side idempotency: before processing a stream entry, the consumer checks a deduplication key (e.g., `billing_event:<task_id>:<timestamp>` with a UNIQUE constraint in PostgreSQL). If the key exists, the message is acknowledged but skipped. This pattern is well-understood, auditable, and does not depend on broker features that may change across upgrades.

- **Natural path to WebSocket push.** Redis Streams can be consumed by a lightweight WebSocket relay service. Alternatively, Redis Pub/Sub (already available on the same instance) can fan out stream events to WebSocket connections. This fits the 2-quarter timeline without adding Kafka or a separate message bus.

- **Low operational overhead.** One Redis instance or a small Redis Cluster. Monitoring: `INFO` commands, memory used by streams (`XINFO`), and PEL depth. A 6-person team with no dedicated infra engineer can operate this.

### Cons

- **Memory-bound retention.** Redis stores stream data in memory. Unlike Kafka, which writes to disk and retains data by configurable policy regardless of consumption rate, Redis Streams must be trimmed. We will need a scheduled job to `XTRIM` (or `XDEL` after acknowledgment) and must budget memory for the stream backlog. At 2k entries/s peak with a ~48-hour retention window (generous for a notification system), this is manageable in a few GB of memory.

- **No native exactly-once.** Kafka offers exactly-once semantics via transactional producers and idempotent consumers. Redis Streams do not. We must implement idempotency in the consumer. This is well-understood and not difficult, but it is an explicit engineering responsibility that must be tested and maintained.

- **No Kafka Connect ecosystem.** If we later need to stream notifications to a data lake (e.g., S3 via Kafka Connect S3 Sink), we would need custom exporters or a separate pipeline (e.g., Redis → Debezium → Kafka → S3 for the audit trail). This is a reasonable trade-off given the team size and current requirements — we can cross this bridge when the need arises.

- **Stream rebalancing is manual.** Redis Streams consumer groups do not automatically rebalance partitions when a consumer joins or leaves (unlike Kafka's `group.protocol`). If a consumer crashes, another consumer must explicitly `XCLAIM` the pending messages. This is adequate for our scale; a simple background heartbeat + claim loop handles it.

- **Single-node write bottleneck at extreme scale.** Redis is single-threaded for commands. Under sustained writes above ~100k entries/s (far beyond our 10x target of ~5k/s), this becomes a bottleneck. Redis Cluster shards by key hash, so scaling beyond a single node for stream writes requires careful key design.

---

## Alternatives Considered

### Apache Kafka (Rejected)

Kafka is the industry standard for high-throughput event streaming. It provides:

- **Exactly-once semantics natively** via idempotent producers + transactional consumers.
- **Disk-based retention** — no memory limits. Messages can be retained for days or months regardless of consumer speed.
- **Strong ordering guarantees per partition** with automatic rebalancing.
- **Kafka Connect ecosystem** for sink/source integrations.
- **Proven at massive scale** (millions of messages/s).

We rejected it for the following hard constraints in our context:

1. **No team experience + no infra engineer.** Kafka requires deep understanding of: ZooKeeper (or KRaft) quorum management, topic partitioning strategy, consumer offset commits (at-least-once vs. exactly-once vs. at-most-once), `min.insync.replicas` and `acks` tuning, partition rebalancing protocols, and log compaction vs. retention. A 6-person team without prior Kafka experience and no dedicated infra engineer cannot safely operate Kafka in production within 2 weeks. The learning curve for the full team would be 4–8 weeks.

2. **Self-hosted Kafka is operationally heavy.** A minimum viable production setup requires 3 Kafka brokers + 3 ZooKeeper nodes (or 3 KRaft controllers). Each needs CPU, memory, disk I/O tuning, and monitoring. Compare this to adding streams to a Redis instance we already run. The operational burden on a small team is significant.

3. **Managed Kafka is expensive.** Confluent Cloud minimum production clusters start at ~$1,200/month (confluent.cloud/pricing). Aws.msk starts at ~$300/month but still requires team Kafka knowledge to operate. For a team running $500–1k/month total infra today, this is a material cost increase for a single subsystem.

4. **Over-engineered for our throughput.** Kafka shines at 100k+ messages/s with replayability and multi-subscriber fan-out. Our peak is ~2k messages/s with exactly one consumer group (the notification workers) today and perhaps two (adding WebSocket relay) within 2 quarters. Redis Streams handles this with less complexity and no additional cost.

5. **Slower to value.** Even with MSK, the team needs to learn consumer group mechanics, offset positioning, rebalancing protocols, and exactly-once configuration. Production-ready async notification delivery is 3–4 weeks minimum with Kafka vs. 1 week with Redis Streams — violating the 2-week constraint.

Kafka becomes the right choice if we outgrow Redis memory limits (extremely unlikely at 10x our current scale), need multi-datacenter replication (not in scope), or must stream to a data lake via Kafka Connect (future, not blocking). **At that point the recommendation should be reassessed**, but Kafka today would be premature optimization that delays value and increases operational risk.

### RabbitMQ (Not formally evaluated)

RabbitMQ was not included in the evaluation brief. For completeness: RabbitMQ provides AMQP-based messaging with strong delivery guarantees, but its native stream support (as of RabbitMQ 3.9+) is newer than Redis Streams or Kafka, the team has no RabbitMQ experience either, and adding a third middleware system (alongside PostgreSQL and Redis) increases the operational surface area without clear advantage over Redis Streams for this use case.

---

