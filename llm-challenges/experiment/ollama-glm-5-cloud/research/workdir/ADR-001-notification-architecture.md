# ADR-001: Notification Subsystem Architecture

## Status

**Proposed** — awaiting team review

## Context

Our project management SaaS platform has outgrown its synchronous notification system. With 85,000 MAU, ~2M tasks/month, and peak traffic of ~500 req/s, the current architecture—where notifications are sent inline during HTTP requests—is causing:

- **Request timeouts**: 800ms average latency, spiking to 8s during peaks
- **Silent failures**: No retry or dead-letter queue for failed deliveries
- **Cascading failures**: Slow webhook endpoints have caused two production incidents via connection pool exhaustion
- **No delivery guarantees**: Billing-critical notifications require exactly-once delivery

We need to decouple notification processing from the request cycle with async processing, retries, delivery guarantees, and support for future WebSocket push notifications.

### Constraints

| Constraint | Impact |
|------------|--------|
| 6-person team, no dedicated infra engineer | Operational simplicity is critical |
| Redis already in production | Familiarity and existing infrastructure |
| No Kafka experience | Steep learning curve risk |
| ≤2 weeks to deliver value | Rapid iteration required |
| Modest budget | Self-hosted solutions preferred |
| Exactly-once for billing notifications | Requires idempotency or transactional processing |

## Decision

**We will use Redis Streams** for the notification subsystem.

### Justification

| Factor | Apache Kafka | Redis Streams | Winner |
|--------|--------------|---------------|--------|
| **Time to value** | 3–4 weeks minimum (learning curve, cluster setup, Zookeeper/KRaft config) | <1 week (team knows Redis, single-node to start) | Redis Streams |
| **Operational complexity** | High — requires cluster management, partition planning, monitoring of brokers, controller | Low — Redis already operated, single-node adequate for 500 req/s | Redis Streams |
| **Team experience** | None | Moderate (Redis for sessions/rate limiting) | Redis Streams |
| **Throughput capacity** | 100K+ msg/s per broker | 1M+ msg/s per node (STREAM operations are O(1) to O(N) with small N) | Tie (both sufficient) |
| **Message ordering** | Per-partition ordering guaranteed | Per-stream ordering guaranteed | Tie |
| **Consumer groups** | Mature, built-in rebalancing | XGROUP-based, manual rebalancing needed for scaling | Kafka |
| **Message retention** | Configurable, days to weeks by default | Configurable via MAXLEN or XTRIM, typically hours-days | Kafka |
| **Exactly-once semantics** | Native via transactions (EOS v2), idempotent producers | At-least-once by default; exactly-once via idempotency keys + deduplication | Kafka (simpler) |
| **Cost** | Self-hosted requires 3+ nodes minimum for fault tolerance; managed Confluent exceeds budget | Redis already paid; single-node sufficient at current scale | Redis Streams |
| **WebSocket readiness** | Requires separate layer (Kafka doesn't push) | Requires separate layer (Redis Streams doesn't push) | Tie |

The deciding factors:

1. **Team capacity**: With 6 engineers and no dedicated infrastructure role, adding Kafka operational burden is untenable. Redis Streams lets us leverage existing skill sets.

2. **Time to production**: We can implement Redis Streams consumers in Flask within days using `redis-py`. Kafka would require weeks of learning and cluster setup before writing application code.

3. **Scale fit**: Our 500 req/s peak is ~1.3M notifications/day. Redis Streams handles millions of operations per second—the workload is trivial for it. Kafka's superior throughput (1M+ msg/s per cluster) offers no practical advantage at 10x scale.

4. **Exactly-once is achievable**: Kafka's native exactly-once semantics are cleaner, but Redis Streams can achieve equivalent guarantees through:
   - Idempotency keys in notification payloads (UUID v4)
   - Consumer group acknowledgments (XACK)
   - Downstream deduplication in notification handlers (check processed_keys table before processing)
   
   This adds ~50 lines of application code—a reasonable tradeoff for avoiding Kafka's operational load.

5. **Future-proofing**: Both systems can scale to 10x traffic. If we later need Kafka's strengths (multi-datacenter replication, stream processing with ksqlDB, week-long retention), we can migrate notification events. The architecture remains decoupled either way.

## Consequences

### Pros

- **Fast implementation**: We can ship a working prototype in <1 week and production-ready code within the 2-week constraint
- **Reduced operational overhead**: One less distributed system to learn, monitor, and debug
- **Team confidence**: Engineers can debug Redis issues; fewer new failure modes
- **Cost efficiency**: No new infrastructure spend beyond what we already operate
- **Adequate scale headroom**: Redis Streams easily handles 10x our current throughput
- **Consumer groups built-in**: XREADGROUP + XACK provides reliable message consumption with retry semantics via XPENDING
- **Dead-letter queue pattern achievable**: Failed notifications after N retries can be XADD'd to a dead-letter stream for manual inspection

### Cons

- **No native exactly-once**: We must implement idempotency at the application layer. A processed_notifications table (notification_id, processed_at) is required for billing notifications. This is additional code and a database round-trip per notification.
- **Manual consumer rebalancing**: If we scale to multiple consumer instances, we'll need to implement XGROUP CREATE across multiple consumers and handle rebalancing logic. Kafka handles this automatically.
- **Shorter retention by default**: Redis Streams use memory. With MAXLEN we cap stream size, but if we need week-long retention for audit purposes, memory costs grow. We'll set MAXLEN ~1000000 (~2GB at ~2KB/msg) and backfill expired messages to S3 if needed.
- **No native stream processing**: Kafka offers Kafka Streams / ksqlDB for complex event processing. If we need notification aggregation (e.g., "user received 50 emails today, batch them"), we write custom code. This is acceptable—we have no streaming queries today.
- **Future migration risk**: If we eventually outgrow Redis (multi-region, massive scale, complex stream processing), migration to Kafka requires rewriting the producer/consumer layer. We mitigate this by keeping the interface abstracted behind a `NotificationQueue` class.

## Alternatives Considered

### Apache Kafka

**Why we rejected it:**

Kafka is architecturally superior for exactly-once delivery, consumer group management, and long-term retention. However:

- **Learning curve**: The team has zero Kafka experience. We would incur 1–2 weeks of learning before delivering notification logic. This violates the 2-week time-to-value constraint.
- **Operational burden**: Maintaining a Kafka cluster (even self-hosted on AWS) requires expertise in broker management, partition rebalancing, monitoring, and failure recovery. With no dedicated infra engineer, this burden falls on already-stretched backend engineers.
- **Marginal benefit at current scale**: Kafka's throughput advantage (10x–100x Redis) offers no practical benefit at 500 req/s. We would pay complexity cost for unused capacity.
- **Budget constraints**: Managed Kafka (Confluent Cloud, AWS MSK) would exceed our budget at projected scale. Self-hosting requires minimum 3 brokers for fault tolerance—significant EC2 cost plus engineering time.
- **Overkill for the problem**: We need async processing with retries. Kafka's strengths (event sourcing, stream processing frameworks, multi-datacenter replication) are not requirements for this subsystem.

We would revisit Kafka if:
- Multi-region deployment becomes a hard requirement
- We need week-long+ message retention with replay for analytics
- We adopt CQRS/event sourcing as architectural patterns
- Throughput exceeds Redis's single-node capacity (~1M msg/s)

### Other Alternatives Considered and Dismissed

| Option | Why Dismissed |
|--------|---------------|
| **Database queue (Postgres)** | Polling is inefficient; no blocking reads; row locking at high concurrency causes contention; already have connection pool exhaustion issues |
| **Celery + Redis** | Celery adds complexity for simple stream semantics; XREADGROUP provides equivalent functionality with less abstraction; we'd still need Redis Streams or a backing store |
| **RabbitMQ** | Another new system to learn; team already knows Redis; not materially simpler than Kafka; message ordering guarantees weaker than Redis Streams |
| **Amazon SQS** | Vendor lock-in; current infrastructure not AWS-only; cost grows unpredictably with 10x scale; no ordering guarantees within queues without FIFO queues (additional cost) |
| **Cloud Pub/Sub (GCP)** | Same concerns as SQS; team has AWS expertise, not GCP |

---

## Implementation Notes

The implementation should:

1. **Abstract the queue interface**: Create a `NotificationQueue` class with methods `enqueue(notification)` and `consume(callback)`. This allows future migration to Kafka with minimal code changes.

2. **Use consumer groups**: 
   ```python
   # Producer
   redis.xadd('notifications:billing', {'data': json.dumps(notification)}, id='*')
   
   # Consumer
   redis.xreadgroup('notifications:billing', 'billing-consumer', id='>')
   ```

3. **Implement idempotency for billing events**:
   ```python
   if not db.query("SELECT 1 FROM processed_notifications WHERE id = ?" , [notification_id]):
       send_notification(notification)
       db.execute("INSERT INTO processed_notifications VALUES (?)" , [notification_id])
   redis.xack('notifications:billing', 'billing-consumer', message_id)
   ```

4. **Set MAXLEN appropriately**: `XTRIM` or `MAXLEN ~ 1000000` to bound memory usage.

5. **Dead-letter stream**: After 5 failed XACK attempts, move to `notifications:deadletter` with error metadata.

6. **Monitor XPENDING**: Use `XPENDING` to detect stuck messages and alert on growing lag.

## Review History

| Date | Reviewer | Outcome |
|------|----------|---------|
| — | — | Pending |