# ADR-001: Notification Subsystem Architecture

## Status
Proposed

## Context

Our SaaS project management platform (85k MAU, ~2M tasks/month, peak 500 req/s) currently handles notifications synchronously within the HTTP request cycle. This architecture has caused:

- Request timeouts (800ms average, 8s spikes during peak)
- Silent failures with no retry or dead-letter queue
- Cascading failures from slow webhook endpoints
- No delivery guarantees for billing-critical events

We need to decouple notifications, support retry with exponential backoff, guarantee at-least-once delivery for billing events (exactly-once where feasible), add real-time WebSocket push within 2 quarters, and handle 10x traffic growth without re-architecting.

**Constraints:**
- 6-person engineering team (3 senior, 3 mid-level), no dedicated infrastructure engineer
- Already running Redis in production (session storage, rate limiting)
- No Kafka experience on the team
- Must deliver value within 2 weeks of setup/migration
- Modest budget — cannot afford managed Confluent Cloud at scale
- Exactly-once semantics required for billing notifications

## Decision

**Choose Redis Streams** for the notification subsystem.

Redis Streams provides sufficient throughput for our scale (500 req/s peak, 5,000 req/s target), meets our ordering and delivery requirements, and aligns with our team expertise and operational constraints. The exactly-once requirement for billing notifications will be achieved through idempotent consumers using deduplication keys stored in PostgreSQL.

## Consequences

### Positive

- **Fast time-to-value**: Can implement within 1 week using existing Redis infrastructure, versus 2+ weeks for Kafka setup
- **Low operational complexity**: Single additional component (Redis) already managed by the team, versus Kafka's multi-broker + ZooKeeper architecture
- **Cost-effective**: No additional infrastructure costs; leverages existing Redis instance
- **Team expertise**: Builds on existing Redis knowledge; no learning curve for new technology
- **Sufficient throughput**: Redis Streams handles 100k+ messages/second on a single instance, well above our 5,000 req/s target
- **Consumer groups**: Native support with XREADGROUP enables parallel processing and load balancing
- **Message retention**: Configurable via XTRIM with MAXLEN, allowing 7-30 day retention for audit trails
- **Ordering guarantees**: Per-stream ordering ensures notifications are processed in sequence
- **Retry with backoff**: Consumer groups with pending entries list enable exponential backoff implementation

### Negative

- **No native exactly-once semantics**: Requires application-level idempotency (deduplication keys in PostgreSQL) for billing notifications
- **Limited message retention**: Unlike Kafka's log-based retention (years), Redis Streams memory-based retention requires careful capacity planning
- **Single point of risk**: Redis instance failure affects both caching and notifications (mitigated by Redis persistence and eventual replication)
- **Replay limitations**: Cannot replay messages from arbitrary offsets like Kafka; must use consumer group offsets
- **Scaling ceiling**: While sufficient for 10x growth, may require sharding or migration if growth exceeds 50x

## Alternatives Considered

### Apache Kafka (Rejected)

**Why rejected:**

1. **Operational complexity exceeds team capacity**: Kafka requires multi-broker cluster, ZooKeeper (or KRaft), monitoring, and ongoing maintenance. With no dedicated infrastructure engineer and no Kafka experience, this would consume significant engineering time better spent on product features.

2. **Time-to-value constraint**: Production-grade Kafka setup (including security, monitoring, disaster recovery) requires 2+ weeks, exceeding our 2-week value delivery window. Redis Streams can be operational in days.

3. **Budget constraints**: Self-hosted Kafka at production grade requires multiple EC2 instances, increasing infrastructure costs. Managed Confluent Cloud is prohibitively expensive at our scale.

4. **Over-engineering for current needs**: Kafka's strengths (millions of messages/second, years of retention, cross-datacenter replication) are unnecessary for our 500 req/s peak and 7-30 day retention requirements.

5. **Team expertise gap**: Learning Kafka would delay implementation and increase operational risk. Redis Streams builds on existing knowledge.

**Kafka advantages we're foregoing:**
- Native exactly-once semantics with transactions
- Superior message replay capabilities
- Better horizontal scaling beyond 50x growth
- More mature ecosystem and tooling

These advantages do not justify the operational overhead given our constraints and growth trajectory. If we exceed 50x growth, we can migrate to Kafka at that point with clearer business justification.