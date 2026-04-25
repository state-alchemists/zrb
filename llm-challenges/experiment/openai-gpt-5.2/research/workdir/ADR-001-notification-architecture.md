# Title
Notification Subsystem Event Backbone: Redis Streams vs Apache Kafka

# Status
Proposed

# Context — the problem and constraints
We currently send emails and webhooks synchronously inside the Flask HTTP request cycle. This is creating (a) request timeouts/latency spikes, (b) silent drops when downstream providers are unavailable, (c) cascading failures (slow webhook endpoints exhausting shared resources), and (d) missing delivery guarantees for billing-critical events.

We need an asynchronous notification pipeline that:
- Decouples notification delivery from HTTP requests
- Supports retries with exponential backoff and a dead-letter strategy
- Provides **at-least-once** delivery for most events and **exactly-once semantics for billing notifications** (exactly-once “where feasible”)
- Can support real-time push (WebSockets) within ~2 quarters
- Can scale to ~10x current traffic without another major re-architecture

Constraints:
- Team is 6 engineers, no dedicated infrastructure engineer
- We already operate Redis in production; no Kafka experience today
- We must deliver initial value within **2 weeks** (setup + migration)
- Budget is modest; cannot rely on full-scale managed Confluent Cloud

We are evaluating two options for the notification subsystem event backbone:
1) Apache Kafka
2) Redis Streams

# Decision — which option you choose and a clear justification
**Choose: Redis Streams (with consumer groups) as the notification event backbone.**

Justification:
- **Fastest path to value under constraints**: We already run Redis. Adding Redis Streams requires incremental operational work (persistence settings, monitoring, sizing) but avoids standing up and operating a Kafka cluster (brokers, controllers, ZooKeeper/KRaft, storage tuning, partitioning strategy, schema evolution tooling) with a team that has **no Kafka experience** and **no infra specialist**, within a **2-week** window.
- **Consumer groups and ordering are sufficient for notifications**: Redis Streams provide consumer groups with explicit ACKs and a pending entries list (PEL). Ordering is preserved **per stream** (and effectively per key/stream shard we design), which is typically adequate for notification flows (e.g., per user, per task, or per account ordering).
- **Message retention is controllable**: Streams support trimming (MAXLEN) and retention policies. For notifications we generally need short-to-medium retention (hours/days) plus durable storage of billing delivery state in Postgres; we do not need Kafka’s long-term replay-by-offset for months/years as a primary requirement.
- **Throughput fits the current and near-term scale**: At ~500 req/s peak today and a 10x target (~5,000 events/s worst-case depending on event fan-out), Redis Streams can handle this with appropriate sizing and stream key sharding. Kafka can handle far higher throughput, but that headroom comes with operational overhead we cannot absorb now.
- **Exactly-once semantics are not “free” in either option; implement at the application layer**: Kafka’s exactly-once semantics (EOS) are primarily about *processing + producing to Kafka* with transactions and idempotent producers, and do not guarantee exactly-once delivery to external side effects like email/webhook providers without idempotency. Redis Streams also do not provide end-to-end exactly-once. Given the requirement “must maintain exactly-once semantics for billing notifications,” the practical solution in both cases is:
  - Use an **outbox / idempotency key** pattern persisted in PostgreSQL (e.g., `billing_notification_id` with a unique constraint), and ensure workers are idempotent when performing side effects.
  - Process events **at-least-once** from the stream and make external delivery exactly-once *by deduplication* and atomic state transitions in Postgres.

In short: Redis Streams meets the functional needs (async, retries, consumer groups, ordering) with minimal setup and acceptable scale, while keeping the team within operational and time/budget constraints.

# Consequences — pros AND cons of your decision
## Pros
- **Low operational complexity**: One fewer distributed system to operate. We extend an existing Redis deployment rather than introducing Kafka.
- **Meets the immediate goal quickly**: Realistic to implement stream producers in the Flask monolith and workers (e.g., Celery/RQ/custom) within 2 weeks.
- **Built-in consumer group mechanics**: ACK-based processing, visibility into pending messages (PEL), and the ability to claim stuck messages supports robust retries.
- **Backpressure and isolation**: Notification work moves off the request path; slow webhooks no longer exhaust web server connection pools.
- **Good fit for real-time push**: Redis is already commonly used as a pub/sub and coordination backend; Streams can feed WebSocket notification workers with low latency.

## Cons
- **Weaker long-term retention and replay model than Kafka**: Redis Streams are not designed for multi-month durable log retention with cheap replay at scale. Trimming and memory/disk constraints require careful policy.
- **Ordering and scaling require deliberate stream key design**: Global ordering across all notifications is not feasible; we must define ordering domains (per account/user/task) and potentially shard across multiple streams.
- **Operational coupling to Redis**: Redis is currently used for sessions/rate limiting; adding Streams increases Redis criticality. We must harden Redis (persistence, backups, monitoring, resource isolation) to avoid broader impact.
- **Exactly-once still requires application-level guarantees**: Billing notifications will require Postgres-backed idempotency/outbox logic and careful worker implementation.
- **Fewer ecosystem tools than Kafka**: Kafka has mature tooling for schema registry, connectors, and stream processing. With Redis Streams we will build more in-house (DLQ streams, metrics, management scripts).

# Alternatives Considered — why you rejected the other option
## Apache Kafka (rejected)
Kafka provides strong primitives for high-throughput event pipelines:
- **Throughput & partition scaling**: Excellent horizontal scaling via partitions.
- **Ordering guarantees**: Strong ordering within a partition.
- **Retention & replay**: First-class long retention with replay by offset.
- **Consumer groups**: Mature, reliable consumer group rebalancing.
- **Exactly-once semantics (EOS)**: Idempotent producers and transactions can provide exactly-once processing semantics within Kafka.

We rejected Kafka for this system *at this time* because:
- **Operational complexity is too high for team size and timeline**: Running Kafka reliably on AWS without a dedicated infra engineer (and with no prior Kafka experience) is significant work: cluster sizing, storage/IO tuning, partition strategy, upgrades, monitoring, alerting, and incident response.
- **Budget constraint rules out the simplest path**: Managed Kafka (e.g., Confluent Cloud at full scale) is not affordable; self-managed Kafka becomes the burden.
- **Time-to-value mismatch**: Meeting the “deliver value within 2 weeks” constraint while also learning and production-hardening Kafka is unlikely.
- **Kafka EOS does not solve end-to-end exactly-once for external notifications**: Even with Kafka transactions, email/webhook delivery still needs idempotency/deduplication. Therefore Kafka’s marquee advantage (EOS) does not fully satisfy the “billing exactly-once” requirement without additional application-layer work—work we must do anyway.

Given current constraints, Kafka is better positioned as a future evolution if we later need multi-region durability, very large fan-out volumes, long-term event retention/replay, or an organization that can support Kafka operations.
