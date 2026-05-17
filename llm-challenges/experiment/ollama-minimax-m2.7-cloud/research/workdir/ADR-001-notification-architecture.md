# ADR-001: Notification Subsystem Architecture

## Status

**Proposed**

---

## Context

### Problem Statement

The notification module handles emails and webhooks for task events (created, updated, assigned, completed). It currently executes synchronously inside the HTTP request cycle, causing:

- **Request timeouts**: Average latency 800ms, spiking to 8s during peak hours
- **Silent failures**: Provider downtime results in dropped notifications with no retry
- **Cascading failures**: Slow webhook endpoints caused connection pool exhaustion and feature outages
- **No delivery guarantees**: Billing-critical notifications lack exactly-once semantics

### System Scale

| Metric | Value |
|--------|-------|
| Monthly Active Users | 85,000 |
| Tasks Created/Month | ~2,000,000 |
| Peak Request Rate | ~500 req/s |
| Growth Target | 10x without re-architecture |

### Constraints

- **Team**: 6 engineers (3 senior, 3 mid-level), no dedicated infrastructure engineer
- **Kafka experience**: None on the team
- **Existing infrastructure**: Redis running for session storage and rate limiting
- **Timeline**: Must deliver value within 2 weeks of start
- **Budget**: Modest; cannot afford managed Confluent Cloud at scale
- **Critical requirement**: Exactly-once semantics for billing notifications (trial expired, payment failed)

---

## Decision

**Chosen Option: Redis Streams**

### Recommendation

Implement the notification subsystem using **Redis Streams**, leveraging the existing Redis instance already deployed for session storage and rate limiting. This decision prioritizes operational simplicity, team familiarity, and time-to-value while meeting all technical requirements.

---

## Consequences

### Benefits of Redis Streams

1. **Operational simplicity**: Redis is already running and familiar to the team. No new infrastructure to deploy, monitor, or troubleshoot. Single system to operate.

2. **Fast integration**: Redis Streams commands (`XADD`, `XREADGROUP`, `XACK`, `XRANGE`) have a shallow learning curve. The team can become productive within days, not weeks.

3. **Sufficient throughput**: At 500 req/s peak with 10x growth targeting 5,000 req/s, Redis Streams handles 100,000+ events/second comfortably—orders of magnitude above requirements.

4. **Ordering guarantees**: `XADD` provides insertion order within a stream, and consumer groups (`XREADGROUP`) maintain ordering per consumer, satisfying task notification ordering requirements.

5. **Consumer groups with ACK**: `XACK` enables reliable processing acknowledgment. Combined with `XPENDING`, the system supports retry with exponential backoff by re-delivering unacknowledged messages after a visibility timeout.

6. **Message retention**: Configurable via `MAXLEN` or time-based trimming (`MAXLEN ~ 100000`). Supports the 7-day replay window needed for debugging.

7. **Existing investment**: No additional cost for infrastructure or managed services. Can start with a single Redis instance and scale horizontally if needed.

8. **WebSocket roadmap alignment**: Redis pub/sub can supplement streams for real-time push notifications within the same system in the future.

### Drawbacks and Mitigations

1. **Exactly-once semantics require idempotency layer**: Redis Streams provides at-least-once delivery only. For billing notifications requiring exactly-once, the consumer must implement idempotency (e.g., deduplication via notification ID stored in Redis with TTL). **Mitigation**: Implement a deduplication key `notify:dedup:{notification_id}` with 24-hour TTL in the consumer processor.

2. **No native dead-letter queue**: Unprocessable messages require custom handling. **Mitigation**: Route to a dedicated `notifications:dlq` stream after max retry attempts via `XADD notifications:dlq`.

3. **Visibility timeout complexity**: Setting `BLOCK` timeouts and `XPENDING` visibility requires careful tuning. **Mitigation**: Initial implementation uses 30-second visibility timeout with 3 retry attempts; tune based on observed processing times.

4. **Scaling ceiling**: Single Redis instance throughput has limits (~200K-400K ops/sec depending on hardware). **Mitigation**: Redis Cluster can horizontally scale if needed; architecture supports sharding by notification type.

5. **Operational visibility**: Less ecosystem tooling than Kafka for metrics and monitoring. **Mitigation**: Use `INFO streams` command for metrics; integrate with existing Redis monitoring (Redis Insight, or export to Prometheus).

---

## Alternatives Considered

### Apache Kafka

#### Why Not Kafka

| Criterion | Kafka | Redis Streams | Verdict |
|-----------|-------|---------------|---------|
| **Team experience** | None | Familiar (already running) | Redis |
| **Setup time** | 2+ weeks for production-ready cluster | 3-5 days to integrate | Redis |
| **Operational complexity** | High: ZooKeeper/KRaft, topic configs, partition management, replication tuning | Low: single Redis instance | Redis |
| **Learning curve** | steep: producers, consumers, acks, offsets, retention, compaction | shallow: XADD, XREADGROUP, XACK | Redis |
| **Managed cost** | Confluent Cloud too expensive at scale; self-hosted requires dedicated infra engineer | Uses existing Redis | Redis |
| **Exactly-once** | Native exactly-once semantics via transactions | Requires consumer-side idempotency | Kafka (native) |
| **Throughput** | Millions/sec (overkill for requirements) | 100K+ sec (well above 5K target) | Tie |
| **Ecosystem** | Schema registry, Kafka Connect, Streams API, many integrations | Simpler but less extensive | Kafka |

**Technical Assessment:**

- **Throughput**: Kafka's million-event/second capacity far exceeds the 5,000 events/second 10x growth target. This capability would remain largely unused.
- **Ordering**: Both provide strong ordering guarantees (Kafka: per-partition; Redis: per-stream).
- **Retention**: Kafka's configurable retention (hours to years) exceeds Redis Streams' typical retention windows, but the 7-day replay window is sufficient for debugging.
- **Consumer groups**: Both have mature consumer group implementations with offset management.
- **Exactly-once**: Kafka provides native exactly-once semantics; Redis requires a deduplication layer. For billing notifications, the idempotency implementation is straightforward (store deduplication keys with TTL).

**The deciding factors were:**

1. **No Kafka experience** + **no dedicated infrastructure engineer** means a 2-week timeline is unrealistic for production-ready Kafka
2. **Existing Redis investment** makes marginal cost of Redis Streams near zero
3. **Operational overhead** of Kafka (even in KRaft mode) requires specialized knowledge the team lacks

Kafka is the right choice for organizations with dedicated platform/infrastructure teams, throughput requirements exceeding 100K events/second, or multi-team event-driven architectures. For this team and scale, the complexity-to-benefit ratio is unfavorable.

---

## Implementation Notes

### Proposed Architecture

```
Flask App                    Redis Streams              Worker Pool
    |                             |                          |
    |-- XADD notifications:mail --->                          |
    |-- XADD notifications:webhook--->                        |
    |-- XADD notifications:billing--->                       |
    |                             |                          |
    |                        Stream                          |
    |                  (notifications:*)                     |
    |                             |                          |
    |                             |<--- XREADGROUP -------->|
    |                             |         (consumer group) |
    |                             |                          |
    |                             |<--- XACK after success --|
```

### Critical Implementation Requirements

1. **Billing notifications**: Implement idempotency via `SETNX notify:dedup:{id} TTL(24h)` before processing
2. **Retry logic**: Use `XPENDING` to detect stuck messages; re-deliver after visibility timeout
3. **Dead-letter queue**: Route to `notifications:dlq` after max retries
4. **Visibility timeout**: Start at 30 seconds; tune based on observed processing times
5. **Monitoring**: Export stream lengths and consumer lag to Prometheus

---

## Summary

| Requirement | Redis Streams Support |
|-------------|----------------------|
| Async decoupling from HTTP | ✓ Via XADD, XREADGROUP |
| Retry with exponential backoff | ✓ Via XPENDING + re-read |
| At-least-once delivery | ✓ Native via XACK |
| Exactly-once for billing | ✓ Consumer-side idempotency |
| 10x growth capacity | ✓ 100K+ events/sec capacity |
| 2-week delivery | ✓ Familiar technology, fast integration |
| Real-time WebSocket (future) | ✓ Redis pub/sub available |

**Recommendation**: Proceed with Redis Streams. The team can deliver a production-ready notification subsystem within the 2-week constraint, leveraging existing infrastructure and avoiding the operational complexity of Apache Kafka at this scale.