# ADR-001: Notification Subsystem Message Broker

## Title
Choose Redis Streams over Apache Kafka for the Notification Subsystem

## Status
**Proposed**

## Context

Our SaaS project management platform currently handles notifications synchronously inside the HTTP request cycle, causing:
- Average response latency of 800ms (spiking to 8s at peak)
- Silent notification failures with no retry mechanism
- Cascading failures that exhaust connection pools
- No delivery guarantees for billing-critical events

**System Scale:**
- 85,000 monthly active users
- ~2M tasks created per month
- Peak throughput: ~500 req/s
- Growth target: 10x without re-architecting

**Hard Constraints:**
- 6-person engineering team (3 senior, 3 mid-level), no dedicated infrastructure engineer
- No Kafka experience on the team
- Must not exceed 2 weeks to first deliverable value
- Budget cannot accommodate managed Confluent Cloud at full scale
- Existing Redis deployment (used for sessions and rate limiting)
- **Exactly-once delivery required for billing notifications** (trial expired, payment failed)

## Decision

**Choose Redis Streams.**

Redis Streams meets all functional requirements (async decoupling, retry with backoff, delivery guarantees, 10x scale headroom) with significantly lower operational overhead and faster time-to-value than Kafka.

### Technical Justification

**Throughput:**
| Requirement | Redis Streams | Apache Kafka |
|-------------|---------------|--------------|
| Peak load | ~500 req/s | ~500 req/s |
| Sustainable | 500K–1M msg/s on commodity hardware | 1M+ msg/s with proper tuning |
| Verdict | 1000x headroom | Massive overcapacity |

Redis Streams provides more than sufficient throughput for our current and projected load. The 10x growth target (5,000 req/s) remains well within Redis Streams' capabilities.

**Ordering Guarantees:**
- **Redis Streams**: Global ordering per stream. All messages in a stream are consumed in the same order they were appended.
- **Kafka**: Per-partition ordering. Requires careful partition strategy to maintain ordering across consumers.

For notification workloads where ordering within a notification type matters (e.g., task update sequence), Redis Streams delivers simpler guarantees.

**Message Retention:**
| Feature | Redis Streams | Apache Kafka |
|---------|---------------|--------------|
| Retention | Up to 512M entries or memory-constrained | Days/weeks/years, configurable per topic |
| Consumer lag | Visible via `XRANGE` and consumer group metrics | Mature lag monitoring |
| Replay capability | Yes, via `XRANGE` on stream | Yes, via offset seeking |

Both satisfy the replay requirement for retry scenarios.

**Consumer Groups:**
Both support consumer groups with the same semantics: multiple consumers sharing the workload, automatic rebalancing on failure. Redis Streams consumer groups (`XREADGROUP`) are production-tested and offer equivalent fault tolerance.

**Exactly-Once Semantics:**
| Broker | Native exactly-once | Notes |
|--------|---------------------|-------|
| Kafka | Yes (exactly-once transactions via idempotent producers) | Requires careful configuration; adds latency |
| Redis Streams | No (at-least-once only) | Achievable via consumer-side idempotency keys |

For billing notifications, **exactly-once is achievable with Redis Streams** by:
1. Generating a unique idempotency key per notification (e.g., `notification:{user_id}:{event_type}:{event_id}`)
2. Storing processed keys in a Redis hash with TTL
3. Checking existence before processing

This pattern is straightforward to implement and eliminates duplicate deliveries. The team has existing Redis expertise to implement this correctly.

**Operational Complexity:**
| Dimension | Redis Streams | Apache Kafka |
|-----------|---------------|--------------|
| Infrastructure | Zero new infra (Redis already running) | Requires new cluster, ZooKeeper or KRaft |
| Learning curve | Low (team knows Redis) | Steep (no Kafka experience) |
| Configuration | Minimal | Partition count, replication factor, acks, retention policies |
| Monitoring | Existing Redis monitoring | New monitoring stack required |
| Failure modes | Well-understood | Partition rebalancing, leader election, under-replicated partitions |

For a 6-person team with no dedicated infrastructure engineer, Kafka's operational complexity is a significant risk. Redis is already in the stack—monitoring, backups, and operational runbooks already exist.

**Time to Value:**
| Phase | Redis Streams | Apache Kafka |
|-------|---------------|--------------|
| Initial setup | 1–2 days | 1–2 weeks |
| First production message | Days | Weeks |
| Full migration | < 1 week | 2+ weeks |

Redis Streams requires no new infrastructure, no new operational knowledge, and no configuration beyond what the team already manages.

## Consequences

### Positive Consequences

1. **Fast delivery of value**: Team can ship async notifications within days, not weeks
2. **Zero infrastructure cost**: Uses existing Redis deployment; no new servers, no managed service expense
3. **Low operational burden**: Same tooling, monitoring, and on-call rotation as existing Redis
4. **Sufficient throughput**: 500K–1M msg/s capacity handles 10x growth easily
5. **Familiar codebase**: No new dependencies to learn or maintain
6. **WebSocket readiness**: Redis Pub/Sub or Streams can serve real-time push notifications in future quarter without additional infrastructure investment

### Negative Consequences

1. **No native exactly-once**: Requires application-level idempotency implementation (acceptable for billing events given team capability)
2. **Single-node stream limitation**: Redis Streams performance bound to single-core on primary; cluster mode adds complexity (acceptable for current scale)
3. **Message size limits**: Redis is memory-constrained; very large messages (>1MB) require care (not applicable for notification payloads)
4. **Persistence trade-off**: If Redis persistence is misconfigured, stream data could be lost on restart (mitigated by AOF persistence already in production)
5. **No Kafka compatibility**: If scale grows beyond ~50K req/s sustained, migration to Kafka would require re-architecture (acceptable 2-year horizon)

## Alternatives Considered

### Apache Kafka

**Why it was considered:**
- Industry standard for event streaming at massive scale
- Native exactly-once semantics
- Mature ecosystem (Kafka Connect, Kafka Streams, Schema Registry)
- Handles 1M+ msg/s for future scale

**Why it was rejected:**

| Concern | Impact |
|---------|--------|
| No team experience | 6-week learning curve minimum; high risk of misconfiguration |
| Operational complexity | Requires dedicated infrastructure engineer to run safely |
| Setup time | 2-week constraint would be violated; cluster setup alone takes 1 week |
| Budget | Self-managed Kafka on 4 EC2 instances requires significant ops work; managed Confluent Cloud is cost-prohibitive |
| Overcapacity | 500 req/s is 0.05% of Kafka's capability—the complexity is entirely unjustified |

Kafka is the right choice for:
- Teams with dedicated platform/infrastructure engineers
- Sustained throughput > 100K req/s
- Multi-team event-driven architectures needing schema evolution
- Organizations already running Kafka for other use cases

Our constraints (small team, modest budget, moderate scale) make Kafka's operational overhead disproportionate to the benefit.

### In-Memory Queue (Python RQ / Celery)

Also considered but dismissed because:
- No delivery guarantees (in-memory = lost on crash)
- No consumer group semantics for horizontal scaling
- Retry logic requires manual implementation
- No visibility into queue depth or consumer lag

## Summary

Redis Streams is the pragmatic choice for our team size, scale, and constraints. It provides sufficient throughput (1000x headroom), ordering guarantees, retry semantics, and a path to exactly-once delivery for billing notifications—all without new infrastructure, new operational knowledge, or exceeding our 2-week time constraint. Kafka's capabilities are genuine overkill for 500 req/s and would introduce unacceptable operational risk for a 6-person team.

**Recommendation:** Implement Redis Streams with idempotency keys for billing events. Revisit Kafka if sustained throughput exceeds 50K req/s or the organization grows a dedicated platform team.