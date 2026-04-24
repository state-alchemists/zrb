# ADR-001: Notification Subsystem Architecture

**Date**: 2026-04-24  
**Author**: Architecture Team  
**Status**: Proposed

---

## Context

Our project management platform has outgrown its synchronous notification architecture. Current pain points include:

- **Request timeouts**: Notification sending blocks HTTP responses (800ms avg, 8s peak)
- **Silent failures**: No retry mechanism when email providers or webhooks fail
- **Cascading failures**: Slow endpoints exhaust connection pools, causing outages
- **No delivery guarantees**: Billing-critical notifications lack exactly-once semantics

We must decouple notifications from the request cycle while supporting retry logic, delivery guarantees, and 10x traffic growth (targeting 5,000 req/s peak). The solution must be operational by a 6-person team (no dedicated infrastructure engineer) within 2 weeks.

---

## Decision

**We will use Redis Streams as the message broker for our notification subsystem.**

### Justification

This decision prioritizes operational simplicity and time-to-value over maximum theoretical performance. Given our team constraints and existing infrastructure, Redis Streams delivers the required capabilities without introducing operational overhead that could jeopardize delivery timelines.

---

## Technical Evaluation

| Criterion | Redis Streams | Apache Kafka |
|-----------|--------------|--------------|
| **Setup Time** | < 2 days (uses existing Redis) | 1-2 weeks minimum |
| **Team Familiarity** | High (already used for sessions/rate-limiting) | None |
| **Operational Burden** | Low (single existing managed service) | High (cluster management, partitions, rebalancing) |
| **Throughput** | ~100k ops/sec (memory-bound) | 100k-1M+ ops/sec (disk-bound) |
| **Consumer Groups** | ✅ Supported | ✅ Excellent |
| **Message Retention** | Memory-bounded (configurable) | Disk-based (indefinite) |
| **Exactly-Once Semantics** | Application-level only | Native via idempotent producers + transactions |
| **Ordering Guarantees** | Per-stream FIFO | Per-partition strong ordering |
| **WebSocket Synergy** | ✅ Pub/Sub + Streams unified | Requires separate infrastructure |

### Key Reasoning

1. **Time Constraint**: We must deliver value within 2 weeks. Redis Streams leverages our existing Redis deployment, requiring only client-side changes. Self-hosted Kafka would consume most of that window just for setup and tuning.

2. **Team Capacity**: Without a dedicated infrastructure engineer, we cannot sustainably operate a Kafka cluster. Redis is already operational 24/7 for critical session storage.

3. **Throughput Adequacy**: At 10x growth (5,000 req/s peak with bursts), we remain well within Redis Streams' capabilities. Memory constraints can be managed with appropriate retention policies (e.g., 7-day retention with consumer acknowledgment).

4. **Exactly-Once Implementation**: While Kafka offers superior exactly-once primitives (transactions + idempotent producers), Redis Streams can achieve the same outcome at the application layer using PostgreSQL for idempotency key tracking. Billing notifications will carry deterministic IDs, with processed keys stored in an `idempotent_notifications` table with uniqueness constraints.

5. **Future WebSocket Support**: Our planned real-time features will leverage Redis Pub/Sub. Co-locating stream processing with Pub/Sub simplifies architecture and reduces operational surface area.

6. **Budget Constraint**: Managed Kafka (Confluent Cloud) exceeds our budget at scale. Self-hosted Kafka requires significant EC2 resources for ZooKeeper/KRaft + brokers. Redis is already provisioned.

---

## Consequences

### Pros

- **Rapid deployment**: Existing Redis infrastructure means zero new services to provision
- **Operational continuity**: Team expertise transfers directly; same monitoring/alerting applies
- **Simplified debugging**: Single datastore for streams, sessions, and rate limiting
- **Cost efficiency**: No additional AWS resources required
- **Horizontal scaling**: Consumer groups allow parallel processing across our 4 web servers
- **At-least-once delivery**: Redis Streams' consumer group acknowledgment mechanism provides reliable delivery semantics

### Cons

- **Memory-bound retention**: Stream data must fit in RAM or be trimmed aggressively; long-term replay capability is limited compared to Kafka's disk-based retention
- **Simpler consumer group model**: Rebalancing is less sophisticated than Kafka's; sudden consumer failures may cause temporary duplicate processing
- **No native exactly-once**: Requires application-level deduplication using PostgreSQL, adding latency and complexity to billing notification paths
- **Persistence trade-off**: While Redis supports AOF and RDB snapshots, durability guarantees are weaker than Kafka's write-ahead log
- **Monitoring gap**: Stream lag and consumer group health require custom metrics; less mature observability ecosystem than Kafka
- **Limited stream processing**: No built-in stream processing framework (like Kafka Streams or ksqlDB); complex transformations require application code

---

## Alternatives Considered

### Apache Kafka (Rejected)

Kafka was seriously evaluated due to its industry-standard status and superior streaming capabilities. The specific properties that led to rejection:

- **Operational complexity**: Requires management of brokers, ZooKeeper or KRaft consensus, partition rebalancing, and consumer group coordination — all demand expertise we lack
- **Setup overhead**: Estimating 1-2 weeks for production-hardened deployment exceeds our delivery constraint
- **Infrastructure footprint**: Self-hosted requires minimum 3 broker nodes for fault tolerance, tripling our message broker infrastructure costs
- **Learning curve**: Zero team experience with Kafka means troubleshooting partitioned consumers or rebalancing storms could block production incidents

Kafka remains the superior technology for high-throughput, long-retention event streaming. We will revisit if we exceed Redis throughput limits or hire dedicated infrastructure expertise.

---

## Migration Path

1. **Week 1**: Deploy notification producer writing to Redis Streams; async worker reading stream and processing notifications
2. **Week 1-2**: Implement idempotency layer in PostgreSQL for billing-critical notifications
3. **Week 2**: Cut over from synchronous to async processing; add exponential backoff retry logic
4. **Quarter 2**: Add WebSocket push notifications using Redis Pub/Sub alongside existing Streams infrastructure

---

## Related Decisions

- **Idempotency Storage**: PostgreSQL (`idempotent_notifications` table with TTL)
- **Retry Strategy**: Exponential backoff with jitter, max 5 retries, dead-letter stream after exhaustion
- **Monitoring**: Custom metrics for stream lag, consumer group health, and notification delivery rates
