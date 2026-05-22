# ADR-001: Notification Subsystem — Async Architecture

**Status:** Proposed

## Context

The SaaS project management platform (85k MAU, ~2M tasks/month, 500 req/s peak) couples notification delivery — email and webhooks — directly into the HTTP request cycle. This causes:

- **Request timeouts**: Average latency 800ms, spikes to 8s during peak as email provider or webhook endpoint latency dominates the user-facing response.
- **Silent failures**: Failed deliveries (downstream down, rate-limited, 5xx) are dropped. No retry, no dead-letter queue, no observability gap.
- **Cascading failures**: Two production incidents where a single slow webhook endpoint exhausted the connection pool, collapsing unrelated request paths.
- **No delivery guarantees**: Billing-critical notifications ("trial expired", "payment failed") require exactly-once delivery; the synchronous path provides neither at-least-once nor deduplication.

### Constraints

| Constraint | Detail |
|---|---|
| Team size & skill | 6 engineers (3 senior, 3 mid), no dedicated infra or SRE. No Kafka experience. |
| Existing infrastructure | Redis already in production (session storage, rate limiting). PostgreSQL primary + one replica. |
| Time-to-value | Must deliver measurable improvement within 2 weeks of start. |
| Budget | Modest. Managed Confluent Cloud is unaffordable at full scale. |
| Scaling target | 10x traffic growth (5,000 req/s peak) without re-architecting. |
| Exactly-once | Required for billing notifications; at-least-once acceptable for general notifications. |
| Near-term roadmap | Real-time WebSocket push within 2 quarters. |

## Decision

**Adopt Redis Streams as the notification backbone.**

HTTP request handlers will produce notification events to Redis Streams. A set of lightweight Python worker processes (one per notification channel: email, webhook, and later WebSocket) consume via `XREADGROUP` with consumer groups. Failed deliveries are retried with exponential backoff via a pending-entry list (`XPENDING`) and a re-delivery stream that functions as a dead-letter queue after a configurable max-retry threshold. Billing notifications carry an idempotency key stored in a Redis Set (with TTL) to achieve exactly-once processing semantics at the consumer level.

### Why Redis Streams and not a simpler queue (e.g., Redis Lists / RQ / Celery)?

Redis Lists or RQ/Celery atop Redis can provide async delivery, but they lack three properties we need:

1. **Consumer groups** — multiple workers can consume the same stream without message duplication. Lists require manual partitioning or risk duplicate delivery.
2. **Message acknowledgment** — `XACK` lets the consumer signal successful processing. Unacked messages remain in the pending list for inspection and replay. Lists have no native ack mechanism; a popped message is gone.
3. **Time-based retention** — streams can retain messages indefinitely (or by `MAXLEN ~ N`) without a separate persistence layer. Lists are ephemeral FIFO buffers.

For these reasons, Redis Streams are the minimal data structure that satisfies our reliability requirements without importing a new system.

## Consequences

### Pros

- **Zero new infrastructure**: Redis is already deployed, monitored, and backed up. The team already knows its operational characteristics (memory sizing, persistence, failover).
- **Fast time-to-value**: A basic producer-consumer loop using `redis-py` and `XADD`/`XREADGROUP` can be built, tested, and deployed within 1 week. The 2-week deadline is easily met.
- **Consumer groups out of the box**: Multiple workers per notification channel (email, webhook) can scale independently. `XREADGROUP` assigns messages to consumers, and `XPENDING` + `XCLAIM` handle worker failure and message rebalancing.
- **At-least-once delivery**: Workers must `XACK` after successful processing. Crashed workers leave messages in pending state; a reaper process claims and retries them.
- **Exactly-once for billing**: Combine two mechanisms: (a) an idempotency key (UUID v4 generated at the producer, scoped to the billing event source + event ID), (b) a consumer-side dedup check against a Redis Set with 24-hour TTL before processing. This achieves exactly-once without transactional streams (Kafka's approach) while adding only ~2ms per dedup check.
- **Retry with backoff**: Failed deliveries are re-added to a retry stream with exponential backoff. After `N` retries (configurable per channel, e.g., 5 for billing, 3 for general), the message moves to a dead-letter stream for manual inspection.
- **Natural fit for WebSocket push**: Redis Pub/Sub can fan out stream entries to multiple WebSocket server processes. This is a well-trodden pattern (used by Socket.IO, Phoenix Channels, and others) and will meet the 2-quarter roadmap.
- **Adequate throughput**: Redis Streams handle ~100k–200k writes/second on modest hardware. At 500 req/s → 5,000 req/s target, we are well within safe margins with headroom for 4× traffic beyond the 10× target.
- **Low operational burden**: No new brokers, ZooKeeper/KRaft clusters, partition rebalancing, or monitoring surfaces. Redis memory sizing is the primary concern — estimate ~200 bytes/notification (event payload + metadata) × ~6M notifications/month peak → ~1.2 GB/month. A `maxmemory` policy of `allkeys-lru` with monitoring alerts is sufficient.

### Cons

- **No native exactly-once**: Redis Streams provides at-least-once delivery via consumer groups. Exactly-once requires the consumer-side idempotency layer described above. This is technically straightforward but adds code that must be maintained and audited.
- **Memory-bound retention**: Unlike Kafka's disk-backed log, Redis Streams live in memory. A sustained traffic spike combined with a prolonged consumer outage could cause memory pressure if `MAXLEN` is not tuned. Mitigated by: (a) `MAXLEN ~ 100000` cap per stream, (b) a fast-consuming delivery guarantee (notifications are time-sensitive — hours, not days), (c) CloudWatch/Redis `INFO` memory alerts.
- **No cross-stream ordering**: Messages on different streams (email vs webhook) have no ordered relationship. This is acceptable — notification channels are independent by nature.
- **Re-architecture at extreme scale**: At ~100× current traffic (50,000 req/s+) Redis Streams would require clustering (Redis Cluster) and careful slot/hash-tag design. This is a future concern, not a present one, and clustering Redis is a known, documented path.
- **No managed Kafka ecosystem**: No Kafka Connect for sinks to S3/data warehouse, no Schema Registry. For our current needs (simple produce-consume) this is irrelevant, but it constrains future event-sourcing or CQRS ambitions without a migration.

## Alternatives Considered

### Apache Kafka

**Rejected** because the team and operational constraints make it infeasible in the required timeframe.

- **Operational complexity**: Kafka requires at minimum a 3-broker cluster with ZooKeeper (or KRaft in newer versions). This means learning broker configuration, partition assignment, rebalancing protocols, min.insync.replicas tuning, log compaction, and monitoring JMX metrics — none of which the team has prior experience with. For a 6-person team with no infra engineer, this represents a significant ongoing burden.
- **Time-to-value**: A production-ready Kafka deployment (broker provisioning, topic configuration, producer/consumer library integration, monitoring, backup, disaster recovery) would take 4–6 weeks at minimum given the learning curve. This exceeds the 2-week constraint by 2–3×.
- **Overkill at current scale**: Kafka excels at 100k+ msg/s, multi-subscriber fan-out, and long-term log storage. Our peak is 500 msg/s today, 5,000 msg/s at the 10× target. Redis Streams handles this comfortably at a fraction of the operational cost.
- **Budget**: Self-hosted Kafka is cheap (EC2 cost), but the *operational* cost — engineer time spent on broker management, partition tuning, rebalancing incidents — is the real expense. Managed MSK adds $200–600/month for a modest cluster. Confluent Cloud at full scale is out of budget. Neither eliminates the knowledge gap.
- **Native exactly-once**: Kafka's exactly-once semantics (idempotent producer + transactions) are a genuine strength. However, they come with caveats: transactions reduce throughput, require careful configuration of `isolation.level`, and are difficult to debug when they fail. The idempotency-key approach on Redis Streams achieves the same outcome more simply and is easier to reason about.
- **Not a bad choice overall** — Kafka is a fine technology and would serve the platform well at 50×–100× current scale. At today's scale and team composition, it is the wrong tool for the problem.

### Amazon SQS + SNS

**Rejected** because of throughput limits, ordering restrictions, and cost at target scale.

- SQS FIFO supports exactly-once but limits throughput to 300 msg/s (batch) / 30 msg/s (non-batch) without requesting a limit increase.
- Standard SQS offers at-least-once but no ordering guarantees — webhook delivery order matters for certain event types (e.g., "task completed" should not arrive before "task started").
- Cost at 10× scale: ~$6M notifications/month → ~$30–60/month in SQS requests, plus $20–40/month for SNS. Manageable, but the ordering and throughput constraints make it less suitable than Redis Streams.
- No natural WebSocket fan-out — would require a separate transport for the 2-quarter WebSocket goal.

### Amazon MQ (RabbitMQ)

**Rejected** because it adds a new infrastructure dependency (new AMQP cluster to operate) without providing durable log semantics, consumer groups, or time-based retention. RabbitMQ is consumption-based (message is removed after ack), making replay and dead-letter patterns more cumbersome than Redis Streams' retained log.

### Celery + Redis (broker)

**Rejected** because Celery is not a good fit for notification workloads. Celery is designed for background task execution; its retry model is task-level (raise `retry` within the task), not message-level. Dead-letter queues require custom extensions. Monitoring task-state overhead adds latency. A purpose-built consumer group pattern with Redis Streams provides more control over delivery guarantees, retry semantics, and observability.

---

*Decision made: 2026-05-22. Proposed by platform team.*
