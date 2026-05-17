# ADR-001: Notification Subsystem Architecture

## Status

Proposed

## Context

Our SaaS project management platform handles notifications synchronously within HTTP requests, causing request timeouts (800ms average, 8s spikes), silent failures, and cascading failures when external endpoints are slow. We need to decouple notification delivery from the request cycle while supporting:

- Retry with exponential backoff for transient failures
- At-least-once delivery for all notifications; exactly-once for billing-critical events
- Real-time WebSocket push within 2 quarters
- 10x traffic growth (current peak: 500 req/s)
- Time-to-value within 2 weeks

**Team constraints**: 6 engineers (3 senior, 3 mid-level), no dedicated infrastructure specialist. Redis already runs in production for sessions and rate limiting. No Kafka experience.

## Decision

We will use **Redis Streams** as the message broker for the notification subsystem.

### Justification

| Factor | Redis Streams | Apache Kafka |
|--------|---------------|--------------|
| **Setup & time-to-value** | Hours to days (already running Redis) | Days to weeks (new infrastructure) |
| **Team expertise** | Familiar (existing Redis usage) | None (steep learning curve) |
| **Throughput** | 100K–500K msg/s per instance | 1M+ msg/s per broker |
| **Operational complexity** | Low (single process, no ZooKeeper) | High (broker clusters, partition management) |
| **Exactly-once semantics** | No (requires idempotent consumers) | Yes (transactional writes) |
| **Consumer groups** | Yes (XGROUP) | Yes (native) |
| **Message retention** | Time-based, memory-bound (configurable) | Time/size-based, disk-bound (days to weeks) |
| **Ordering guarantees** | Strict per-stream | Per-partition |
| **Cost at our scale** | No additional infrastructure | New cluster or managed service |

**Why Redis Streams wins for this context:**

1. **2-week constraint**: We can productionalize Redis Streams within days by extending our existing Redis deployment. Kafka would consume the entire window just on setup.

2. **Team capacity**: Without a dedicated infra engineer, we cannot afford the operational burden of Kafka cluster management (quorum management, rebalancing, monitoring). Redis Streams requires no additional operational knowledge.

3. **Scale sufficiency**: At 10x growth (5,000 req/s peak), notification throughput would be ~100–200 msg/s assuming 2–4 notifications per event. Redis Streams handles this orders of magnitude more easily—our bottleneck will be external providers, not the stream.

4. **Billing exactly-once workaround**: Redis does not provide true exactly-once semantics, but we can achieve equivalent behavior:
   - Each billing notification includes a unique `notification_id`
   - Consumers check PostgreSQL for prior delivery before processing (SELECT 1 WHERE notification_id = ?)
   - Idempotent writes to notification log table before sending
   - This pattern is well-established for financial systems using non-transactional queues

5. **Future WebSocket path**: Redis Streams supports blocking reads (XREAD BLOCK), suitable for WebSocket push workers reading from streams in real time.

6. **Migration option**: If we outgrow Redis Streams (unlikely before 50x current scale), we retain the consumer logic and swap the backend. The architecture remains queue-based.

## Consequences

### Pros

- **Rapid delivery**: Functional async notifications within 1 week; production-ready within 2 weeks
- **Zero new infrastructure**: No additional servers, containers, or managed services
- **Operational simplicity**: Single Redis instance to monitor; no cluster coordination
- **Familiar tooling**: Existing Redis expertise, dashboards, and alerts extend naturally
- **Cost efficiency**: No additional licensing or cloud costs
- **Adequate scale headroom**: 100K+ msg/s throughput covers 10x growth with margin
- **Consumer groups built-in**: `XGROUP`, `XREADGROUP`, and `XACK` provide consumer coordination without external libraries

### Cons

- **No native exactly-once**: Billing notifications require application-level deduplication (database check before send). This adds ~10ms latency per billing notification but is acceptable for asynchronous processing.

- **Memory-bound retention**: Messages persist in Redis memory (with optional disk persistence). Long retention (weeks) is impractical. We configure 24-hour retention—sufficient for retry cycles; consumers log processed messages to PostgreSQL for audit.

- **Single point of failure**: Redis is a SPOF. Mitigation: Redis Sentinel for failover, or migrate to Redis Cluster later. Given our 99.9% SLA target and team size, Sentinel is acceptable initial architecture.

- **Less ecosystem maturity**: Fewer tooling options vs. Kafka (no Kafka Connect, more limited stream processing). We accept this because our use case is simple fan-out, not complex event processing.

- **Future migration risk**: If we hit 50x scale or need multi-datacenter replication, we must migrate. We accept this risk because: (a) 50x is years away, (b) migration path is straightforward (consumer code unchanged), (c) we gain 2+ years of operational experience before facing this.

## Alternatives Considered

### Apache Kafka

Kafka is objectively superior for:
- True exactly-once semantics (transactional writes)
- Multi-day/week retention with disk-based storage
- Massive scale (millions of msg/s)
- Multi-datacenter replication
- Rich ecosystem (Kafka Connect, ksqlDB, schema registry)

**Why we rejected it:**

1. **Setup violates timeline**: Self-hosted Kafka requires ZooKeeper/KRaft, multi-broker clusters, and significant configuration—2 weeks minimum before production-ready. Managed Confluent Cloud is faster but exceeds budget at scale.

2. **Operational burden**: Kafka requires expertise in partition strategy, consumer lag monitoring, rebalancing, and cluster maintenance. We have no infra engineer and no training budget.

3. **Over-engineered for current needs**: Our notification throughput is ~10–50 msg/s. Kafka's strengths (massive throughput, complex stream processing, long retention) do not justify its complexity for this workload.

4. **Idempotent consumers still needed for billing**: Even with Kafka's exactly-once, billing notifications targeting external services (email providers, webhooks) require idempotency—you cannot guarantee external systems process once. So we must implement the same deduplication pattern regardless.

5. **Cost at our scale**: Self-hosted adds operational cost; managed Confluent would cost $0.50–$1.00 per million messages. While modest, it adds no value over Redis at our throughput.

**Verdict**: Kafka is the correct choice for organizations with dedicated infrastructure teams, 100x+ scale requirements, or complex event processing needs. Our context does not match any of these.

### PostgreSQL as Queue (SKIP LOCKED)

We considered using PostgreSQL `SELECT ... FOR UPDATE SKIP LOCKED` as a simple queue.

**Why rejected**: Polling the database for every notification adds unnecessary load to our primary PostgreSQL instance (already under pressure). We'd need to implement retry logic, backoff, and consumer coordination manually. Redis Streams provides this out-of-the-box with better performance characteristics.

### RabbitMQ

RabbitMQ is a mature alternative with excellent queue semantics.

**Why rejected**: It requires new infrastructure and operational knowledge (similar complexity to Kafka without Kafka's scale benefits). Redis Streams is sufficient for our throughput and already in our stack.

---

**Decision Date**: 2026-05-17
**Decision Makers**: Engineering Team
**Review Trigger**: If monthly active users exceed 500,000, or notification P99 latency exceeds 5 seconds, or billing delivery failures exceed 0.1%, revisit this decision with consideration of Apache Kafka.