# ADR-001: Notification Subsystem Architecture

**Status:** Proposed

## Context

The Notifier subsystem runs synchronously inside the Flask HTTP request cycle, causing request timeouts (800ms average, 8s spikes), silent failures when email providers or webhook endpoints are down, and cascading failures from connection pool exhaustion. Billing-critical notifications require reliable delivery, and the team plans to add WebSocket push notifications within two quarters.

The system serves 85k MAU, 2M tasks/month, and peaks at 500 req/s. The engineering team is 6 people (3 senior, 3 mid-level) with no dedicated infrastructure engineer. Redis is already in production for session storage and rate limiting. No one on the team has Kafka experience. Budget is modest — managed Confluent Cloud is out of reach.

The notification subsystem must decouple from the HTTP request cycle, support retry with exponential backoff, guarantee at-least-once delivery (exactly-once for billing), handle 10x traffic growth, and ship value within 2 weeks of setup time.

## Decision

**Adopt Redis Streams for the notification subsystem.**

Redis Streams provides the async message queue primitive we need (XADD to enqueue, XREADGROUP for consumer groups, XPENDING/XAUTOCLAIM for retry) while adding zero new infrastructure to operate. The team already manages Redis in production — the learning curve is limited to the Streams data structure and consumer group protocol, which a senior engineer can prototype in 2–3 days. At 500 req/s peak (5k req/s at 10x growth), a single Redis node handles the throughput comfortably; Redis Streams sustains ~100k msg/s on modest hardware, giving us a 20x headroom factor above the 10x target.

For exactly-once semantics on billing notifications, we combine Redis Streams consumer groups with application-level idempotency: consumers track processed message IDs in a Redis Set with an expiry TTL, and discard duplicates before processing. This pattern is simpler and more auditable than Kafka's native exactly-once semantics (transactions + idempotent producer), which requires careful handling of its own failure modes (transaction coordinator failures, zombie fencing).

WebSocket push integrates naturally — a background consumer reads from the same stream and fans out to connected WebSocket clients via Redis Pub/Sub channels or a local in-process hub. No second message broker is needed.

## Consequences

### Pros

- **Zero new infrastructure.** Redis is already deployed, monitored, and backed up. Adding Streams to the existing Redis instance costs nothing in additional operational footprint. Backup/restore procedures already cover the notification data.

- **Fast time-to-value.** A senior engineer can ship a working prototype (Flask → Redis Streams → email worker) in under a week. The full migration fits within the 2-week constraint. Consumer group code is ~50 lines of Python using `redis-py`'s `XADD` and `XREADGROUP` methods.

- **Low team risk.** Every engineer on the team understands Redis basics. The Streams API has a gentle learning curve — consumer groups, pending entries, and message claiming are well-documented and intuitive. No JVM tuning, no partition rebalancing, no Zookeeper/KRaft to learn.

- **Sufficient throughput headroom.** Single-node Redis Streams handles ~100k msg/s. At 10x growth (5k req/s peak, roughly 15k notifications/s assuming webhook + email fan-out), we operate at 15% of single-node capacity. If needed, Redis Cluster shards streams across nodes transparently.

- **Exactly-once via idempotency.** Tracking processed message IDs in a Redis Set with a TTL equal to the maximum retry window gives us exactly-once delivery without distributed transactions. A consumer checks the Set before processing: if the ID exists, skip; if not, process and add. This pattern is well-understood, testable, and survives consumer crashes.

- **Natural WebSocket path.** Redis Pub/Sub (or a dedicated stream per WebSocket topic) is the standard pattern for fanning out real-time updates. We already have Redis — no additional infrastructure needed when WebSocket support ships in Q2.

- **Retry and dead-letter queue.** Consumer groups track pending entries via XPENDING. Failed messages can be inspected, retried, and moved to a dead-letter stream after exhausting the retry budget. The pattern is built-in, not bolt-on.

### Cons

- **In-memory retention limits.** Redis streams live primarily in memory (backed by RDB/AOF snapshots). Long-term message retention is expensive. For notification delivery we only need hours of retention (retry window + monitoring), so this is acceptable. For audit trail requirements, consumers archive to PostgreSQL or S3 after delivery.

- **No native exactly-once.** Redis Streams does not provide atomic exactly-once delivery. We must implement idempotency at the consumer layer. This is straightforward (Set-based dedup) but must be applied consistently to every consumer, including the WebSocket fan-out consumer. Miss it once and we deliver a billing notification twice.

- **Consumer group rebalancing is manual.** Kafka auto-rebalances partitions across consumers in a group. Redis requires the operator to manage consumer registration and handle reconnection manually. For a notification subsystem with 2–4 consumer instances, this is a minor operational note — not a burden — but it becomes noticeable if we scale to dozens of consumers.

- **Not the industry standard for event streaming.** Kafka is the dominant choice for event-driven architectures at scale. Hiring engineers in the future may question Redis Streams. Documentation, tutorials, and community support for Redis Streams are thinner than Kafka's. This is a cultural cost, not a technical one.

## Alternatives Considered

### Apache Kafka (Rejected)

Kafka delivers industry-leading throughput (millions of msg/s), persistent disk-backed log storage with configurable retention, strong partition-level ordering, mature consumer group rebalancing, and native exactly-once semantics via transactions and idempotent producers. For a team with Kafka experience and the operational bandwidth to run a cluster, it is the superior technical choice.

We reject Kafka for four reasons that are decisive given our constraints:

1. **Operational overhead.** A production Kafka deployment requires a minimum of 3 brokers (for replication), 3 Zookeeper nodes (or KRaft controllers), careful JVM heap tuning (heap sizing, GC tuning, page cache sizing), and ongoing partition management (leadership rebalancing, ISR monitoring, log compaction tuning). This is a full-time operational burden for a team of 6 with no dedicated infra engineer. It directly violates the 2-week setup constraint — a production-ready Kafka cluster takes 3–4 weeks to provision, tune, and validate even on managed services like MSK.

2. **No existing team expertise.** Zero members of the 6-person team have Kafka production experience. The learning curve spans not just the programming API but the operational model: partition strategy, replication factor, min.insync.replicas, consumer rebalance protocol, and the monitoring surface (consumer lag, ISR state, unclean leader elections). This is a multi-week ramp-up before any production code is written.

3. **Budget.** Self-managed Kafka requires at minimum 3 EC2 instances of moderate size (m6i.large or similar) for brokers, plus Zookeeper nodes — roughly $800–1,200/month in compute costs, plus EBS storage for retention. Managed MSK starts at ~$0.50/hr per broker (~$1,100/month for a 3-broker cluster). Managed Confluent Cloud's pricing is higher. Redis Streams on the existing Redis instance adds $0 in new infrastructure cost.

4. **Over-engineered for our scale.** At 500 req/s (5k at 10x), Kafka's throughput advantage is irrelevant. We don't need log compaction, infinite retention, or multi-datacenter replication. We need a reliable, retryable message queue that the team can ship and operate in 2 weeks. Kafka brings a jet engine to a bicycle problem.

The only scenario where Kafka becomes necessary is if the notification subsystem evolves into a full event-sourced audit log requiring years of replayable retention at millions of events/second. That is outside the 10x growth target and beyond the scope of this ADR. We can migrate to Kafka at that point if needed.
