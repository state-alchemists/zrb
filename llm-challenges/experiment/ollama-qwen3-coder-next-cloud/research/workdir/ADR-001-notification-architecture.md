# ADR-001 — Notification Subsystem Architecture: Redis Streams

- **Status**: Proposed
- **Date**: 2026-05-17

## Context

The current notification implementation is synchronous, blocking HTTP responses and causing cascading failures when external services (email providers, webhook endpoints) are slow or down. Metrics show 2M notifications per month with peak traffic of 500 requests/second. The system must guarantee at-least-once delivery for billing events and exactly-once semantics where feasible.

Engineering constraints:

- Team: 6 engineers (3 senior, 3 mid-level), no dedicated infrastructure engineer
- Existing infrastructure: PostgreSQL, Redis (production-proven for sessions/rate limiting), 4 web servers on AWS
- No Kafka experience on the team
- Must complete setup/migration within 2 weeks
- Budget constrained: cannot afford managed Confluent Cloud
- No re-architecture allowed for 10× growth

## Decision

We will use **Redis Streams** as the async messaging backbone for the notification subsystem.

Redis Streams provides sufficient throughput (100K+ messages/second per instance), built-in consumer groups with offset tracking, and support for exactly-once delivery when combined with client-side deduplication IDs. Its simple operational model (single server, standard replication) matches our team size and timeline constraints.

## Rationale

**Throughput capacity**: Redis Streams can handle 100K+ messages/second per instance in production. Our current rate is ~2M/month (≈700/day or ~1 msg/s average), and even at 10× growth we peak at ≈10 msg/s — well below capacity. Kafka would be overkill.

**Exactly-once semantics**: We implement deduplication by assigning each notification a unique `dedup_id` in the message payload. The consumer maintains a Redis SET of processed `dedup_id`s with TTL (e.g., 7 days). Before processing, the consumer checks the SET; if present, it ACKs the message without re-processing. This gives exactly-once behavior at the application level. Kafka offers native exactly-once semantics but only with complex coordination (idempotent producers, transactional APIs) that the team does not yet know.

**Operational match to team constraints**: We already operate Redis in production for sessions and rate limiting. On-call engineers understand Redis CLI (`redis-cli`, `MONITOR`, `INFO`), persistence (`RDB`/`AOF`), and common failure modes. Adding Streams adds minimal cognitive overhead: same tool, same monitoring, same disaster recovery. Kafka would require learning ZooKeeper/KRaft, broker configuration, replication factors, consumer group rebalancing, and tune parameters like `log.segment.bytes` and `replica.fetch.max.bytes` — a steep learning curve for 6 engineers with no dedicated infra person and a 2-week delivery wall.

**Retry and dead-letter handling**: Redis Streams gives us offset-based redelivery when messages are not ACKed. Combined with a simple consumer that implements exponential backoff (e.g., `EXPIRE dedup_id key_in_seconds = min(2^attempts * base_delay, max_delay)`), we achieve robust retry behavior. We store the `attempt_count` in the message JSON and increment it on each retry. After N attempts (e.g., 5), the consumer moves the message to a dedicated `notifications:dead_letter` stream. This is a one-day implementation, whereas Kafka would require configuring dead-letter topics and reconciling offset gaps.

**Upgrade path to WebSocket push**: Per the scaling target, we must add WebSocket push notifications within two quarters. Redis Streams consumers can publish events to Redis Pub/Sub for the WebSocket gateway to consume, or we can add a secondary consumer group that writes to Redis Stream `ws:notifications` that the WebSocket service reads. The same Redis instance supports both patterns — no additional infrastructure needed. With Kafka, we would need a dedicated cluster for WebSocket traffic or add a separate streaming pipeline (Flink/Kafka Streams), increasing complexity.

## Alternatives Considered

**Apache Kafka**

- *Rejected because*: Kafka’s throughput, partitioning, and exactly-once semantics are valuable for high-scale, high-complexity systems. However, Kafka introduces operational complexity: cluster management, broker configuration, replication, and troubleshooting rebalance storms. Our team has zero Kafka experience, and onboarding would consume more than the 2-week budget. The budget cannot cover Confluent Cloud at full scale, and self-hosted Kafka on EC2 would require dedicated infra time we don’t have. For our 10 msg/s (even at 10× peak), Kafka adds complexity our current problems do not justify.

**Database-backed queue (PostgreSQL NOTIFY/LISTEN or polling)**

- *Rejected because*: While PostgreSQL is already in use, it is optimized for transactional consistency, not message queuing. Implementing a queue on top of PostgreSQL risks blocking the primary database during notification bursts, exacerbating the latency issue we’re trying to solve. Retry and dead-letter handling would require custom logic with no built-in guarantee of exactly-once delivery. The existing PostgreSQL primary + read replica topology is already at capacity; adding queue I/O increases risk of timeouts and replication lag.

## Consequences

**Positive**:

- Minimal operational overhead: reuse existing Redis monitoring (e.g., `redis-cli info`, Prometheus exporter) and alerting.
- Fast iteration: consumer implementation in Python/Flask is straightforward using `redis-py` streams API; first version can be delivered in <3 days.
- Exactly-once billing notifications implemented at the application layer (dedup_id + SET) without infrastructure changes.
- Easy integration with future WebSocket gateway (same Redis instance, same API pattern).

**Negative**:

- Redis Streams does not natively support message compaction or tiered storage. Message retention is bounded by memory/disk capacity; we must configure `maxmemory-policy allkeys-lru` and monitor disk usage. For our volume (≈1 msg/s, 30-day retention = ~2.5M messages), this is negligible — memory footprint <200 MB.
- No built-in replication lag detection for consumers. We must implement consumer health checks (e.g., monitor lag via `XINFO GROUP` and alert if `lag > threshold`).
- Redis single-primary architecture: if the Redis node fails, we lose in-flight messages unless `appendonly yes` and `fsync always` are configured (latency trade-off). We accept this because notifications are not financial transactions; we prioritize availability over zero-loss delivery, and we rely on consumer-side dedup to handle reordering on recovery.

**Follow-ups**:

1. Implement consumer health alerts: monitor `pending_messages` and `lag` per consumer group in `XINFO GROUP notifications`.
2. Add retry metrics (attempts histogram, dead-letter queue size) to Prometheus.
3. Document deduction_id generation (UUID v7, timestamp + instance_id) in code comments.
4. Within two quarters, build Redis Pub/Sub → WebSocket gateway sidecar to support real-time push.
