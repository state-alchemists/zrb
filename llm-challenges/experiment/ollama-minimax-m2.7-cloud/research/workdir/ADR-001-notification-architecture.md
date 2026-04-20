# ADR-001: Notification Subsystem Architecture

## Title
Choose Redis Streams over Apache Kafka for Notification Processing

## Status
**Proposed**

---

## Context

### The Problem
The notification module sends emails and webhooks synchronously inside the HTTP request cycle, causing:
- **Request timeouts**: Average latency 800ms, spiking to 8s during peak hours
- **Silent failures**: No retry mechanism; notifications dropped on provider failures
- **Cascading failures**: Slow webhooks have twice exhausted connection pools, taking down unrelated features
- **No delivery guarantees**: Billing-critical notifications lack exactly-once semantics

### Current System Constraints
| Constraint | Value |
|------------|-------|
| Peak throughput | ~500 req/s |
| Growth target | 10x within planning horizon |
| Engineering team | 6 people (3 senior, 3 mid-level) |
| Kafka experience | None |
| Redis experience | Extensive (already in production for sessions/rate-limiting) |
| Setup time budget | ≤2 weeks to production |
| Budget | Modest; cannot afford Confluent Cloud |

### Scaling Requirements
1. Decouple notifications from HTTP request cycle (async processing)
2. Retry with exponential backoff
3. At-least-once delivery for billing events; exactly-once where feasible
4. Support WebSocket push notifications within 2 quarters
5. Handle 10x traffic growth without re-architecting

---

## Decision

**We choose Redis Streams for the notification subsystem.**

### Justification

Redis Streams meets all functional requirements while satisfying the operational and timeline constraints that make Kafka impractical for this team.

**Throughput adequacy**: At 500 req/s peak (targeting 5,000 req/s for 10x growth), Redis Streams handles 500K–1M ops/s on commodity AWS instances—**30-60x headroom** above our 2-year horizon. Kafka's millions/sec capacity is unnecessary.

**Operational continuity**: The team already runs Redis for sessions and rate-limiting. Operational tooling, monitoring, and expertise transfer directly. Kafka would require building entirely new operational knowledge—ZooKeeper/KRaft management, partition balancing, replication factor tuning, consumer group lag monitoring—without a dedicated infrastructure engineer.

**Time to value**: A Redis Streams implementation can be production-ready in **3-5 days** using existing libraries (`redis-py`, `rq`, or minimal custom consumer). Kafka requires 2-4 weeks for equivalent production readiness given team unfamiliarity and operational complexity.

**Exactly-once semantics**: Both Kafka and Redis Streams provide only at-least-once at the transport layer. Exactly-once delivery for billing notifications must be implemented at the application layer via deduplication (idempotency keys with Redis TTL). Since this application-level logic is required regardless of chosen technology, Redis Streams' at-least-once guarantee is functionally equivalent for our billing needs.

**Consumer groups**: Redis Streams provides first-class consumer groups (`XREADGROUP`, `XACK`, `XPENDING`) with identical semantics to Kafka consumer groups—partition-like assignment, offset tracking, and redelivery on failure.

---

## Consequences

### Benefits of Redis Streams

| Property | Value |
|----------|-------|
| **Throughput** | 500K–1M ops/s (sufficient for 10x growth) |
| **Ordering** | Per-stream FIFO within consumer groups |
| **Message retention** | Configurable via `MAXLEN` or `MINID`; supports replay |
| **Consumer groups** | Full support: `XREADGROUP`, `XACK`, `XPENDING`, dead letter tracking |
| **Exactly-once** | At-least-once transport + idempotency keys at application layer |
| **Integration** | Existing Redis client library; no new infrastructure |

- **Fast integration**: Leverage existing `redis-py` and Redis expertise
- **Operational simplicity**: Single Redis cluster serves sessions, rate-limiting, and now notifications
- **Replay capability**: `MINID` allows reprocessing from timestamp for backfills
- **Monitoring**: Existing Redis monitoring stack (Redis Insight, `INFO` stats) covers the new use case

### Risks / Trade-offs

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Scale ceiling** | Redis Streams begins to strain above ~50K req/s per stream | Design for stream-per-notification-type; shard across multiple streams if needed |
| **Multi-region resilience** | Redis Streams not designed for cross-datacenter replication | If multi-region needed within 2 years, re-evaluate; for now single-AZ is acceptable |
| **No native compaction** | Kafka's log compaction is more flexible for event sourcing | Not needed for notification use case; TTL-based trimming sufficient |
| **Operational learning curve** | Still learning Redis Streams patterns | Small risk; team knows Redis well; Streams API is small (8 commands) |

**Long-term re-evaluation**: If throughput exceeds 50K req/s or multi-region deployment becomes a hard requirement, revisit Kafka evaluation. The notification subsystem can be migrated; the architecture is not a dead end.

---

## Alternatives Considered

### Apache Kafka

| Property | Kafka | Redis Streams |
|----------|-------|---------------|
| **Peak throughput** | Millions/s | 500K–1M ops/s |
| **Exactly-once** | Native transactions | Application-layer idempotency |
| **Consumer groups** | Mature, first-class | First-class, identical semantics |
| **Ordering** | Per-partition | Per-stream |
| **Message retention** | Days–indefinite, log-compaction | Configurable, TTL-based |
| **Operational complexity** | High (brokers, ZooKeeper/KRaft, partition management) | Low (single Redis instance, familiar tooling) |
| **Learning curve** | Steep | Minimal |
| **Setup time** | 2-4 weeks | 3-5 days |
| **Team expertise** | None | Extensive |
| **Infrastructure cost** | 3+ brokers for resilience | Leverage existing cluster |

**Why Kafka was rejected**:

1. **Timeline incompatibility**: 2-week delivery requirement is not realistic for Kafka production deployment with an inexperienced team. Proper Kafka setup requires broker configuration, replication factor decisions, partition count planning, consumer group offset management, and monitoring dashboards—2 weeks is insufficient.

2. **Operational burden**: Without a dedicated infrastructure engineer, Kafka operational concerns (broker failures, partition rebalancing, under-replicated partitions, consumer lag alerts) would consume senior engineering time that should go toward product development.

3. **Over-engineering**: At 500 req/s (5,000 req/s target), Kafka's capacity is 200-2000x overkill. The complexity premium is not justified by requirements.

4. **Cost**: Self-managed Kafka requires minimum 3 brokers for resilience. Redis Streams runs on the existing cluster.

5. **No operational leverage**: Kafka expertise does not transfer to other systems the team operates. Redis Streams expertise reinforces existing knowledge.

**Kafka would be appropriate if**: Team size were 15+, included dedicated infrastructure engineers, timeline were 2+ months, and scale targets exceeded 100K req/s.

---

## Recommendation Summary

For a 6-person team with existing Redis expertise, a 2-week timeline, and modest budget, **Redis Streams is the correct choice**. It delivers:

- Async notification processing immediately (3-5 days)
- Retry with exponential backoff via consumer group pending entry management
- At-least-once delivery (exactly-once for billing via idempotency keys)
- Sufficient throughput for 10x growth
- Zero new operational infrastructure

Kafka's capabilities exceed our requirements by 2-3 orders of magnitude while imposing operational complexity the team cannot absorb given constraints.