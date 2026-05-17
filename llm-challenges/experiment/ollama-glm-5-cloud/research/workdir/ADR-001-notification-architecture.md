# ADR-001: Notification Subsystem Architecture

## Status

Proposed

## Context

The notifications module currently blocks HTTP requests, causing latency spikes (800ms average, 8s at peak), silent failures, and cascading outages. We need to decouple notification processing from the request cycle with the following requirements:

- **Throughput**: Handle current peak of ~500 req/s with headroom for 10x growth (~5,000 req/s)
- **Reliability**: At-least-once delivery for all notifications; exactly-once semantics for billing events
- **Features**: Retry with exponential backoff, dead-letter handling, and future WebSocket push support
- **Constraints**:
  - 6-person team (no dedicated infrastructure engineer)
  - No Kafka operational experience
  - 2-week maximum time to first value
  - Modest budget (self-managed infrastructure required)
  - Redis already deployed for sessions and rate limiting

## Decision

**Use Redis Streams** as the message backbone for the notification subsystem.

### Justification

Redis Streams is the pragmatic choice given our constraints. It provides sufficient technical capability while minimizing operational risk and time-to-production.

| Factor | Kafka | Redis Streams | Winner |
|--------|-------|---------------|--------|
| **Throughput at our scale** | Millions/sec | Hundreds of thousands/sec | Tie (both exceed 5,000 req/s comfortably) |
| **Consumer groups** | Mature, feature-rich | Supported since Redis 5.0, adequate for our needs | Tie |
| **Exactly-once semantics** | Native (transactions + idempotent producers) | Requires application-level deduplication | Kafka |
| **Message retention** | Days to months, configurable | Time or length-based, typically hours/days | Kafka |
| **Ordering guarantees** | Per-partition strict ordering | Per-stream strict ordering | Tie |
| **Operational complexity** | High (Zookeeper/KRaft, brokers, monitoring) | Low (single process, already deployed) | Redis |
| **Team experience** | None | Redis familiarity from sessions/rate limiting | Redis |
| **Time to production** | 4-8 weeks for proper setup | 1-2 weeks | Redis |
| **Infrastructure cost** | 3+ broker nodes minimum | Leverage existing Redis (may need memory upgrade) | Redis |

Redis Streams wins decisively on **operational fit**: our team has no Kafka expertise and no dedicated infrastructure engineer. Self-managing a Kafka cluster would introduce significant operational burden (broker failures, rebalances, Zookeeper/KRaft maintenance, monitoring stack) that a small team cannot absorb without delaying product work.

For **exactly-once semantics** on billing notifications, neither system provides true end-to-end exactly-once without application-level cooperation. Kafka's transactional semantics require careful producer/consumer configuration and idempotent downstream processing. With Redis Streams, we implement the same pattern: write a unique `message_id` to the stream (idempotency key), track processed IDs in PostgreSQL, and deduplicate on consumption. The effort is comparable.

## Consequences

### Pros

1. **Fast delivery**: 1-2 weeks to production vs. 4-8 weeks for Kafka, meeting the 2-week constraint
2. **Low operational overhead**: Single Redis instance (potentially clustered later) vs. multi-broker Kafka cluster
3. **Leveraged expertise**: Team already knows Redis; no new technology learning curve
4. **Cost-effective**: Uses existing infrastructure; no additional broker nodes required
5. **Adequate scale**: Redis Streams handles 100K+ messages/sec — well above our 5,000 req/s target
6. **Consumer group support**: Native `XREADGROUP` enables parallel consumers with visibility into pending messages
7. **Built-in retry tracking**: `XPENDING` command exposes unacknowledged messages for retry logic
8. **Path to WebSockets**: Same Redis instance can serve as a pub/sub backend for WebSocket message distribution

### Cons

1. **Limited retention**: Redis is memory-bound; message retention is typically hours, not weeks. Long-term archival (for audit/compliance) requires a separate mechanism (e.g., write-through to PostgreSQL or S3)
2. **No native exactly-once**: Billing notifications require application-level deduplication via PostgreSQL idempotency table
3. **Persistence model**: AOF/RDB snapshots provide durability, but less robust than Kafka's replicated log. A Redis crash with unwritten AOF could lose recent messages (mitigable with `appendfsync everysec` or `always`)
4. **Scaling ceiling**: Beyond ~50K-100K msg/sec, Redis Streams may require sharding or migration; Kafka scales more gracefully to extreme throughput
5. **Less ecosystem**: Fewer tooling options (monitoring, connectors, schema registry) compared to Kafka's mature ecosystem
6. **Single point of failure**: Requires Redis Sentinel or Cluster for HA; adds complexity as we scale

## Alternatives Considered

### Apache Kafka

Kafka is the industry standard for event streaming and would be the right choice for a different context: larger scale (millions of events/sec), long-term retention requirements, or a team with dedicated infrastructure engineers and Kafka expertise.

We rejected Kafka because:
- **Operational risk**: 6-person team with no Kafka experience and no infra specialist would struggle to operate Kafka correctly. Misconfiguration (producer `acks`, consumer offset management, replica placement) can cause data loss or outages.
- **Time violation**: Proper Kafka setup (cluster provisioning, security, monitoring, consumer group management) exceeds the 2-week constraint. Managed Confluent Cloud would reduce ops burden but violates budget constraints.
- **Over-engineering**: Our peak throughput (500 req/s, scaling to 5,000 req/s) is 2-3 orders of magnitude below Kafka's threshold. We would pay complexity costs for capability we do not need.

Kafka remains a viable **future migration target** if we hit Redis Streams' scaling limits (which would require 10-20x our projected peak) or need week/month-long retention for compliance.

### PostgreSQL SKIP LOCKED (Queue in Database)

Considered using PostgreSQL with `SELECT ... FOR UPDATE SKIP LOCKED` as a job queue. Rejected because:
- Polling-based consumption adds latency vs. event-driven streams
- Higher database load under high message throughput
- Less elegant consumer group semantics
- Redis Streams provides cleaner separation between transactional DB and async processing

### RabbitMQ

Considered as a traditional message broker. Rejected because:
- No team experience
- Adds a new infrastructure component (vs. leveraging existing Redis)
- Consumer groups and stream semantics less mature than Redis Streams for our use case
- Redis Streams provides comparable functionality with lower operational cost

## Implementation Notes

1. **Exactly-once pattern for billing**: Use PostgreSQL `notification_dedup` table with unique constraint on `message_id`. Consumer writes to this table before processing; duplicates are rejected at the database level.

2. **Retry logic**: Use `XPENDING` + `XCLAIM` to reassign timed-out messages. Implement exponential backoff by tracking retry count in message payload or a separate metadata store.

3. **Dead-letter queue**: After N retries, move messages to a separate `dlq` stream for manual inspection.

4. **WebSocket integration**: Use Redis Pub/Sub (`PUBLISH`/`SUBSCRIBE`) alongside Streams for real-time WebSocket push, or use the same stream with separate consumer groups.

5. **Persistence**: Configure Redis with `appendonly yes` and `appendfsync everysec` for durability. Consider upgrading to Redis Cluster if HA is required.

6. **Monitoring**: Track stream length (`XLEN`), pending messages (`XPENDING`), and consumer lag. Alert on growing backlog.