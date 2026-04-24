# ADR-001: Notification Subsystem — Redis Streams over Apache Kafka

## Status

Proposed

## Context

Our SaaS project management platform (85k MAU, ~2M tasks/month, 500 req/s peak) handles all notifications — emails, webhooks, and billing-critical events — synchronously inside the HTTP request cycle. This has caused:

- **Request timeouts**: Average notification latency 800ms, spiking to 8s at peak, blocking responses.
- **Silent failures**: No retry, no dead-letter queue. Dropped notifications are invisible.
- **Cascading failures**: Two incidents this year where slow webhook endpoints exhausted the DB connection pool, taking down unrelated features.
- **No delivery guarantees**: Billing notifications ("trial expired", "payment failed") have exactly-once requirements with zero enforcement.

We must decouple notification processing from request handling, add retry with exponential backoff, guarantee at-least-once delivery for billing events, support WebSocket push within two quarters, and absorb 10x traffic growth without re-architecting.

**Hard constraints:**

| Constraint | Detail |
|---|---|
| Team | 6 engineers (3 senior, 3 mid), no dedicated infra |
| Existing stack | Redis already in production (sessions, rate limiting); no Kafka experience |
| Time to value | ≤ 2 weeks before first working async notification |
| Budget | Modest — managed Confluent Cloud at full scale is not affordable |
| Delivery semantics | Exactly-once for billing notifications |

## Decision

**We choose Redis Streams.**

Redis Streams provides the core messaging primitives we need — durable append-only logs, consumer groups, pending-entry tracking for retry, and per-stream ordering — on infrastructure the team already operates. It satisfies the 10x scaling target (single-instance Redis handles ~1M ops/sec; our 10x peak is ~5,000 notifications/sec, well within capacity) and can be production-ready within the 2-week window without introducing a new distributed system.

Kafka is the stronger system on paper — superior long-term retention, native partition-level parallelism, and a mature ecosystem — but it is the wrong system for this team at this stage. The operational burden, knowledge gap, and timeline make it a net risk rather than a net gain.

### Justification by technical property

**Throughput & scaling to 10x**

Current peak: ~500 req/s. Not every request produces a notification; realistic peak notification rate is likely 200–400 msg/s. 10x of that is 2,000–4,000 msg/s. A single Redis instance handles orders of magnitude more. Sharding across multiple streams or migrating to Redis Cluster gives additional headroom. Kafka's design strength — multi-terabyte throughput across clusters — is overkill and unexercised at our scale.

**Consumer groups & delivery model**

Redis Streams consumer groups (XGROUP, XREADGROUP, XPENDING) provide the same logical model as Kafka: partitioned consumption, offset tracking per consumer, and claim/redelivery of messages from failed consumers via XPENDING + XCLAIM. This is sufficient to implement retry with exponential backoff: a consumer reads, processes, and XACKs on success; on failure the message stays in the pending list and is reclaimed after a timeout. We add a retry-count field to the message payload; on the Nth reclaim the message routes to a dead-letter stream.

**Exactly-once semantics for billing**

Neither Kafka nor Redis Streams provides true exactly-once delivery to external systems (email, webhooks). Kafka's exactly-once semantics (idempotent producer + transactions) apply only to Kafka-to-Kafka consume-transform-produce loops — they do not extend to side effects like HTTP calls. For billing notifications, we must solve exactly-once at the application layer regardless of broker choice:

1. **Transactional outbox pattern**: Write the notification to a PostgreSQL outbox table within the same transaction as the business event. A separate relay process tails the outbox and publishes to the Redis Stream. This guarantees the notification is published if and only if the business transaction commits.
2. **Idempotency keys**: Every billing notification carries a deterministic idempotency key (e.g., `billing:{org_id}:{event_type}:{period}`). The consumer deduplicates against a Redis SET or DB table before executing the side effect.
3. **At-least-once from broker + idempotent consumer = effective exactly-once.**

This works identically on Redis Streams or Kafka. The broker choice does not affect the outcome.

**Ordering guarantees**

Redis Streams guarantee insertion-order per stream. All notifications for a given tenant can be routed to a tenant-prefixed stream (e.g., `notifications:tenant:{id}`) to preserve per-tenant ordering. Kafka provides per-partition ordering; to get per-tenant ordering in Kafka you must key by tenant ID and accept the throughput limitation of a single partition per tenant. Both systems require the same trade-off; Redis Streams is simpler to configure.

**Message retention**

Redis Streams support MAXLEN trimming (count-based) or `MINID` trimming (time-based). We will configure `MAXLEN ~ 500000` (approximate trimming for performance) plus a 7-day MINID, giving us ample replay window for debugging and recovery at our volumes. Kafka's configurable long-term retention is superior for event-sourcing or audit-log use cases; we do not have that requirement — our PostgreSQL outbox serves as the durable record of record. After successful delivery and acknowledgment, the stream entry's value is purely for replay/debugging.

**Operational complexity**

This is the decisive factor. A production Kafka deployment requires:

- Brokers (3+ for fault tolerance), each needing JVM tuning, disk, and heap management
- ZooKeeper cluster or KRaft migration
- Topic/partition planning, replication factor configuration
- Monitoring: lag tracking (Burrow or equivalent), under-replicated-partition alerts, ISR alerts
- Ongoing operational incidents: leader elections, rebalances, disk pressure

With no dedicated infra engineer and zero Kafka experience, this is an unacceptable operational risk. Redis is already running, already monitored, and already understood by the team. Adding a stream is a configuration change, not a new distributed system.

**Setup time**

Redis Streams: add consumer group creation to the existing Redis instance, write a producer shim (XADD) and a consumer daemon (XREADGROUP). Realistic first working notification in 3–5 days.

Kafka: provision brokers (or an MSK cluster), learn and configure Kafka, write producers and consumers, load-test, harden monitoring. Bare minimum 3–4 weeks for a production-ready deployment — exceeding the 2-week constraint.

## Consequences

### Pros

- **Zero new infrastructure**. Redis is already in production with monitoring and runbooks. We add streams to the existing instance (or a dedicated Redis if isolation is preferred), not a new distributed system.
- **Fast time to value**. Producer (XADD) and consumer (XREADGROUP with XPENDING/XCLAIM retry loop) can be implemented in a few days. First async notification delivered within the 2-week window.
- **Team velocity**. No learning curve for a new technology. Redis tooling is already familiar; `redis-cli`, existing dashboards, and the team's operational intuition all apply.
- **Sufficient performance**. Single-instance Redis handles our 10x scaling target with ~250x headroom. If we eventually exceed single-instance capacity, Redis Cluster is a well-understood migration path.
- **Consumer group model**. XREADGROUP, XPENDING, and XCLAIM give us the same delivery/retry semantics we'd use in Kafka, at our scale.
- **Budget neutral**. No new infrastructure cost. If we later need a dedicated Redis for notifications, a single `cache.m6g.large` on ElastiCache is ~$150/month — orders of magnitude cheaper than a 3-broker MSK cluster.

### Cons

- **No native exactly-once**. Redis Streams provide at-least-once. Exactly-once for billing events must be implemented at the application layer (outbox + idempotency keys). This adds code complexity — but as noted, Kafka would require the same pattern for external side effects.
- **Retention is simpler but less flexible**. Redis Streams trim by count or age; there is no compacted-topic equivalent or long-term retention with log compaction. Our PostgreSQL outbox becomes the durable event store, which is a sound architectural choice but means the stream is a delivery mechanism, not an audit log.
- **No native partition-level parallelism**. A Redis Stream is a single partition. To scale consumer throughput, we must shard across multiple streams (e.g., `notifications:shard:0..N`). Kafka's automatic partition-to-consumer mapping is more ergonomic. At our volumes this is a minor inconvenience, not a blocker.
- **Single point of failure risk**. A single Redis instance is a SPOF. Mitigation: Redis Sentinel or ElastiCache Multi-AZ for automatic failover. This is simpler than Kafka replication but still requires planning.
- **Long-term ceiling**. If the company grows to millions of MAU with high-fanout event topologies (many consumer groups, event-sourcing, cross-service streaming), Redis Streams will become a limitation and Kafka (or a similar log-based system) will be the right choice. This ADR should be revisited if notification throughput exceeds ~100K msg/s or we adopt an event-driven microservices architecture.

## Alternatives Considered

### Apache Kafka

Kafka is the industry-standard distributed event streaming platform. We rejected it for this decision based on the following:

| Factor | Kafka Reality | Why It Loses |
|---|---|---|
| **Team expertise** | Zero Kafka experience | 2–4 week ramp + ongoing operational burden with no infra engineer |
| **Operational load** | 3+ brokers, ZooKeeper/KRaft, partition management, ISR monitoring | Unreasonable for a 6-person team without dedicated infra |
| **Setup time** | Minimum 3–4 weeks to production | Exceeds 2-week constraint |
| **Budget** | Self-managed: dev time + EC2 costs. Managed (MSK/Confluent): ~$500–1,500/month for a 3-broker cluster at our throughput | Outside budget for a team that cannot afford Confluent Cloud |
| **Exactly-once** | Only for Kafka-to-Kafka transactions | Does not solve external delivery; still needs application-level idempotency — same as Redis Streams |
| **Throughput advantage** | Millions of msg/sec in a cluster | 200–250x over-provisioned for our 4,000 msg/s 10x target |
| **Retention advantage** | Configurable, compacted, long-term | We use PostgreSQL outbox as the durable record; stream is a delivery channel, not an audit store |

Kafka is a technically superior messaging system at scale. If the company grows to a size where we have a platform/infra team, adopt event-driven microservices, or need cross-domain event streaming, we should write a new ADR to migrate. Today, it introduces risk and delay for capabilities we do not yet need.

### Other alternatives briefly considered and rejected

- **SQS/SNS**: Fully managed, low operational cost, but no consumer groups (SNS fan-out + SQS per consumer), no native ordering guarantees, and per-request pricing becomes expensive at volume. Also requires exactly-once to be solved at the app layer.
- **RabbitMQ**: Mature, supports retry/dead-letter exchanges, but introduces a new system to operate (Erlang runtime, different monitoring) with similar learning curve to Kafka. Does not solve the "new infra" problem.
- **Celery/Redis (list-based)**: Already possible with our Redis, but Redis Lists (BLPOP) lack consumer groups, per-message acknowledgment, and pending-entry tracking. Streams are a strictly superior primitive for this use case.