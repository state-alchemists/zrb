# ADR-001: Notification Subsystem Architecture

## Status

Proposed

## Context

Our SaaS project management platform handles 85,000 monthly active users and generates ~2M tasks per month. Currently, notifications (emails and webhooks) are processed synchronously within HTTP request handlers, causing:

- **Request timeouts**: Average latency of 800ms, spiking to 8s during peak hours (~500 req/s)
- **Silent failures**: No retry mechanism when downstream providers fail
- **Cascading failures**: Slow webhook endpoints have caused connection pool exhaustion and outages
- **No delivery guarantees**: Billing-critical notifications lack exactly-once semantics, risking revenue loss and customer trust

We must decouple notifications into an asynchronous, reliable messaging system supporting retry, exponential backoff, and exactly-once delivery for billing events. Additionally, we must support real-time WebSocket push notifications within 2 quarters and handle 10x traffic growth without re-architecting.

**Key Constraints:**
- Engineering team: 6 people (3 senior, 3 mid-level), no dedicated infrastructure engineer
- Already running Redis for sessions and rate limiting
- No Kafka experience on the team
- Must deliver value within 2 weeks of setup/migration
- Modest budget — cannot afford managed Confluent Cloud at full scale
- Must guarantee exactly-once semantics for billing notifications

## Decision

**We will adopt Apache Kafka as the notification subsystem message broker.**

Given the requirement for exactly-once delivery guarantees for billing-critical events and the mandate to handle 10x growth without re-architecting, Kafka is the only option that satisfies our non-negotiable constraints. We accept the operational complexity and will invest the upfront learning time to avoid a costly migration later.

## Consequences

### Positive Consequences

- **Exactly-once semantics**: Kafka provides idempotent producers and transactions, enabling true exactly-once processing for billing notifications without application-layer deduplication complexity
- **10x growth headroom**: Kafka's partition-based architecture scales horizontally to millions of messages per second; we can add brokers and partitions as load increases
- **Strong ordering guarantees**: Per-partition ordering ensures webhook and email notifications arrive in sequence for a given user or task
- **Durable message retention**: Disk-based retention with configurable policies (days to weeks) provides a buffer against consumer downtime and supports replay for debugging
- **Mature consumer groups**: Automatic rebalancing, offset management, and consumer failures handled gracefully without message loss
- **Ecosystem leverage**: Native integrations for future WebSocket support (e.g., Kafka WebSocket proxy or Kafka Connect), plus mature Python clients

### Negative Consequences

- **Operational complexity**: Kafka requires managing brokers, ZooKeeper (or KRaft mode), replication, partition leadership, and failure recovery. Our 6-person team without infrastructure expertise must learn and own this operational burden
- **Setup timeline risk**: Initial deployment, security hardening, and operational tooling will take 3–4 weeks, exceeding the 2-week target by 1–2 weeks
- **Learning curve**: The team must grasp concepts like partitions, replication factors, in-sync replicas, and offset commit strategies before production use
- **Memory and resource footprint**: Kafka is JVM-based with higher memory requirements than Redis; each broker requires significant heap allocation
- **No immediate shared knowledge**: Unlike Redis, no team member has Kafka experience, meaning early mistakes in configuration (e.g., replication factor = 1, unclean leader election) could cause outages

## Alternatives Considered

### Redis Streams — Rejected

Redis Streams was initially attractive because Redis is already in production for sessions and rate limiting, offering operational familiarity and a sub-1-week setup timeline. However, it was rejected for the following reasons:

1. **No native exactly-once semantics**: Redis Streams provides at-least-once delivery only. Achieving exactly-once for billing notifications would require building complex application-level deduplication logic (idempotency keys, consumer-side state management), introducing significant risk from our past track record of silent failures

2. **Memory-bound scaling**: With 2M tasks/month and 10x growth, notification volume could reach 20M+ messages. Redis is memory-first; even with capped streams (`MAXLEN`), large backlogs during consumer downtime risk eviction of session data or OOM kills, taking down unrelated features

3. **Weaker consumer group guarantees**: Redis Streams consumer groups lack Kafka's automatic rebalancing and offset management sophistication. Partitioning logic is manual, and consumer failures require careful handling to avoid message loss or duplicates

4. **Retention limitations**: While Kafka retains on disk affordably, Redis persistence is either memory-limited or relies on AOF/RDB with performance trade-offs. Long-term retention for audit trails or replay is impractical

We would have chosen Redis Streams if our requirements were limited to at-least-once delivery, if team bandwidth for operations were severely constrained, or if the growth trajectory were modest (<3x). Given exactly-once requirements for billing and the mandate to support 10x growth without re-architecting, Redis Streams does not satisfy our constraints at the acceptable risk level.

---

*Decision Date: 2026-05-17*
*Decision Makers: Engineering Team Lead, Senior Engineers*
