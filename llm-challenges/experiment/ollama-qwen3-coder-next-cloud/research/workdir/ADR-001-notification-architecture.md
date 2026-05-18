# ADR-001: Notification Subsystem Architecture

## Status

Proposed

## Context

The current notification subsystem is synchronous and blocking, causing request timeouts, silent failures, cascading failures, and no delivery guarantees. We need to decouple notifications from the HTTP request cycle while meeting these requirements:

- Async processing with retry and exponential backoff
- At-least-once delivery for billing events, exactly-once where feasible
- Support 10x traffic growth (from ~66 notifications/sec to ~660+ notifications/sec)
- Real-time WebSocket push within 2 quarters
- Operational simplicity for a 6-person team with no dedicated infrastructure engineer

## Decision

**Choose Redis Streams** for the notification subsystem.

### Justification

1. **Throughput & Performance**: Redis Streams can handle 50,000+ operations/sec on a single instance, easily accommodating our current peak (660 msgs/sec) and 10x growth (6,600+ msgs/sec). Kafka would be overkill for this scale.

2. **Operational Simplicity**: We already run Redis in production for sessions and rate limiting. Adding Streams requires only enabling it (built into Redis 5.0+, no separate deployment). Kafka would require learning, deploying, and maintaining a cluster — a significant burden for a 6-person team without infrastructure expertise.

3. **Consumer Groups & Exactly-Once**: Redis Streams supports consumer groups with `XGROUP创建` and `XREADGROUP`. Combined withidempotent processing (using unique message IDs tracked in Redis Set), we can achieve exactly-once semantics for billing notifications without complex coordination.

4. **Message Retention & Retry**: Streams retain messages until explicitly acknowledged (`XACK`). Failed workers don't lose messages — unacknowledged messages reappear after a timeout (via `XPENDING`). This allows simple retry with exponential backoff in the consumer application logic.

5. **Budget & Timeline**: Redis Streams needs no new infrastructure cost or budget beyond our existing Redis setup. Setup is under 2 weeks (Redis is already configured; consumers are Python code changes). Kafka would require 4-6 weeks minimum for learning, deployment, and team ramp-up.

6. **Team Constraints**: Three team members have Redis experience (from current session/rate-limiting work). Zero team members have Kafka expertise. The risk of operational debt with Kafka is unacceptable.

## Consequences

### Positive
- **Fast delivery**: Async notifications reduce HTTP response time from 800ms+ to <50ms
- **Resilient**: Unacknowledged messages survive consumer crashes; retry logic is straightforward
- **Exactly-once billing**: Track processed message IDs in Redis Set (O(1) lookup); skip duplicate processing
- **Simple monitoring**: Redis CLI and `XPENDING`/`XLEN` commands provide visibility; no new dashboards needed
- **Future-ready**: Redis Streams consumer groups scale linearly with consumer processes; we can scale consumers independently on our existing AWS infrastructure

### Negative
- **Maximum scale ceiling**: Redis Streams works well up to ~100K msgs/sec on a single instance; Kafka would be needed for million-msg/sec scale. However, at 10x our current growth, we're only at ~6,600 msgs/sec — well within Redis capacity.
- **Durability trade-offs**: Redis default persistence (RDB/AOF) is good but not as durable as Kafka's disk-based immutable log. For billing notifications, we can configure AOF with `fsync=everysec` to mitigate.
- **Memory usage**: streams retain messages in memory until acknowledged/purged. We'll need to monitoring memory and potentially purge processed messages after a retention window (e.g., 7 days via `XTTL` or `XTRIM`).

## Alternatives Considered

### Apache Kafka

**Why rejected:**

1. **Operational complexity**: Kafka requires ZooKeeper or KRaft cluster management, topic configuration, replication factor decisions, and JVM tuning. Our team lacks Kafka experience — this introduces high risk of misconfiguration and operational incidents.

2. **Time to value**: Kafka deployment (even EKS-based) + team onboarding + consumption pattern implementation would take 4-6 weeks minimum. Our constraint is "2 weeks before delivering value."

3. **Cost**: Managed Kafka (MSK) or Confluent Cloud at our scale would cost $300-800/month vs. $0 incremental for Redis Streams (we pay for existing Redis instance).

4. **Over-engineering**: Kafka excels at high-throughput, long retention, many subscribers, and partition-based scaling. Our use case is simple: one topic (notifications), one consumer group (notification workers), and retention of days not months. Kafka's partitioning and replication features provide no benefit here.

5. **Synchronous batching inefficiency**: Our notification workload is bursty (spikes during business hours), not sustained high-throughput. Kafka's batch-based throughput optimization doesn't align with our pattern.

### Other Alternatives (No Action, RabbitMQ, etc.)

- **No action**: Cascading failures continue; billing events may be lost; compliance risk.
- **RabbitMQ**: More operational complexity than Redis, same queue semantics. Redis is already in our stack.
- **PostgreSQL LISTEN/NOTIFY**: Not designed for high-throughput; poor consumer group semantics; no built-in message acknowledgment.

## Implementation Steps

1. Enable Redis Streams (no config change needed if Redis ≥5.0)
2. Create notification stream: `XGROUP CREATE notifications notification-group $ MKSTREAM`
3. Update webhook/task-update endpoints to `XADD` to the stream instead of sending synchronously
4. Implement Python consumer with:
   - `XREADGROUP` with `STREAMS notifications >` (pending messages)
   - Idempotent processing via Redis Set lookup of `message-id`
   - Exponential backoff retry on failure
   - `XACK` after successful delivery
5. Implement dead-letter stream (`notifications:dlq`) for messages that exceed retry limit
6. Add monitoring: `XLEN notifications`, `XPENDING notifications notification-group` metrics

## Migration Backout Plan

If Redis Streams proves inadequate after 3 months:
- Write messages to both Redis Streams and Kafka (dual-write, <1 week work)
- Deploy Kafka consumers alongside Redis consumers
- Cut over traffic, decommission Redis Streams consumers

The architecture is designed so that switching to Kafka later is simply adding—not replacing—infrastructure.
