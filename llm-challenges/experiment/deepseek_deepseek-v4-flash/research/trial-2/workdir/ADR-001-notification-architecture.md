# ADR-001: Notification Subsystem — Async Decoupling with Redis Streams

**Status:** Proposed

## Context

The Notifier subsystem sends email and webhook notifications when tasks are created, updated, assigned, or completed. These calls are currently synchronous inside the Flask HTTP request cycle, causing:

- **Request timeouts**: 800ms average, 8s spikes during peak hours (~500 req/s).
- **Silent failures**: No retry mechanism. Downstream email providers or webhook endpoints that fail cause permanent data loss.
- **Cascading failures**: Two incidents this year where a slow webhook endpoint exhausted the PostgreSQL connection pool, taking down unrelated features.
- **No delivery guarantees**: Billing-critical notifications ("trial expired", "payment failed") require at-least-once or exactly-once delivery. The current system provides neither.

The system must be decoupled into an async pipeline with retry, exponential backoff, and delivery guarantees.

### Constraints

- **Team**: 6 engineers (3 senior, 3 mid-level). No dedicated infrastructure engineer.
- **Existing infrastructure**: Redis (session storage, rate limiting) already runs in production. PostgreSQL primary + one read replica. 4 nginx-backed web servers on AWS.
- **Experience**: Zero Kafka knowledge on the team. Redis is already in day-to-day use.
- **Timeline**: Must deliver value within 2 weeks. Cannot tolerate a multi-month infrastructure project before the first notification flows asynchronously.
- **Budget**: Modest. Managed Confluent Cloud at full production scale is unaffordable.
- **Scale target**: Current metrics — 85k MAU, ~2M tasks/month, 500 req/s peak. Must handle 10x growth without re-architecting.
- **Future requirement**: Real-time WebSocket push notifications within 2 quarters.

## Decision

**Use Redis Streams**, not Apache Kafka, as the notification message broker.

The application will push notification events to a Redis Stream upon task state changes. A dedicated background worker process (Python) will consume the stream via consumer groups, dispatch emails and webhooks asynchronously, and acknowledge messages only after successful delivery. Failed deliveries enter a retry stream with exponential backoff; persistently failing messages are moved to a dead-letter stream for manual inspection.

For billing notifications requiring exactly-once delivery, an idempotency key scheme on the consumer side (deduplication via the existing PostgreSQL primary key) guarantees exactly-once semantics at the point of external side effects.

## Consequences

### Pros

1. **Zero new infrastructure, immediate time-to-value.** Redis is already deployed and operated for session storage and rate limiting. Adding Streams requires no new services, no new instances, no new monitoring. A working prototype can ship within days, not weeks. This meets the 2-week delivery constraint.

2. **Operational simplicity for a 6-person team.** The team already understands Redis — connection pooling, memory management, persistence configuration. There is no ZooKeeper/KRaft cluster to manage, no broker rebalancing to debug, no partition assignment strategy to tune. When the on-call engineer gets paged at 2 AM, they are debugging a system they already know.

3. **Adequate throughput at current and 10x scale.** Redis Streams comfortably handles 10k–100k messages/second on modest hardware. Current peak is 500 req/s. At 10x growth (5k req/s), Redis Streams still operates at less than 10% of its ceiling. The throughput argument for Kafka only activates at a scale this team may never reach.

4. **Consumer groups with acknowledgment semantics.** Redis Streams' `XREADGROUP` with `XACK` provides the same at-least-once delivery primitive that Kafka consumer groups offer. Messages are redelivered if a consumer crashes before acknowledgment. This satisfies the at-least-once requirement.

5. **Natural fit for WebSocket push.** Redis pub/sub is already the simplest path to real-time fan-out. Adding a WebSocket server that subscribes to a Redis channel fed by the Stream consumer is straightforward and well-documented. Kafka would require a separate bridge for this.

6. **Cost.** Zero additional infrastructure cost today. Kafka would require a minimum of 3 broker instances (plus ZooKeeper nodes, or KRaft quorum) for production-grade deployment — a significant recurring expense on a modest budget.

### Cons

1. **No native partitioning.** Redis Streams operate within a single Redis instance. Kafka can partition a topic across many brokers, achieving unlimited horizontal scale. At extreme scale (100k+ messages/second sustained, or multi-terabyte retention), a single Redis instance becomes a bottleneck. Mitigation: use multiple streams sharded by tenant ID or notification type, with consistent-hashing consumers. This adds application-level complexity that Kafka handles natively.

2. **Message retention bounded by memory, not disk.** Kafka retains messages on disk for configurable periods regardless of consumer throughput. Redis Streams are bound by `maxmemory` policy — if consumers fall far behind, messages are evicted. Mitigation: (a) configure a dedicated Redis instance or logical database for streams with generous `maxmemory` and `allkeys-lru` disabled; (b) implement a dead-letter pattern aggressively; (c) the notification workload is transient (messages are valuable for minutes, not days), so bounded retention is acceptable.

3. **No native exactly-once semantics.** Redis Streams do not have an equivalent of Kafka's idempotent producer + transactions for end-to-end exactly-once. However, this is less impactful than it seems: Kafka's EOS guarantees apply within Kafka's ecosystem (consume-process-produce loop). External side effects (calling an email API or a webhook endpoint) require consumer-side idempotency regardless of broker choice. Our approach of deduplicating by idempotency key in PostgreSQL gives exactly-once semantics at the side-effect boundary, which is where it actually matters.

4. **Consumer group rebalancing is more primitive.** When a consumer joins or leaves a Redis consumer group, messages in flight may be re-delivered more aggressively than Kafka's cooperative rebalancing. Mitigation: make notification consumers idempotent, which we need anyway for billing guarantees.

5. **Long-term migration path if Kafka becomes necessary.** If the team grows to dozens of services and the throughput exceeds Redis Streams' ceiling, a migration to Kafka is a non-trivial project. Mitigation: this is years out at projected growth rates, and the team will have Kafka expertise and headcount by then. The Streams abstraction is similar enough (consumer groups, acknowledgment, offset tracking) that the architectural pattern transfers.

## Alternatives Considered

### Apache Kafka

**Rejected.** Kafka is the technically superior message broker for massive-scale, multi-subscriber event streaming. It offers:

- Durable disk-based retention with configurable TTL and compaction.
- Native partitioning for unbounded horizontal scaling.
- Mature consumer groups with cooperative rebalancing.
- Idempotent producer + transactions for exactly-once guarantees within the ecosystem.

These strengths are decisive when operating at the scale of thousands of partitions, hundreds of consumers, and petabyte-level retention. They are liabilities for a 6-person team operating at 500 req/s peak.

The concrete rejection reasons:

1. **Operational complexity.** A production Kafka deployment requires: 3+ brokers (minimum for quorum), ZooKeeper or KRaft controller quorum, topic partitioning strategy, partition rebalancing tuning, monitoring for ISR (in-sync replica) status, leader election, and consumer lag. Each of these is a failure mode the team has no experience debugging. Redis Streams adds zero new operational surfaces.

2. **No delivery within 2 weeks.** Standing up production-grade Kafka (security configurations, TLS, SASL/SCRAM, broker sizing, persistent volumes, backup strategy) would consume the entire 2-week window before a single notification message flowed. Redis Streams can be shipping notifications in 2 days.

3. **Team skill mismatch.** Zero Kafka experience on a 6-person team with no dedicated infrastructure engineer is a recipe for silent operational debt — topics with too few partitions, incorrectly tuned retention, consumer groups that never rebalance correctly. Redis is already in the team's toolbox.

4. **Cost overhead.** Self-hosted Kafka requires at least 3 EC2 instances (brokers) plus ZooKeeper/KRaft nodes, plus EBS volumes sized for retention. Managed alternatives (Confluent Cloud, MSK) cost $500–$2,000+/month at production scale. This is wasteful for the current workload.

5. **Overkill for the workload.** Kafka's design targets 100k–1M messages/second across multiple subscribers. The notification subsystem produces at most a few hundred messages per second at peak. Redis Streams handles this trivially with sub-millisecond latency, lower operational cost, and simpler code.

### pg_notify / PostgreSQL LISTEN/NOTIFY

**Rejected briefly.** While PostgreSQL is already the application database, `LISTEN/NOTIFY` has critical limitations: no message persistence (notifications are lost if no listener is connected), a hard 8KB message size limit, and no consumer group acknowledgment model. It requires an external queue for retry and dead-letter handling, which means maintaining two systems anyway. It does not meet the at-least-once delivery or retry requirements.

## Key Risks and Mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Redis Stream memory exhaustion if consumers fall behind | Medium | Dedicated Redis instance for streams; monitor `XLEN` and consumer lag; alert before `maxmemory` is reached |
| Idempotency key collision for billing notifications | Low | Use deterministic key based on `notification_type + task_id + timestamp_bucket`; unique constraint in PostgreSQL ensures exactly-once |
| Redis single-instance ceiling hit at extreme growth | Low (3+ years out) | Shard by notification type across multiple streams; migration to Kafka documented as future option |
| WebSocket subscriber scaling | Medium | WebSocket servers connect via Redis pub/sub; horizontal scale by adding more WS server instances behind a load balancer |

## Decision Summary

Redis Streams is the correct choice for this team, at this scale, under these constraints. It delivers decoupling, retry, at-least-once guarantees, and a WebSocket path within the 2-week timeline — using infrastructure the team already runs and understands. Kafka's advantages in partitioning, retention depth, and exactly-once semantics are real but irrelevant to a 6-person team handling hundreds of messages per second.

We reserve the right to revisit this decision when the team has grown, the infrastructure engineer headcount has increased, and the throughput exceeds what a single Redis instance can sustain.
