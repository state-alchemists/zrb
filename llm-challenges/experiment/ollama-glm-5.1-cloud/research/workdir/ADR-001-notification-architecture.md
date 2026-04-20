# ADR-001: Notification Subsystem Message Broker

**Status**: Proposed

## Context

Our SaaS project management platform (85,000 MAU, ~2M tasks/month, peak ~500 req/s) handles email and webhook notifications synchronously inside the HTTP request cycle. This causes request timeouts (800ms avg, 8s spikes), silent dropped notifications on provider failures, cascading connection-pool exhaustion from slow webhooks, and zero delivery guarantees for billing-critical events.

We must decouple notification processing from request handling, add retry with exponential backoff, guarantee at-least-once delivery (exactly-once for billing where feasible), and support future WebSocket push — all while handling 10x traffic growth without re-architecting.

Key constraints:

- **6-person engineering team** (3 senior, 3 mid-level), no dedicated infrastructure engineer
- **Redis already in production** for sessions and rate limiting — team has operational fluency
- **Zero Kafka experience** on the team
- **2-week ceiling** on setup/migration before delivering visible value
- **Modest budget** — managed Confluent Cloud at scale is not affordable today
- **Exactly-once semantics** required for billing notifications ("trial expired", "payment failed")

Throughput requirements are modest by streaming standards: at 500 req/s peak and ~2M tasks/month, even assuming 3 notifications per task, peak production is ~1,500 messages/s. The 10x scaling target puts this at ~15,000 messages/s — well within the envelope of both candidates.

## Decision

**We choose Redis Streams.**

Redis Streams provides consumer groups (XREADGROUP, XACK, XPENDING), persistent append-only logs with configurable retention, and at-least-once delivery — all on infrastructure we already run and understand. The two-week constraint, absence of Kafka expertise, and modest budget make Kafka operationally untenable for this team at this stage.

The exactly-once requirement for billing notifications will be satisfied through **application-level idempotency**: each billing notification carries an idempotency key (derived from `event_type + entity_id + attempt_id`), and the consumer deduplicates against a PostgreSQL table before executing the side effect. This is necessary regardless of broker choice — Kafka's exactly-once semantics (transactional producer/consumer via `enable.idempotence=true` and transactional APIs) only guarantee no duplicate within Kafka itself. Once the consumer performs an external side effect (SMTP call, HTTP POST to a webhook), end-to-end exactly-once requires the same application-level deduplication. Betting on Kafka for "free" exactly-once would be a category error for this use case.

## Consequences

### Pros

- **Immediate operability**: Redis is already deployed, monitored, and understood by the team. No new infrastructure to provision, harden, or learn to operate. We can write the first producer in day 1 and the first consumer in day 2.
- **Fits the 2-week window**: A working async notification pipeline (produce → stream → consume → retry → DLQ) is achievable within sprint scope using redis-py's stream commands and our existing Flask workers.
- **Consumer groups are sufficient**: Redis Stream consumer groups (XREADGROUP, XACK, XCLAIM for dead consumers, XPENDING for monitoring) cover our needs: fan-out to multiple workers, claim-orphaned messages, and inspect unacknowledged messages for alerting.
- **Cost**: No new infrastructure spend. Our existing Redis instance (or a separate Redis instance for isolation if needed) costs a fraction of even a small Confluent Cloud cluster (~$0.30/hour for a basic CCloud Standard cluster vs. near-zero marginal cost on our existing ElastiCache).
- **WebSocket compatibility**: Redis Pub/Sub (for real-time fan-out) combined with Streams (for reliable delivery) is a proven pattern for WebSocket push. The same Redis instance can serve both, avoiding a second messaging substrate.
- **Adequate throughput**: Single-node Redis handles 100K+ ops/s. Our 1,500 msg/s peak (15,000 at 10x) is negligible. Even with persistence enabled (AOF every-write), we remain comfortably within headroom.

### Cons

- **Message retention is finite**: Redis Streams use `MAXLEN` or time-based trimming; they are not an infinite durable log. We mitigate by persisting every notification event to PostgreSQL before publishing (outbox pattern), so the stream is a transient delivery mechanism, not the source of truth. Replay comes from the DB, not the stream.
- **No native exactly-once**: Redis provides at-least-once. We must implement idempotency in the consumer. This is application-level work (a `processed_notifications` table with a unique constraint on the idempotency key) — roughly a half-day of implementation and testing.
- **Scaling ceiling**: Redis Streams scale vertically (single primary) and through clustering (partitioned keyspace). At extreme scale (millions of msgs/s, multi-TB retention), Kafka's horizontal partition model is superior. If we hit that ceiling in 2+ years, we can migrate then — the outbox pattern in PostgreSQL makes this a consumer-side change, not an architectural rewrite.
- **Operational fragility under memory pressure**: If Redis hits `maxmemory`, stream eviction policy can silently drop messages. We mitigate by running a dedicated Redis instance for streams (isolated from session cache), setting `maxmemory-policy noeviction`, and alerting on memory utilization at 70%.
- **Consumer group limitations**: Redis consumer groups lack the rebalancing sophistication of Kafka (no cooperative sticky assignment, no rack-awareness). For 6–12 notification workers behind a load balancer, round-robin XREADGROUP is entirely adequate. This becomes a concern only at dozens of consumers with heterogeneous processing speeds — far from our reality.

## Alternatives Considered

### Apache Kafka

Kafka is the industry-standard distributed event streaming platform with exceptional throughput (millions of msgs/s across a cluster), durable log-based retention (days to years), mature consumer groups with partition-based parallelism, and transactional exactly-once semantics within the Kafka ecosystem.

**Why we reject Kafka for this decision:**

1. **Operational complexity is disproportionate.** A production Kafka deployment requires broker configuration, ZooKeeper or KRaft quorum management, topic/partition planning, ISR monitoring, and a runbook for broker failures. We have no dedicated infra engineer and zero Kafka experience. The team would spend the entire 2-week window just standing up and validating the cluster — leaving no time for the actual notification pipeline migration.

2. **Cost at our scale is unjustified.** Self-hosted Kafka on AWS requires minimum 3 broker nodes (m5.large or equivalent) for a resilient cluster, plus ZooKeeper nodes if not on KRaft — roughly $300–500/month before EBS and data transfer. Managed Confluent Cloud Standard starts at ~$0.30/hour per CKU ($220/month minimum) and scales with throughput. Our current need is ~1,500 msg/s peak — we would be paying enterprise-grade infrastructure for a problem that fits on a single Redis instance.

3. **Exactly-once is a mirage for external side effects.** Kafka's transactional API (`.beginTransaction`, `send`, `commitTransaction`) guarantees that consumed offsets and produced messages are committed atomically *within Kafka*. Once our consumer calls an external SMTP API or fires an HTTP webhook, there is no Kafka transaction that can unwind that side effect on crash. The consumer must be idempotent regardless. Kafka's exactly-once reduces duplicate *production* risk but does not eliminate the need for the same idempotency key + dedup table we need with Redis Streams. The complexity premium buys us no real improvement in end-to-end delivery guarantees.

4. **Team velocity.** Every hour spent learning Kafka admin, client libraries (confluent-kafka-python, schema registry, Avro serialization), and debugging consumer lag is an hour not spent fixing the production incident that motivated this ADR. Redis Streams with the redis-py library our team already uses has near-zero learning curve.

5. **If we grow into Kafka, the outbox pattern makes migration clean.** By writing every notification to PostgreSQL before publishing to the stream, we retain a complete, queryable event log. A future migration to Kafka means swapping the stream producer to a Kafka producer and pointing consumers at the Kafka topic — no re-architecture of the notification logic itself. We are not locking ourselves out; we are deferring the complexity until it is justified by scale.

---

*Revisit this decision when peak notification throughput exceeds 50,000 msg/s, or when we need multi-service event sourcing with long-lived replay windows beyond what the PostgreSQL outbox table can support.*