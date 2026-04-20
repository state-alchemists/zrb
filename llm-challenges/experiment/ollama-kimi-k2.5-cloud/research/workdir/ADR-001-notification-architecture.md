# ADR-001: Notification Architecture — Apache Kafka vs Redis Streams

**Date:** 2026-04-21  
**Author:** Engineering Team  
**Status:** Proposed

---

## Context

Our project management platform has outgrown synchronous notification processing. Current pain points include:

- **Request timeouts:** 800ms average latency, spiking to 8s during peak (500 req/s)
- **Silent failures:** No retry mechanism when email providers or webhooks fail
- **Cascading failures:** Slow external endpoints have caused connection pool exhaustion and outages
- **No delivery guarantees:** Billing-critical notifications (trial expiration, payment failures) lack exactly-once delivery guarantees

We must decouple notifications from the HTTP request cycle and implement:
- Asynchronous processing with retry and exponential backoff
- At-least-once delivery (exactly-once for billing events)
- A foundation for real-time WebSocket push notifications (Q3-Q4)
- Capacity to handle 10x traffic growth without re-architecting

**Operational Constraints:**
- Engineering team: 6 people (3 senior, 3 mid-level), no dedicated infrastructure engineer
- Redis is already operational (sessions, rate limiting)
- No team experience with Kafka
- Must deliver value within 2 weeks
- Modest budget rules out managed Confluent Cloud at scale

---

## Decision

**We will adopt Redis Streams for the notification subsystem.**

This decision prioritizes operational velocity and team capability over theoretical throughput advantages. Redis Streams meets our functional requirements while respecting our time and staff constraints.

### Justification

1. **Operational Familiarity:** Redis is already in production. The team understands persistence settings, memory management, and monitoring. Adding Streams uses existing infrastructure rather than introducing a new distributed system.

2. **Time-to-Value:** A functional prototype can be deployed within days. Kafka requires broker setup, ZooKeeper/KRaft configuration, topic partitioning strategy, and operational runbooks—easily exceeding our 2-week constraint.

3. **Sufficient Throughput for Current Scale:** Redis Streams handles ~100K messages/sec per node. At 500 req/s with 10 notifications per request, we need ~5K msg/s—two orders of magnitude below Redis limits. Even 10x growth (50K msg/s) remains comfortably within single-node capacity.

4. **Consumer Groups & Ordering:** `XGROUP CREATE` provides consumer group semantics with automatic partitioning and load balancing. Stream entries are ordered by ID (milliseconds time + sequence), providing per-stream ordering guarantees adequate for per-user notification sequencing.

5. **Exactly-Once for Billing (Application-Level):** While Redis lacks Kafka's native transactional producer/consumer, we will implement exactly-once via:
   - Deduplication table in PostgreSQL keyed by `(notification_id, recipient)`
   - `XACK` only after successful delivery confirmation
   - Transactional outbox pattern inserting notification events
   
   This adds application complexity but keeps infrastructure simple. Given our low volume of billing events (~1% of traffic), this tradeoff is acceptable.

6. **WebSocket Foundation:** Redis Streams' low latency (sub-millisecond) and Pub/Sub integration provide a clean path to real-time push notifications without adding another message broker.

---

## Consequences

### Positive

- **Immediate delivery:** Notifications processed asynchronously within days, not weeks
- **Reduced infrastructure sprawl:** No new servers, monitoring, or backup strategies to learn
- **Lower operational risk:** Familiar tooling reduces 3am pages and on-call burden
- **Memory-first performance:** Sub-millisecond enqueue/dequeue latency
- **Flexible retention:** `XTRIM` with `MINID` or approximate length keeps memory bounded

### Negative

- **Durability limitations:** Messages live in memory (or AOF/RDB snapshots). A crash between write and fsync can lose messages. Mitigation: `appendfsync everysec` and `aof-use-rdb-preamble yes`.

- **No native exactly-once:** Requires idempotent consumers via PostgreSQL deduplication. This is technical debt that Kafka would avoid.

- **Single-node bottleneck:** While 10x scale fits one Redis node, 100x growth would require clustering or migration. We accept this risk; by that scale, we may have dedicated infrastructure resources to re-evaluate.

- **Memory ceiling:** `maxmemory` with `allkeys-lru` eviction can drop messages if misconfigured. Mitigation: dedicated notification stream with `noeviction` policy and memory alerts.

- **Limited ecosystem:** Fewer client libraries and monitoring integrations compared to Kafka. We will build internal abstractions.

---

## Alternatives Considered

### Apache Kafka (Rejected)

**Why it was attractive:**
- Native exactly-once semantics via producer transactions and consumer idempotency
- Infinite retention (disk-based) and strong durability guarantees
- Industry-standard consumer groups with automatic rebalancing
- Proven at massive scale (millions of messages/sec)
- Stream processing ecosystem (Kafka Streams, ksqlDB)

**Why we rejected it:**

1. **Operational burden:** Kafka requires 3+ brokers for fault tolerance, ZooKeeper or KRaft metadata management, partition rebalancing tuning, and careful disk I/O monitoring. Our 6-person team lacks the bandwidth to operate this safely.

2. **Learning curve:** Zero team members have production Kafka experience. The 2-week constraint is incompatible with hiring/consulting ramp-up time.

3. **Cost:** Self-hosted Kafka requires EC2 instances or EBS volumes. Managed Confluent Cloud starts at ~$0.10/GB ingress—prohibitively expensive as we scale, and "modest budget" rules it out.

4. **Over-engineering:** 500 req/s with modest payload sizes is well within single-node Redis capacity. Kafka's distributed architecture solves problems we don't have yet.

**Decision:** Kafka is the technically superior platform for exactly-once semantics and long-term scalability, but the operational tax outweighs benefits for a 6-person team with no infrastructure specialist. We will reconsider if we exceed 100K msg/s or hire dedicated platform engineering.

---

## Implementation Notes

1. **Partitioning strategy:** One stream per notification type (`notifications:email`, `notifications:webhook`, `notifications:billing`) rather than consumer-group partitioning, to allow priority handling.

2. **Monitoring:** Alert on stream length, consumer group lag (`XPENDING`), and memory usage.

3. **Retry logic:** Use `XPENDING` to scan for stalled messages, increment retry count, re-enqueue to end of stream with exponential backoff delay.

4. **Dead-letter:** After 5 retries, `XADD` to `notifications:dlq` for manual inspection.

5. **Future reconsideration:** Re-evaluate at 50K msg/s sustained or if WebSocket volume requires partitioning across Redis Cluster.

---

*Approved by:* _________________  
*Date:* _________________
