# ADR-001: Notification Subsystem — Async Processing Architecture

**Status:** Proposed

---

## Context

The Notifier subsystem sends emails and webhooks on task update, assignment, and completion events. It currently runs synchronously inside the Flask HTTP request cycle. With 85,000 MAU and ~500 req/s peak, this coupling causes four interconnected problems:

1. **Request timeouts** — average latency 800ms, spikes to 8s during peak hours.
2. **Silent failures** — failed SMTP calls or unresponsive webhook endpoints drop notifications with no retry or dead-letter queue.
3. **Cascading failures** — two incidents this year where slow webhook consumers exhausted the connection pool, taking down unrelated features.
4. **No delivery guarantees** — billing-critical events (trial expiry, payment failures) require exactly-once delivery but have none.

The team must decouple notification dispatch from the request cycle with an async message broker. The solution must support retry with exponential backoff, at-least-once delivery (exactly-once for billing), lay the groundwork for WebSocket push within two quarters, and handle 10x traffic growth.

**Critical constraints:**
- Engineering team: 6 people, no dedicated infra engineer, no Kafka experience.
- Redis already in production (session storage, rate limiting).
- Must ship production value within 2 weeks.
- Budget cannot absorb managed Kafka (Confluent Cloud, MSK) at full scale.
- Billing notifications must achieve exactly-once semantics.

---

## Decision

**Adopt Redis Streams as the notification message broker.**

The team will introduce a dedicated Redis Stream for notifications alongside the existing Redis instances (or a new, separate Redis node sized for notification throughput). Producers (the Flask monolith) will write notification events to the stream. A pool of consumer workers will read from consumer groups, dispatch emails and webhooks, acknowledge messages via `XACK`, and route failed deliveries to a dead-letter stream for manual review.

Exactly-once semantics for billing notifications will be implemented at the consumer layer: deduplication via a unique constraint on `(billing_event_id, notification_type)` in PostgreSQL, combined with Redis Streams' PEL (Pending Entry List) for at-least-once delivery guarantees. This achieves the same exactly-once outcome as Kafka transactions without the operational overhead.

---

## Consequences

### Benefits

**Leverages existing investment.** Redis is already deployed, monitored, and understood by the team. No new infrastructure, no new deployment pipelines, no new failure modes to learn. A dedicated notification Redis instance can be spun up from the same Ansible/Terraform templates used for the current cache nodes.

**Rapid time-to-value.** A working producer-consumer loop with retry and dead-letter routing can be built in days, not weeks. Redis Streams' `XADD`, `XREADGROUP`, `XPENDING`, and `XACK` form a complete consumer-group API without any external dependencies. The 2-week constraint is comfortable.

**Appropriate for scale.** Redis single-node throughput comfortably exceeds 100k ops/s. The target load (500 req/s today, 5,000 req/s at 10x) is two orders of magnitude below Redis' ceiling. A single notification-dedicated Redis instance (e.g., `cache.r6g.large` on AWS) is sufficient for years of growth. Scaling to multiple shards is possible via client-side partitioning if needed.

**PEL-based retry is built in.** `XREADGROUP` uses the Pending Entry List to track unacknowledged messages. Workers that crash mid-processing leave messages in the PEL; other consumers in the group auto-claim them after a timeout (`XAUTOCLAIM`). This provides at-least-once delivery without custom retry logic.

**Exactly-once for billing is achievable.** True exactly-once requires consumer-side idempotency in any brokered system — Kafka included. Redis Streams + PostgreSQL dedup table with a unique constraint gives the same guarantee as Kafka transactions (which also rely on an atomic commit). The implementation is simpler and debuggable with standard SQL.

**Natural path to WebSocket push.** Redis Pub/Sub integrates trivially with Streams. Consumer workers can publish to a `notifications:live` channel, and a WebSocket server (e.g., Flask-SocketIO with Redis as the message bus) forwards events to connected clients. This pattern is well-documented and avoids introducing a third message broker.

### Costs & Risks

**Memory-bound retention.** Redis holds data primarily in RAM. Notification streams must be capped with `MAXLEN` to avoid OOM. This limits message replay depth compared to Kafka's disk-backed log. Mitigation: set `MAXLEN ~ 100k` messages, archive finished billing records to PostgreSQL, and consider a secondary Redis node if retention requirements grow.

**No native partitioning sharding.** Redis Streams consumer groups do not auto-rebalance partitions across nodes the way Kafka does. Scaling horizontally requires client-side sharding logic (e.g., hash notification type to stream key). For the 5,000 ops/s target, a single notification node is sufficient, so this is a future concern.

**Weaker ordering guarantees than Kafka.** Redis Streams guarantees order within a single stream but has no cross-partition ordering. This is acceptable: per-task notification ordering is the requirement, not global ordering. Since each task ID maps to one stream partition, temporal ordering of notifications within a task is preserved.

**Not the industry standard for event sourcing.** Kafka dominates the event-streaming space for good reason — log compaction, infinite retention, and a richer ecosystem of connectors. If the team ever needs event sourcing for audit trails or CQRS, Kafka becomes the right tool. At that point, Redis Streams can act as a buffer while a parallel Kafka pipeline is built. This ADR does not foreclose that future migration.

---

## Alternatives Considered

### Apache Kafka

Kafka offers a durable, distributed commit log with partitioned consumer groups, replay from arbitrary offsets, log compaction, and a rich ecosystem (Kafka Connect, Schema Registry, ksqlDB). For high-throughput event streaming at enterprise scale, it is the gold standard.

**Why it was rejected for this context:**

*Operational complexity is mismatched to team size.* A production Kafka deployment requires a minimum of 3 brokers running KRaft (or ZooKeeper), topic tuning for partitions/replication, monitoring of consumer lag and ISR shrinks, and expertise in handling rebalance storms, unclean leader elections, and disk failure recovery. For a 6-person team with no infra engineer and no Kafka experience, this is a significant operational tax that diverts time from product work.

*Timeline incompatibility.* Building a production-grade Kafka pipeline in 2 weeks — including security (TLS, SASL/SCRAM), topic configuration, Python client integration with `confluent-kafka`, retry/dead-letter setup, and team training — is unrealistic for a team new to the technology. Redis Streams can reach the same point in 3 days.

*Cost pressure.* Self-hosted Kafka on AWS EC2 requires at least 3 `m6i.large` or `m6i.xlarge` instances for quorum, plus EBS volumes sized for retention. Managed Kafka (MSK) starts at ~$0.50/hr per broker (~$1,100/month for 3 brokers). Confluent Cloud is more expensive. Redis is already paid for; a dedicated notification Redis instance adds ~$50–100/month.

*Overkill at current scale.* Kafka's architectural strengths — multi-TB log retention, 100k+ msg/s throughput, replay across dozens of independent consumer groups — are not yet needed. The team would be paying complexity and cost for capacity it will not use for years. By the time those needs arise, a migration to Kafka can be planned deliberately, not rushed under the 2-week constraint.

*Exactly-once is not a differentiator here.* Kafka's exactly-once semantics (EOS) require enabling `enable.idempotence=true`, using Kafka transactions, and consuming via `read_committed` isolation — all of which add complexity. The simpler idempotency-key pattern used with Redis Streams achieves the same result for billing events with less moving parts. EOS in Kafka also does not prevent duplicate processing at the application layer; the consumer must still implement deduplication.

**Recommendation path:** Redis Streams now; re-evaluate Kafka in 12–18 months if notification volume exceeds 50k msg/s or event sourcing becomes a requirement.
