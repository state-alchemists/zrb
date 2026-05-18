# ADR-001: Notification Subsystem Architecture

## Status

**Proposed**

## Context

### Problem Statement

The notification module currently processes emails and webhooks synchronously inside the HTTP request cycle. This causes:

1. **Request timeouts**: Average latency 800ms, spikes to 8s during peak hours
2. **Silent failures**: Dropped notifications when providers are unavailable, no retry mechanism
3. **Cascading failures**: Two incidents where slow webhooks exhausted connection pools, affecting unrelated features
4. **No delivery guarantees**: Billing-critical notifications lack exactly-once semantics

### System Scale

| Metric | Value |
|--------|-------|
| Monthly Active Users | 85,000 |
| Tasks Created/Month | ~2,000,000 |
| Peak Throughput | ~500 req/s |
| Target Growth | 10x without re-architecting |

### Constraints

- **Team**: 6 engineers (3 senior, 3 mid-level), no dedicated infrastructure engineer
- **Existing infrastructure**: Redis deployed for sessions and rate limiting
- **Kafka experience**: None on the team
- **Migration timeline**: Must deliver value within 2 weeks
- **Budget**: Modest; cannot afford managed Confluent Cloud at full scale
- **Delivery guarantee**: Exactly-once semantics required for billing notifications

---

## Decision

**Recommendation: Redis Streams**

Redis Streams is the correct choice given our team size, existing Redis expertise, migration timeline, and operational constraints.

---

## Alternatives Considered

### Option A: Apache Kafka

Kafka is a mature, high-throughput distributed streaming platform. It provides per-partition ordering, configurable retention (hours to years), native consumer groups, and exactly-once semantics via transactions API.

| Property | Kafka | Assessment |
|----------|-------|------------|
| Throughput | Millions of msg/s | Exceeds our needs by 2-3 orders of magnitude |
| Ordering | Per-partition guaranteed | Excellent |
| Retention | Configurable, persistent | Excellent |
| Consumer groups | Native, robust | Excellent |
| Exactly-once | Transactions API | Supported, but complex |
| Operational complexity | High | Significant: requires ZooKeeper/KRaft, topic partitions, replication factor, consumer group offset management, dedicated monitoring |

**Why rejected:**

1. **Zero Kafka experience**: Team faces a steep learning curve (topics, partitions, consumer groups, offset management, replication, leader election). The 2-week migration deadline becomes unrealistic.
2. **Operational burden**: Self-managed Kafka requires expertise we do not have. Without a dedicated infrastructure engineer, troubleshooting broker failures, partition rebalancing, and consumer lag becomes a significant risk.
3. **Over-engineering**: At 500 req/s peak, we require roughly 10-50K msg/s including notification retries. Kafka's architecture (designed for millions/sec) introduces unnecessary complexity for our scale.

### Option B: Redis Streams (Selected)

Redis Streams is a persistent, append-only log data structure with consumer group support. It inherits all benefits of our existing Redis deployment.

| Property | Redis Streams | Assessment |
|----------|--------------|------------|
| Throughput | 100K-1M msg/s | Far exceeds our 500 req/s peak + 10x growth |
| Ordering | Per-stream guaranteed (XADD/XREAD) | Excellent |
| Retention | Configurable max length (~16M entries on 64-bit) | Sufficient for notification use case |
| Consumer groups | Native (XREADGROUP) | Equivalent to Kafka consumer groups |
| Exactly-once | Consumer-side idempotency keys | Achievable with simple deduplication table |
| Operational complexity | Low | Same deployment as existing Redis; no new systems |

---

## Consequences

### Pros of Redis Streams

1. **Familiar operational model**: Team already manages Redis for sessions and rate limiting. Monitoring, backups, and failover procedures already exist.
2. **Rapid delivery**: Minimal new concepts. Redis Streams commands (`XADD`, `XREAD`, `XREADGROUP`, `XACK`) are easily learned in days.
3. **Sufficient scale**: 100K-1M msg/s throughput accommodates our 500 req/s peak with 200x-2000x headroom. 10x growth target is trivially handled.
4. **Existing infrastructure**: No new servers, no new monitoring systems, no new operational runbooks.
5. **Exactly-once for billing**: Implement via a `notification_deliveries` table with a unique constraint on message ID. The worker checks this table before processing; if the ID exists and is marked `delivered`, skip processing.
6. **Retry with exponential backoff**: Achieved by tracking pending entries (`XPENDING`) and rescheduling via a dead-letter stream pattern.
7. **WebSocket readiness**: Redis Pub/Sub or Streams can feed a WebSocket fan-out service when we add real-time push notifications within 2 quarters.

### Cons of Redis Streams

1. **Retention limit**: Streams cap at ~16M entries (4GB on 64-bit). For our volume (~2M tasks/month × 3 notifications × 30-day retry window ≈ 180M entries worst case), we need to set `MAXLEN` appropriately or use `MINID` trimming. Mitigation: trim aggressively and rely on the idempotency table for replay safety.
2. **Not a message queue**: Redis Streams is an append-only log, not a full-featured message broker. We must implement consumer group offset management manually (though `XACK` handles this).
3. **Exactly-once complexity**: Requires consumer-side deduplication logic. Kafka's transactions API provides this natively, but the implementation overhead is manageable with a simple database table.

---

## Technical Specification

### Exactly-Once Delivery for Billing Notifications

```
# Worker pseudocode
def process_notification(message):
    notification_id = message['id']
    
    # Idempotency check using existing PostgreSQL
    with conn.cursor() as cur:
        cur.execute("""
            SELECT status FROM notification_deliveries 
            WHERE id = %s
        """, (notification_id,))
        row = cur.fetchone()
        
        if row and row[0] == 'delivered':
            return  # Already processed, skip
        
        if row and row[0] == 'pending':
            # In-progress or failed, let XPENDING handle retry
            return
        
        # Mark as pending
        cur.execute("""
            INSERT INTO notification_deliveries (id, status, created_at)
            VALUES (%s, 'pending', NOW())
            ON CONFLICT (id) DO NOTHING
        """, (notification_id,))
    
    # Process notification
    send_email_or_webhook(message)
    
    # Mark as delivered
    cur.execute("""
        UPDATE notification_deliveries 
        SET status = 'delivered', delivered_at = NOW()
        WHERE id = %s
    """, (notification_id,))
```

### Retry with Exponential Backoff

```
# Dead-letter stream pattern
while True:
    messages = XREADGROUP group, consumer, streams=['notifications', '>'], count=10
    
    for message in messages:
        try:
            process_notification(message)
            XACK(stream, group, message.id)
        except transient_error:
            # Do not ACK; message remains pending
            # Reschedule via secondary index
            XADD('notifications-retry', '*', message)
        except permanent_error:
            XACK(stream, group, message.id)
            XADD('notifications-dlq', '*', message)
```

### Stream Configuration

```
# Stream creation with max length for 7-day retention at ~500 req/s
XADD notifications MAXLEN ~ 3000000 * event task:created payload {...}
```

---

## Recommendation Summary

| Factor | Redis Streams | Kafka |
|--------|---------------|-------|
| Team expertise | **Wins** | Loses |
| Time to value (<2 weeks) | **Wins** | Loses |
| Operational complexity | **Wins** | Loses |
| Throughput adequacy | **Wins** | Wins |
| Exactly-once semantics | **Wins** (with dedup) | Wins |
| Exactly-once complexity | **Wins** | Loses |
| 10x growth capacity | **Wins** | Wins |
| Future WebSocket support | **Wins** | Wins |
| Budget fit | **Wins** | Loses |

Redis Streams satisfies all requirements with existing infrastructure and team expertise. Kafka would be the right choice for a team with existing Kafka experience, dedicated platform engineers, and throughput requirements exceeding 100K msg/s. We have none of these.

---

## Appendix: Operational Considerations

If Redis Streams becomes insufficient (e.g., needing multi-datacenter replication or retention beyond 30 days), migrate to Kafka at that time. The notification producers are decoupled via a message schema; swapping the transport layer is a consumer-side change only.