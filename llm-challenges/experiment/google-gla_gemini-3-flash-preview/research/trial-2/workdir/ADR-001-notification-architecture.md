# ADR-001: Notification Subsystem — Redis Streams over Apache Kafka

**Status:** Proposed

---

## Context

Our SaaS project management platform (85k MAU, ~2M tasks/month, 500 req/s peak) handles notifications synchronously inside the HTTP request cycle. This causes request timeouts (avg 800ms, spikes to 8s), silent failures with no retry, and cascading incidents from slow webhook endpoints. We need an async notification pipeline that decouples delivery from request processing.

**Key requirements:**
- Decouple notification dispatch from the HTTP request cycle
- Support retry with exponential backoff and dead-letter queues
- At-least-once delivery across the board; exactly-once for billing-critical events
- Add WebSocket push notifications within two quarters
- Handle 10x traffic growth without re-architecting

**Constraints that drive this decision:**
- Engineering team of 6 (3 senior, 3 mid-level), no dedicated infrastructure engineer
- Redis already in production for session storage and rate limiting
- Zero Kafka experience on the team
- Must ship value within two weeks of starting
- Budget is modest — managed Confluent Cloud at full scale is not an option
- Billing notifications require exactly-once semantics

---

## Decision

**We will use Redis Streams as the notification backbone.**

Apache Kafka was the primary alternative. Redis Streams wins on every constraint that matters for this team, at this stage, with this traffic profile — without sacrificing the ability to migrate to Kafka later if traffic grows beyond Redis's capabilities.

### Key technical justification

| Property | Redis Streams | Kafka | Decision driver |
|---|---|---|---|
| **Throughput at our scale** | ~100k ops/s on single node | ~1M msgs/s on cluster | Both exceed 500 req/s (or 5k at 10x). Throughput is not a differentiator. |
| **Ordering guarantees** | Per-stream ordering preserved | Per-partition ordering preserved | Equivalent for our use case (task-scoped ordering) |
| **Message retention** | Configurable via MAXLENGTH/MAXAGE + RDB/AOF persistence | Disk-based with configurable retention (time/size), full replay | Kafka wins on replay; Redis retention is sufficient for our retry windows (hours, not weeks) |
| **Consumer groups** | Native XREADGROUP with competing consumers, pending entry list, auto-claim | Mature consumer groups with rebalance protocol | Both support the competing-consumers pattern needed for retry/DLQ |
| **Exactly-once semantics** | At-least-once only; consumer must implement idempotency | Idempotent producer + transactional API | Kafka wins natively, but idempotent consumers at the billing layer achieve the same outcome |
| **Operational complexity** | Single process, already running, familiar to the team | Requires KRaft cluster (min 3 nodes), JVM tuning, partition management, rebalancing, monitoring | **Redis wins decisively** — no new infrastructure, no new operational surface |
| **Time to value** | Prototype in a day, ship in a week | 3–6 weeks for provisioning, learning, migration, and hardening | Redis wins decisively |
| **WebSocket push readiness** | Redis Pub/Sub is already available for broadcasting to WS servers | Requires additional integration (KSQL, bridge service) | Redis wins |

### Addressing the exactly-once gap

Kafka's native exactly-once semantics is its strongest advantage here. However, we can achieve effectively-exactly-once delivery for billing notifications using a well-established pattern:

1. **Redis Streams provides at-least-once delivery** via consumer group acknowledgments (XACK).
2. **The billing consumer implements idempotency**: deduplicate by event ID before applying state changes, and use PostgreSQL `ON CONFLICT DO NOTHING` / upsert semantics for the actual writes.
3. **In-flight tracking via pending entry list** (XPENDING) handles crash recovery automatically — the consumer auto-claims and re-processes, and the idempotency key ensures no double-application.

This pattern is battle-tested and avoids the operational complexity of Kafka's transactional protocol — which, while powerful, introduces its own failure modes (producer fencing, zombie fencing fencing, coordinator failures).

### Migration path to Kafka (if needed)

This decision is not permanent. The notification producer and consumer abstractions should be behind an interface (`NotificationBroker`). If traffic grows beyond Redis's capability or we need long-term message retention, the same interface can be backed by Kafka with zero changes to business logic. The ADR to revisit this should trigger at **50k req/s sustained** or when **message retention beyond 7 days** becomes a requirement — neither of which is on the horizon.

---

## Consequences

### ✅ Pros (Wins)

1. **Zero new infrastructure.** Redis is already deployed, monitored, and backed up. We add a handful of streams to an existing server — no new provisioning, no new attack surface, no new PagerDuty integration.

2. **Fast time to value.** The team knows Redis. The Python driver (`redis-py`) is already a dependency. We can deliver async notification dispatch with retry logic inside the two-week window.

3. **Proportional complexity.** Redis Streams' simplicity is a feature for a 6-person team with no infra engineer. Consumer groups, pending entry lists, and auto-claim map directly to our retry/DLQ requirements without JVM tuning or partition rebalancing to manage.

4. **WebSocket push path is clear.** Redis Pub/Sub (already available) is the natural bridge to WebSocket servers. We can push real-time notifications alongside the stream-based async delivery.

5. **Sufficient throughput.** Redis handles 100k+ ops/s on modest hardware. Even at 10x growth (5k req/s peak), we're using <5% of that capacity.

6. **Lower cost.** No additional infrastructure. A slightly larger Redis instance is marginal cost on AWS.

### ❌ Cons (Trade-offs)

1. **No native exactly-once.** Redis Streams delivers at-least-once. We must implement idempotency at the consumer layer for billing notifications. This is well-understood but represents code the team must write and maintain.

2. **Message retention is weaker.** Redis persists to disk via RDB/AOF, but it is not designed for long-term message archival. If we need to replay notifications from weeks ago, we'll need a separate archival strategy.

3. **No schema registry.** Kafka's Schema Registry enforces contract evolution between producers and consumers. With Redis Streams, message schema is ad-hoc JSON in the stream fields. We'll need to manage schema evolution manually (documentation, consumer backward compatibility tests).

4. **Smaller ecosystem.** Kafka has a rich ecosystem (Kafka Connect for external integrations, Kafka Streams for stream processing). Redis Streams integrations are less mature. This may matter if we want to push notifications directly to Snowflake, S3, or similar sinks — we'd build those connectors ourselves.

5. **Partitioning is coarser.** Kafka partitions a topic across multiple brokers for horizontal scale. Redis Streams lives on a single node. If streams outgrow available memory, we'd need to shard manually or upgrade vertically. At our projected scale this is unlikely, but it's a ceiling Kafka doesn't have.

---

## Alternatives Considered

### Apache Kafka (primary alternative, rejected)

**Why it was evaluated:** Kafka is the gold standard for async event pipelines. It offers native exactly-once semantics, durable disk-based retention, massive throughput, and a mature ecosystem.

**Why it was rejected for now:**

1. **Operational burden exceeds team capacity.** A production Kafka deployment requires a KRaft cluster (minimum 3 nodes), JVM heap tuning, partition rebalancing protocols, broker monitoring, consumer lag alerting, and TLS/SASL security configuration. For a 6-person team with no infra engineer, this is a material ongoing tax — not a one-time setup cost.

2. **Cannot meet the 2-week timeline.** Even with managed MSK, the team must learn Kafka's consumer/producer APIs, partition strategy, offset management, and retry/dead-letter patterns. Realistic timeline for a team starting from zero Kafka experience: 3–4 weeks to production readiness, 6+ weeks to operational confidence.

3. **Over-provisioned for current and near-future scale.** Kafka's design targets 1M+ msgs/s across distributed brokers. Our peak is 500 req/s. We'd be paying the complexity tax for capabilities we won't use for years — if ever.

4. **Cost.** Self-hosted: minimum 3 EC2 nodes + EBS volumes (~$300+/month). Managed MSK: ~$200+/month for the smallest cluster. Confluent Cloud: similarly priced. None is prohibitive alone, but combined with the operational overhead it's hard to justify when Redis is already paid for and capable.

5. **No existing team expertise.** Three of six engineers would need to ramp up on Kafka fundamentals before writing production code. This learning curve delays the WebSocket push feature and other roadmap items.

**Reopening condition:** If sustained throughput exceeds 50k req/s, or message retention beyond 7 days becomes a hard requirement, or the team hires an infrastructure engineer, Kafka should be re-evaluated.

### Celery + RabbitMQ (considered during scoping, not a primary candidate)

Celery with RabbitMQ is a common Python async task pattern. It was excluded because:
- Celery's routing model is less flexible than stream-based consumer groups for our notification patterns
- RabbitMQ's message acknowledgment model is queue-oriented rather than stream-oriented, making replay and time-based retention harder to implement
- Adding RabbitMQ means introducing a third middleware (alongside Redis and PostgreSQL), increasing operational surface without Redis Streams' reuse advantage
- Celery does not natively support the consumer-group parallelism model that fits our per-tenant notification workers

### Amazon SQS + SNS (considered during scoping, not a primary candidate)

- SQS offers at-least-once (standard) or exactly-once (FIFO) but FIFO throughput is capped at 300 TPS, which is insufficient for our WebSocket push ambitions
- SNS/SQS polling model adds latency compared to Redis Streams' push-based XREADGROUP with BLOCK
- Vendor lock-in: moving notification logic into AWS-managed queues makes local development, testing, and future cloud migration harder
- No support for WebSocket push in the same middleware
