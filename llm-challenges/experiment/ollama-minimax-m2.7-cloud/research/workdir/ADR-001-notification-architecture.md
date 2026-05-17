# ADR-001: Notification Subsystem Message Broker Selection

**Status:** Proposed

---

## Context

### Problem Statement

The notification module currently sends emails and webhooks synchronously inside the HTTP request cycle. This causes:

- **Request timeouts**: 800ms average latency, spikes to 8s during peak hours
- **Silent failures**: Dropped notifications when email providers or webhook endpoints are unavailable, with no retry or dead-letter handling
- **Cascading failures**: Connection pool exhaustion from slow webhook endpoints has twice caused platform-wide incidents
- **Missing delivery guarantees**: Billing-critical notifications (trial expired, payment failed) lack exactly-once guarantees

### Scaling Requirements

- Decouple notifications from the HTTP request cycle (async processing)
- Retry with exponential backoff
- At-least-once delivery for billing events; exactly-once where feasible
- WebSocket push notifications within 2 quarters
- Handle 10x traffic growth without re-architecting

### Constraints

| Constraint | Implication |
|------------|-------------|
| 6-person engineering team (3 senior, 3 mid-level) | No dedicated infrastructure engineer; operational burden must be minimal |
| No Kafka experience | Kafka has significant learning curve for operations |
| 2-week maximum setup/migration window | Must deliver value quickly; cannot spend months on infrastructure |
| Modest budget | Cannot afford managed Confluent Cloud at scale |
| Already running Redis in production | Leveraging existing infrastructure reduces operational complexity |
| Must maintain exactly-once semantics for billing notifications | Non-negotiable for billing-critical events |

### Traffic Profile

- **Current load**: ~500 req/s peak, ~2M tasks/month
- **10x growth target**: ~5,000 req/s peak (still modest for most message brokers)

---

## Decision

**Chosen Option: Redis Streams**

### Justification

Redis Streams is the correct choice given the team size, existing Redis footprint, timeline, and operational constraints. The decision rests on four pillars:

**1. Operational familiarity eliminates ramp-up risk.**

The team already operates Redis for session storage and rate limiting. Redis Streams is an extension of that same Redis engine—no new systems, no new operational runbooks, no new monitoring dashboards. Kafka would require the team to learn broker configuration, topic partitioning strategies, ZooKeeper/KRaft quorum management, and consumer group offset semantics under production pressure.

**2. Two-week constraint is realistic with Redis, unrealistic with Kafka.**

A production-ready Kafka deployment on AWS (EC2-based, self-managed) requires: cluster sizing, broker configuration, replication factor decisions, partition count planning, consumer group implementation, and monitoring setup. Even with experienced teams, a safe Kafka rollout takes 4–6 weeks. Redis Streams can be integrated in days using existing Redis clients (e.g., `redis-py` with stream support), with the worker process being a simple Python consumer.

**3. Sufficient throughput headroom.**

At 500 req/s peak (projecting to 5,000 req/s at 10x growth), Redis Streams comfortably handles the workload. Redis Streams sustains 500K–1M events/second on commodity AWS instances—two orders of magnitude above current and projected needs. Kafka's throughput advantage is irrelevant at this scale.

**4. Exactly-once via consumer groups + idempotency.**

Redis Streams consumer groups provide at-least-once delivery. Exactly-once for billing notifications is achieved by combining consumer group acknowledgment with idempotent notification handlers (e.g., deduplication keys stored in Redis or PostgreSQL). This pattern is well-understood and straightforward to implement.

---

## Consequences

### Benefits of Redis Streams

| Benefit | Detail |
|---------|--------|
| **Minimal operational overhead** | Runs on existing Redis infrastructure; no new services to monitor |
| **Fast implementation** | Python `redis-py` streams API is straightforward; 2-week delivery is achievable |
| **At-least-once delivery** | Consumer groups ensure messages are not lost; acknowledgment-based processing |
| **Exactly-once for billing** | Combine consumer group + deduplication table (e.g., `notification_id` in PostgreSQL) |
| **Ordered processing** | Streams maintain insertion order; consumers process sequentially per stream |
| **Consumer groups** | Multiple workers can share load; supports independent scaling of email vs. webhook processors |
| **Retention configurable** | `MAXLEN` or `MINID` policies control disk usage; up to 512GB per stream |
| **XREADGROUP blocking** | Efficient polling without busy-waiting; sub-millisecond wake latency |
| **Existing team expertise** | Redis CLI, monitoring, and troubleshooting skills transfer directly |

### Drawbacks of Redis Streams

| Drawback | Mitigation |
|----------|------------|
| **No native dead-letter queue** | Implement manually using a separate stream (`notifications.dlq`) for failed messages after max retries |
| **Single-node throughput ceiling** | For 10x growth (5,000 req/s), a single Redis node is likely sufficient; cluster mode available if needed |
| **No native message replay by timestamp** | Use `XREAD` with stream IDs for cursor-based replay; suitable for our use case |
| **Less ecosystem than Kafka** | Kafka Connect, schema registry, and stream processing are richer; not needed for this use case |
| **Persistence tied to Redis config** | Redis RDB/AOF settings must be tuned for message durability (see below) |
| **Stream trimming on `MAXLEN`** | Messages may be trimmed before acknowledgment if consumer is slow; use `MAXLEN ~` (approximate trimming) or `MINID` to avoid losing unacknowledged messages |

### Configuration Requirements

To meet durability and ordering requirements:

```python
# Ensure Redis persistence for durability
# redis.conf: appendonly yes (AOF) + appendfsync everysec

# Stream creation with approximate trimming to prevent losing unacknowledged messages
redis.xadd("notifications", "*", payload, maxlen=100_000, approximate=True)

# Consumer group for at-least-once delivery
redis.xgroup_create("notifications", "notification-workers", id="0", mkstream=True)

# Blocking read with 5-second timeout
messages = redis.xreadgroup("notification-workers", "worker-1", {"notifications": ">"}, count=10, block=5000)
```

---

## Alternatives Considered

### Apache Kafka

| Criteria | Kafka | Redis Streams |
|----------|-------|---------------|
| **Throughput** | 1M+ events/sec | 500K–1M events/sec |
| **Ordering** | Per-partition | Per-stream |
| **Message retention** | Days/weeks/months, configurable | Up to 512GB per stream |
| **Consumer groups** | Yes, mature | Yes, functional |
| **Exactly-once semantics** | Native transactions | Consumer group + idempotency |
| **Operational complexity** | **High** — brokers, ZooKeeper/KRaft, partition rebalancing, leader election | **Low** — single Redis instance |
| **Setup time** | 4–6 weeks (inexperienced team) | 3–5 days |
| **Team familiarity** | No experience | Existing knowledge |
| **Infrastructure cost** | 3+ broker nodes for HA | Leverages existing Redis |

**Why Kafka was rejected:**

Kafka's strengths (millions of events/second, global message compaction, infinite retention, battle-tested exactly-once semantics) are not relevant to our current scale. Its weaknesses—operational complexity, unfamiliarity, extended setup timeline, and infrastructure cost—are fatal given our constraints.

Specifically:
- A production Kafka cluster requires minimum 3 brokers for HA, plus ZooKeeper (or KRaft in newer versions). On AWS, this means 3+ EC2 instances at `$0.10–$0.30/hour` each, plus EBS volumes.
- The team has zero Kafka operational experience. Debugging `UnderMinISR` errors, partition rebalancing storms, and consumer lag spikes requires knowledge the team does not have.
- Two weeks is insufficient to go from zero Kafka knowledge to a production-ready deployment. A rushed Kafka rollout would introduce reliability risks that outweigh its theoretical benefits.
- Kafka is designed for event sourcing and log aggregation at internet scale. Our use case—decoupled notification delivery at 5,000 req/s—is well within Redis Streams' capabilities.

Kafka would be the correct choice if we had: a dedicated platform/infrastructure team, petabyte-scale data, complex stream processing requirements, or multi-team event mesh architecture. None of these apply.

---

## Recommendation Summary

**Use Redis Streams.**

Implement notification processing as follows:

1. **Producer**: Webhook endpoint enqueues to `notifications` stream; returns 202 immediately
2. **Consumer workers**: `XREADGROUP` blocks waiting; processes with acknowledgment
3. **Retry logic**: On failure, increment retry counter; re-enqueue with backoff delay (using `ZADD` on a `notifications.retry` sorted set with score = `now + backoff_ms`)
4. **Dead-letter handling**: After 5 retries, move to `notifications.dlq`; alert on non-empty DLQ
5. **Exactly-once for billing**: Store `notification_id` + `delivered_at` in PostgreSQL; check before processing; skip if duplicate
6. **WebSocket push**: Future phase—reuse `notifications` stream to fan out to WebSocket workers via separate consumer group

This architecture delivers value within the 2-week constraint, leverages existing Redis expertise, and scales to 10x growth without re-architecting.