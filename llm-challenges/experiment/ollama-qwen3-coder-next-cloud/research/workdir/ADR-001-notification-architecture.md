# ADR-001 — Notification Subsystem: Choose Redis Streams Over Apache Kafka

- **Status**: Proposed
- **Date**: 2024-05-17

## Context

The current notification subsystem is synchronous, causing request timeouts (800 ms average, 8 s peaks), silent failures, cascading failures from slow webhooks, and no delivery guarantees for billing-critical events.

The system must be:
- Async to decouple notifications from request latency
- Support retry with exponential backoff
- Guarantee at-least-once delivery, exactly-once where feasible (billing events)
- Scale 10× without re-architecting (peak ~500 req/s → ~5,000 notifications/s)
- Support future real-time WebSocket push within 2 quarters

Constraints:
- Team: 6 engineers (3 senior, 3 mid), no dedicated infrastructure engineer
- Current Redis already in production (session/rate limiting)
- No Kafka experience on the team
- ≤2 weeks setup/migration before delivering value
- Budget: modest (no Confluent Cloud)
- Existing infrastructure: PostgreSQL, 4 web servers, nginx, Redis

## Decision

We choose **Redis Streams** for the notification subsystem.

Redis Streams provides sufficient throughput, built-in consumer groups with offset tracking, message acknowledgment for delivery guarantees, easy integration with existing Redis infrastructure, and requires minimal operational overhead—making it the right fit for our team size, experience, and budget constraints while meeting all functional requirements.

## Rationale

Throughput requirements are modest: ~500 events/s peak (2M tasks/month ÷ 30 days ÷ 24h ÷ 3600s ≈ 0.77 events/s baseline; peaks at 10× that = ~7.7 events/s, with bursts for task creation). Redis Streams handles [100,000+ messages/s per shard](https://redis.io/docs/data-types/streams/) in practice, far exceeding our needs.

Messaging guarantees:
- **At-least-once**: Redis Streams supports `XREADGROUP` with `GROUP` + `CONSUMER`, where consumers process and acknowledge (`XACK`) messages only after success. Failed messages remain in the pending entries list and can be re-delivered.
- **Exactly-once**: Implement deduplication via a Redis SET keyed by notification ID (stored with message metadata), cleared after successful delivery. This is simpler than Kafka's transactional producer + exactly-once semantics (EOS) which require coordination across producer and consumer.

Consumer groups and parallelism:
- Multiple worker processes can join the same consumer group, each consuming from specific partitions (stream entries are ordered per group). Redis supports unlimited consumer groups with independent offset tracking.
- Retry with exponential backoff: Redis does not provide automatic retry, but the `PEL` (Pending Entries List) lets us inspect and re-queue failed messages with backoff — straightforward in Python with `redis-py-stream` and a scheduler like RQ or Celery beat.

Operational overhead:
- Redis is already deployed, monitored, and backed up. No new infrastructure to provision, configure TLS, or manage persistence policies.
- No dedicated infrastructure role needed: our mid-level engineers can operate Redis Streams with existing skills (we already use Redis for sessions/rate limiting).
- Minimal migration work: Add a worker process and a few lines of config; no cluster setup, topic creation, or JVM tuning.

Budget: Redis is open-source (self-hosted) or available via AWS ElastiCache (low cost for our traffic), whereas Confluent Cloud at scale would exceed our modest budget.

## Consequences

**Positive**
- Faster delivery: Async notifications reduce request latency by 800 ms+.
- Reliability: Pending entries list + retry logic eliminates silent failures.
- No cascading failures: Notification failures don’t exhaust web server connection pools.
- Exactly-once billing events via simple deduplication with Redis SET.
- Existing Redis infrastructure means no new onboarding, monitoring, or backup systems.

**Negative**
- Limited horizontal scaling compared to Kafka clusters (but Redis Streams scales past our 10× requirement).
- No built-in compaction or log retention tiering (we store only brief notification metadata—bytes, not data).
- Consumer lag monitoring less mature than Kafka’s (but Prometheus/Grafana dashboards for Redis exist and are easy to configure).

**Follow-ups**
- Implement PEL monitor with alerting on stale pending entries.
- Document deduplication key format and TTL for notification IDs.
- Add rate limiting per consumer to avoid overwhelming webhook endpoints.
- Build admin view of pending messages for debugging.
- Evaluate [Kombu](https://github.com/celery/kombu) or [ celery-redis](https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/redis.html) integration if we later adopt Celery.

## Alternatives Considered

**Apache Kafka**
- Would work functionally and provide high throughput, but Kafka’s operational complexity far exceeds our team’s capacity: requires dedicated JVM resources, cluster management, topic partition tuning, and JVM heap/memory tuning. Kafka’s exactly-once semantics require transactional producers and consumer offset management—a much heavier implementation than Redis Streams’ simple acknowledgment + deduplication. Given no Kafka experience on the team and our ≤2-week migration constraint, Kafka introduces unacceptable risk and time-to-value delay.

**Kafka would have won if**: Our peak throughput were 1,000+ events/s, we had a dedicated infrastructure engineer, or we planned to share the same broker for other subsystems (logging, metrics) beyond notifications.

**PostgreSQL LISTEN/NOTIFY**
- Technically feasible (PostgreSQL is our current DB), but lacks consumer groups, offset tracking, and reliable retry semantics. We’d need to build a whole message queue on top of it—more complexity than Redis Streams with fewer guarantees.

**RabbitMQ / Amazon SQS**
- RabbitMQ adds another infrastructure component and learning curve; SQS would increase AWS spend and latency (no ephemeral, self-hosted option). Neither integrates with our current Redis workload as smoothly or efficiently.
