# ADR-001: Notification Subsystem Architecture

## Status

**Proposed**

## Context

Our SaaS project management platform handles ~85,000 monthly active users with peak traffic of ~500 requests/second. The current notification system sends emails and webhooks synchronously within HTTP requests, causing:

1. **Request timeouts** — Average latency 800ms, spikes to 8s during peak hours
2. **Silent failures** — No retry mechanism or dead-letter queue
3. **Cascading failures** — Slow webhook endpoints have exhausted connection pools twice this year
4. **No delivery guarantees** — Billing-critical notifications (trial expired, payment failed) lack exactly-once delivery

We need to decouple notifications from the HTTP request cycle, support retry with exponential backoff, guarantee at-least-once delivery (exactly-once for billing events), and handle 10x traffic growth.

### Constraints

| Factor | Constraint |
|--------|------------|
| Team | 6 engineers (3 senior, 3 mid-level), no dedicated infra engineer |
| Existing infrastructure | Redis already in production (session/rate limiting) |
| Team experience | No Kafka experience |
| Time-to-value | Must deliver value within 2 weeks |
| Budget | Modest — managed Confluent Cloud unaffordable at scale |
| Semantics | Exactly-once required for billing notifications |

### Traffic projections

- Current peak: ~500 req/s
- Target: 10x growth = ~5,000 req/s peak
- Notification volume: ~50-200 notifications/sec (estimated 10-40% of requests trigger notifications)

## Decision

**We will use Redis Streams for the notification subsystem.**

### Justification

Redis Streams is the correct choice given our constraints:

**1. Time-to-value (decisive factor)**

- Redis is already operational. Adding streams requires configuration changes and consumer code — days, not weeks.
- Kafka requires infrastructure provisioning, ZooKeeper/KRaft setup, security configuration, monitoring, and team training — at minimum 2-3 weeks before writing application code.
- The constraint "must not require more than 2 weeks of setup/migration work before delivering value" effectively rules out Kafka.

**2. Sufficient throughput**

- Redis Streams handles 100K+ messages/sec on modest hardware — orders of magnitude above our 10x growth target (5,000 req/s peak, ~200 notifications/sec).
- Kafka's throughput advantage (millions/sec) is irrelevant at our scale.

**3. Team capacity**

- 6-person team with no dedicated infrastructure engineer cannot afford the operational burden of Kafka cluster management (partition rebalancing, broker failures, replication lag monitoring, security patches).
- Redis Streams operational model matches existing team skillset.

**4. Consumer groups and delivery guarantees**

- Redis Streams XREADGROUP provides consumer group semantics with automatic message tracking.
- At-least-once delivery is native: failed consumers don't acknowledge, messages remain in pending list for retry.
- Exactly-once for billing events is achievable via idempotency keys (see Implementation section).

**5. Cost**

- No additional infrastructure beyond existing Redis instance (scale vertically or add replica).
- Kafka would require 3+ brokers minimum for production redundancy, plus operational tooling.

### Implementation details

**Exactly-once semantics for billing notifications**

Redis Streams provides at-least-once. We achieve exactly-once through idempotency:

```
Producer:
  message_id = uuid4()
  idempotency_key = f"billing:{message_id}"
  SETNX idempotency_key "processing" EX 86400  # 24h TTL
  XADD billing_stream * message_id <data> idempotency_key <key>

Consumer:
  # Check if already processed
  current = GET idempotency_key
  if current == "processed":
    XACK billing_stream group <message_id>
    return
  
  # Process notification
  send_email(...)
  
  # Mark processed (atomic transition)
  SET idempotency_key "processed"
  XACK billing_stream group <message_id>
```

This pattern ensures:
- Duplicate sends are ignored (idempotency key check)
- Failed processing is retried (message stays pending until ACK'd)
- Billing events processed exactly once under normal conditions

**Consumer group configuration**

```
# Create consumer group
XGROUP CREATE notifications notification_workers $ MKSTREAM

# Consumer loop (pseudo-code)
while True:
    messages = XREADGROUP GROUP notification_workers consumer-1 COUNT 10 BLOCK 5000 STREAMS notifications >
    for message in messages:
        try:
            send_notification(message)
            XACK notifications notification_workers message.id
        except Exception:
            # Leave in pending for retry; configure XCLAIM for retry logic
            log_error(message)
```

**Retry with exponential backoff**

- Use XCLAIM with idle time threshold to release stuck messages
- Implement backoff in consumer: track retry count in message metadata, apply `min(2^retry_count * 100ms, 30s)` delay
- After max retries (5), move to dead-letter stream

**WebSocket future-proofing**

- Redis Pub/Sub is already suitable for real-time WebSocket push
- Streams pattern translates directly: WebSocket server subscribes to stream, pushes to connected clients
- Can migrate to Kafka later if scale demands (streams pattern is abstract enough)

## Consequences

### Pros

1. **Fastest path to production** — Days to implement consumer code against existing Redis instance
2. **Lower operational burden** — Single Redis instance to monitor vs. Kafka cluster with multiple failure modes
3. **Team velocity** — Team works in familiar paradigm; no learning curve for infrastructure
4. **Cost-effective** — Uses existing infrastructure; scales vertically before needing horizontal
5. **Sufficient for 10x growth** — Throughput ceiling orders of magnitude above target
6. **Consumer groups built-in** — XREADGROUP + XACK provides at-least-once semantics out of the box
7. **Message persistence** — AOF/RDB persistence provides durability for critical notifications

### Cons

1. **No native exactly-once** — Must implement idempotency layer (adds ~50 lines of code per notification type)
2. **Memory-bound** — Message retention limited by available memory; long-term archival requires additional tooling
3. **Single point of failure** — Redis primary failure pauses notifications until failover (mitigate with Redis Sentinel or cluster mode)
4. **Less mature ecosystem** — Fewer operational tools vs. Kafka (Kafka Manager, Confluent Control Center, ksqlDB)
5. **Potential future migration** — If traffic exceeds Redis capacity or exactly-once requirements become stricter, migration to Kafka may be needed (cost: ~4 weeks engineering time)

## Alternatives Considered

### Apache Kafka

**Why rejected:**

| Factor | Kafka capability | Our constraint | Mismatch |
|--------|------------------|----------------|----------|
| Setup time | 2-4 weeks configuration | 2 weeks max | ✗ Exceeds window |
| Operational complexity | Requires broker management, partition planning, replication monitoring | 6-person team, no infra engineer | ✗ Insufficient capacity |
| Cost | Self-hosted: 3+ brokers, monitoring; Managed: Confluent Cloud | Modest budget | ✗ Not affordable at scale |
| Team experience | Requires Kafka expertise | No experience | ✗ Learning curve delays value |
| Throughput need | Millions/sec | ~200 notifications/sec projected | ✗ Overkill for current scale |
| Exactly-once | Native support | Required for billing | ✓ Strongly matches |

**Kafka would be appropriate if:**

- We were building a streaming analytics platform
- We had 100+ engineers and dedicated infrastructure team
- We needed 1M+ messages/sec throughput
- We already had cloud provider-managed Kafka available

**We should reconsider Kafka when:**

- Notification volume exceeds 50,000/sec
- We need long-term (7+ day) event replay capability
- We need native stream processing (aggregations, joins)
- Team expands and can invest in infrastructure expertise

### Hybrid approach (Redis Streams + eventual Kafka migration)

Considered starting with Redis and migrating to Kafka when scale demands. This is a valid strategy but the migration cost is real (~4 weeks of engineering time). Given current constraints and 10x scale target, Redis alone is sufficient — migration should only proceed if requirements exceed Redis capabilities.

## Recommendations

1. **Immediate**: Implement Redis Streams consumer on existing Redis instance (1 week)
2. **Week 2**: Add dead-letter stream, retry with backoff, idempotency layer for billing notifications
3. **Month 1**: Add Redis Sentinel for higher availability (minimal infrastructure addition)
4. **Quarter 2**: Evaluate WebSocket architecture using same Redis instance
5. **Quarter 4**: If notification volume exceeds 10,000/sec, begin Kafka evaluation for Year 2 migration

---

**Author**: Architecture Team  
**Date**: 2026-05-17  
**Reviewers**: Required (Backend Lead, Infrastructure)