# ADR-001: Notification Subsystem Architecture Decision

**Status:** Proposed  
**Date:** 2026-04-24  
**Author:** Architecture Team

---

## Context

The current notification subsystem is synchronous and embedded in the HTTP request cycle, causing:

- ** request latency:** 800ms average, 8s spikes; blocking billing-critical events
- **reliability issues:** silent failures, no retry, dead-letter gaps
- **cascading failure risk:** webhook latency → connection pool exhaustion → site instability
- **missing delivery guarantees:** no at-least-once or exactly-once semantics

**Requirements:**
- Async decoupling; < 2-week migration
- At-least-once delivery for all notifications; exactly-once for billing events
- Exponential backoff retry
- Real-time WebSocket support within 2 quarters
- 10x traffic growth buffer (peak throughput target: ~5,000 events/s)
- Must use existing infrastructure (Redis is already in production)
- Team capacity: 6 engineers, no Kafka expertise

---

## Decision

**Choose Redis Streams** as the message queue backing the notification subsystem.

### Justification

1. **Operational feasibility for small team**  
   Redis Streams requires no cluster provisioning or separate infrastructure. It integrates into our existing Redis instance (used for sessions/rate limiting). Setup is one configuration change; migration can be done in < 2 weeks by current staff. Kafka would require learning, cluster provisioning, monitoring, and backup—exceeding our 2-week runway and team skill constraints.

2. **Throughput sufficiency**  
   Redis Streams can handle > 100,000 messages/s on a single instance (benchmarked). Our peak requirement: ~5,000 events/s. Kafka’s advantage (millions of messages/s) is overkill for our scale.

3. **Exactly-once semantics via idempotent consumers**  
   Redis Streams supports `XREADGROUP` with `GROUP`/`CONSUMER` and explicit ACKs. Combined with idempotent notification IDs (UUID + deduplication cache), we achieve exactly-once delivery for billing events by deduplicating retries using a Redis SET with TTL.

4. **Simpler retry logic**  
   Failed messages can be requeued with `XPENDING`/`XRANGE` introspection. A Python worker can implement exponential backoff by reinserting with a delayed timestamp or using a sorted set score-based queue (delayed job pattern). Kafka’s offset management is more complex to orchestrate manually without Confluent’s managed tooling.

5. **Real-time WebSocket support**  
   Redis Pub/Sub (already used alongside Streams for other features) integrates natively with WebSocket presence detection and pub-sub broadcast. Redis Streams can feed Pub/Sub channels, enabling “notification ready” events for WebSocket push without extra infrastructure.

---

## Consequences

### Pros
- ** Rapid iteration:** New notification types can be added by adding a new consumer group; no schema changes.
- ** Monitoring simplicity:** Use existing Redis monitoring (e.g., `redis-cli --stat`, Prometheus exporter for Redis).
- ** Cost:** No additional managed service; uses existing Redis infrastructure (capacity headroom available).
- ** Debuggability:** `XRANGE`, `XINFO`, `XPENDING` commands provide out-of-the-box CLI and programmatic visibility.
- ** Lower cognitive overhead:** 3–5 days for team onboarding; no Java/Scala cluster operations knowledge required.

### Cons
- ** Limited message retention** vs. Kafka: Redis retention is memory-bound (configurable maxmemory policy); Kafka sustains months of retention out-of-box. For our volume (~2M/month), 7–14 days retention is sufficient; billing events are replayable from the DB if needed.
- ** No native replay from offset zero:** To replay, we must re-read from PostgreSQL change-stream or reenqueue historical events; Kafka’s `--from-beginning` is more ergonomic. However, our requirement is forward-looking, not historical reprocessing.
- ** Single point of failure risk:** Mitigated by Redis high-availability (we already run a primary/replica); Kafka also requires HA setup (ZooKeeper/KRaft) and still has failure modes.

---

## Alternatives Considered

### Apache Kafka

**Rejected because:**

1. **Operations burden:** Team has zero Kafka experience. Setting up a durable, HA cluster (3 brokers, replication factor 3, proper compaction/tuning) requires 2–3 weeks initial setup plus ongoing infrastructure maintenance. Our constraint is 2 weeks to deliver value.

2. **Over-engineering for scale:** Kafka excels at high-cardinality, high-volume ingress (e.g., clickstream, logs). Our notification volume (~2M/month) is 5–10 orders of magnitude below Kafka’s design sweet spot.

3. **Cost:** Managed Confluent Cloud at scale is expensive; self-hosted Kafka on AWS EC2 still requires DevOps effort. Our budget cannot absorb the infrastructure engineer time.

4. **Complex exactly-once semantics:** Kafka’s EOS requires careful coordination between producer (idempotent + transactional ID) and consumer (offset commit control). Our team has no experience tuning this, increasing production incident risk.

5. **WebSocket integration overhead:** Pushing Kafka messages to WebSocket clients requires an additional service (e.g., Kafka → Redis Pub/Sub proxy), versus Redis’s native two-way integration.

**Trade-off analysis:** Kafka’s superior throughput, retention, and mature ecosystem are irrelevant for our current constraints. The engineering runway saved by choosing Redis Streams (2 weeks vs. 6+ weeks) enables faster delivery of billing safety guarantees and real-time features.

---

## Implementation Next Steps

1. Add Redis Streams producer in Flask (POST/PUT task endpoint) to enqueue events with `XADD notifications.stream * event_type <type> payload <json>`
2. Build Python consumer worker with `XREADGROUP` and `GROUPCREATE` for “ email”, “webhook”, “billing” consumer groups
3. Implement idempotency cache using Redis SET + TTL for billing events (key: `notify:billing:{event_id}`, TTL 24h)
4. Deploy monitoring: alert on `pending_messages > 1000` in XPENDING for > 5 minutes
5. After 1 month, add Redis Pub/Sub side-channel for real-time WebSocket push events

---

## Links

- [Redis Streams Documentation](https://redis.io/docs/latest/develop/data-types/streams/)
- [Redis Streams vs Kafka: When to Use Each](https://redis.com/blog/redis-streams-vs-apache-kafka/)
