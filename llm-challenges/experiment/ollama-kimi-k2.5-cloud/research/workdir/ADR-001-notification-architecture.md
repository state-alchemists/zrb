# ADR-001: Notification Subsystem Architecture

**Date:** 2026-05-17  
**Author:** Platform Engineering Team  
**Status:** Proposed

---

## Context

Our SaaS project management platform has outgrown its synchronous notification architecture. Current pain points include:

- **Request timeouts** (800ms avg, 8s peak) caused by blocking notification calls
- **Silent failures** with no retry mechanism or dead-letter queue
- **Cascading failures** from slow webhook endpoints exhausting connection pools
- **No delivery guarantees** for billing-critical notifications requiring exactly-once semantics

### Scaling Requirements

- Decouple notifications from HTTP request cycle for async processing
- Support retry with exponential backoff
- Guarantee at-least-once delivery, exactly-once for billing events
- Future support for real-time WebSocket push notifications
- Handle 10x traffic growth (from ~500 req/s to ~5,000 req/s peak)

### Constraints

- **Team size:** 6 engineers (3 senior, 3 mid-level), **no dedicated infrastructure engineer**
- **Existing infrastructure:** Redis already in production for sessions and rate-limiting
- **Experience:** No Kafka operational experience on the team
- **Timeline:** Maximum 2 weeks for setup/migration before delivering value
- **Budget:** Modest; managed Confluent Cloud at full scale is unaffordable
- **Critical requirement:** Exactly-once semantics for billing notifications

---

## Decision

**We will use Redis Streams** as the messaging backbone for the notification subsystem.

### Justification

Redis Streams satisfies our core requirements while aligning with our operational constraints. The decisive factors are:

1. **Operational Leverage:** We already operate Redis in production. Adding Streams functionality requires no new infrastructure, monitoring, or operational runbooks. This reduces risk given our lack of dedicated infrastructure expertise.

2. **Timeline Compliance:** Redis Streams can be operational within days, not weeks. The team can reuse existing Redis connection handling, client libraries (redis-py already in-use), and monitoring. Kafka would require broker provisioning, cluster sizing, ZooKeeper/KRaft coordination learning, and new client library integration.

3. **Adequate Feature Set:** While less feature-rich than Kafka, Redis Streams provides:
   - Consumer groups for horizontal scaling
   - Message persistence (configurable retention)
   - Explicit ACK/NACK with re-delivery for retry semantics
   - Blocked reads for efficient async workers
   - Range queries by message ID (timestamp-based)

4. **Exactly-Once Feasibility:** We acknowledge Redis Streams provides at-least-once delivery. For billing-critical notifications requiring exactly-once semantics, we will implement idempotency checks using Redis or PostgreSQL (deduplication keys) at the consumer layer. This is a standard pattern in distributed systems and acceptable given our volume (2M tasks/month → ~70 notifications/minute at current scale).

---

## Consequences

### Positive

| Aspect | Impact |
|--------|--------|
| **Operational Simplicity** | Single Redis instance manages sessions, rate-limiting, AND message queues. Reduced operational surface area. |
| **Speed to Value** | Notification subsystem operational within days, meeting the 2-week constraint. |
| **Familiar Tooling** | Team uses existing redis-py library and Redis CLI. No new client libraries or debugging patterns to learn. |
| **Horizontal Scaling** | Consumer groups allow adding notification workers without code changes as volume grows. |
| **Cost Efficiency** | Uses existing Redis infrastructure. No additional cloud spend for managed Kafka or extra EC2 instances. |
| **Unified Observability** | Existing Redis monitoring covers queue depth, consumer lag, and throughput. |
| **Future WebSocket Path** | Redis Pub/Sub (already available) can power WebSocket push notifications in Q3/Q4 using the same infrastructure. |

### Negative

| Aspect | Impact | Mitigation |
|--------|--------|------------|
| **Limited Retention** | Default Redis persistence is memory-bound; unacknowledged messages may be lost if memory exhausted. | Configure `MAXLEN` with appropriate eviction; add persistent log for critical billing events in S3/PostgreSQL as audit trail. |
| **No Native Partitioning** | Single stream per event type; cannot partition billing events across multiple brokers for higher throughput. | Not a constraint at 10x scale (5,000 req/s). Single-node Redis handles 100K+ ops/sec. Partition by stream name if needed in future. |
| **At-Least-Once Only** | No native exactly-once semantics; duplicate processing possible on consumer restart/crash. | Implement idempotent consumers using Redis SETNX or PostgreSQL unique constraints on `notification_id`. |
| **No Replay by Timestamp** | Cannot easily replay messages from arbitrary timepoints like Kafka's `consumer.seek()`. | Use Redis AOF/Snapshot for point-in-time recovery; acceptable given notification queue is ephemeral (retention hours, not days). |
| **Operational Risk Concentration** | Session storage and notifications share Redis—failure affects both. | Run separate Redis DB (numeric index) for Streams; monitor memory usage aggressively. Consider ElastiCache for Redis with Multi-AZ for high availability. |

---

## Alternatives Considered

### Apache Kafka

We evaluated Apache Kafka as the alternative. While Kafka is the gold standard for high-throughput, durable message streaming, it was rejected based on our constraints:

| Kafka Advantage | Why It Wasn't Decisive |
|-----------------|------------------------|
| **Exactly-once semantics** (transactions API) | Critical only for billing; manageable via idempotency layer with Redis Streams |
| **Unbounded retention** (disk-based) | Notification queue is ephemeral (hours); long-term persistence not required |
| **Partitioning for scale** | 5,000 req/s peak fits comfortably on single Redis node (100K+ ops/sec) |
| **Mature consumer groups & rebalancing** | Redis Streams consumer groups are adequate for our throughput |
| **Rich ecosystem** (Kafka Connect, Streams API) | Adds complexity we don't need; no current requirement for stream processing |

| Kafka Drawback | Impact on Constraints |
|----------------|---------------------|
| **Operational complexity** | Requires broker cluster, ZooKeeper/KRaft, partition management, rebalancing tuning. No dedicated infra engineer to manage this. |
| **Learning curve** | New client libraries, consumer group semantics, offset management. Team has no Kafka experience. |
| **Setup time** | 2-4 weeks to provision, tune, and integrate safely. Exceeds our 2-week value-delivery window. |
| **Cost** | Self-hosted requires EC2 instances; managed Confluent Cloud starts at ~$200/month base + usage, scaling to thousands at 10x traffic. |
| **Over-provisioning** | Kafka's strengths (partitioning, replay, stream processing) solve problems we don't have at our scale. |

### Rationale Summary

> Kafka is the superior technology for large-scale streaming, but Redis Streams is the *right choice for us now*. Our constraints (small team, tight timeline, modest budget, existing Redis) make operational simplicity the overriding concern. We can migrate to Kafka if we outgrow Redis Streams, but that migration is significantly easier than recovering from an operational incident caused by running complex infrastructure we cannot support.

---

## References

- Redis Streams Documentation: https://redis.io/docs/data-types/streams/
- Redis Consumer Groups: https://redis.io/docs/data-types/streams/#consumer-groups
- Kafka Exactly-Once Semantics: https://www.confluent.io/blog/exactly-once-semantics-are-possible-heres-how-apache-kafka-does-it/
- Idempotent Consumer Pattern: https://microservices.io/patterns/communication/idempotent-consumer.html
