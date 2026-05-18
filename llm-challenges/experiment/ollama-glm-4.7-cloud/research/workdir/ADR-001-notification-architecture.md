# ADR-001: Notification Subsystem Architecture

## Status
Proposed

## Context

Our SaaS project management platform (85k MAU, ~2M tasks/month, peak 500 req/s) currently handles notifications synchronously within the HTTP request cycle. This architecture has caused:

- Request timeouts (800ms average, 8s spikes during peak)
- Silent failures when external services (email providers, webhooks) are unavailable
- Cascading failures from slow webhook endpoints exhausting connection pools
- No delivery guarantees for billing-critical events

We need to decouple notifications from the request cycle, support retry with exponential backoff, guarantee at-least-once delivery for billing events (exactly-once where feasible), and handle 10x traffic growth without re-architecting.

**Constraints:**
- Engineering team: 6 people (3 senior, 3 mid-level), no dedicated infrastructure engineer
- Redis already in production (session storage, rate limiting)
- No Kafka experience on the team
- Must deliver value within 2 weeks of setup/migration
- Modest budget — cannot afford managed Confluent Cloud at full scale
- Exactly-once semantics required for billing notifications

## Decision

**Choose Redis Streams** for the notification subsystem.

Redis Streams provides sufficient throughput, ordering guarantees, and consumer group semantics for our scale while aligning with our team expertise, timeline, and budget constraints.

## Justification

### Scale Fit
- Current notification volume: ~200-300k/day (based on 2M tasks/month × 3-5 events/task)
- 10x growth target: ~2-3M notifications/day peak
- Redis Streams throughput: 100k+ messages/sec per instance — orders of magnitude above our needs
- Kafka's million-message-per-second capability is overkill for our use case

### Team and Timeline Alignment
- **Redis**: Already in production, team familiar with operations and monitoring
- **Kafka**: No existing expertise, steep learning curve for ZooKeeper/KRaft, broker management, partitioning strategies
- **Setup time**: Redis Streams can be production-ready in days; Kafka requires weeks for proper configuration, testing, and operational readiness
- **2-week constraint**: Kafka self-hosting is unrealistic; managed Confluent exceeds budget

### Technical Requirements Met
- **Throughput**: Redis Streams handles our current and projected 10x load comfortably
- **Ordering guarantees**: Per-stream ordering maintained (sufficient for notification ordering)
- **Message retention**: Configurable via `MAXLEN` — 7-14 days adequate for retry windows
- **Consumer groups**: Full support with `XREADGROUP`, offset management, and consumer rebalancing
- **Exactly-once semantics**: Achievable through idempotent processing and database-level deduplication (notification_id unique constraint)
- **Retry with backoff**: Application-level implementation using Redis sorted sets for scheduled retries

### Operational Complexity
- **Redis**: Single binary, no coordination service, familiar operational model
- **Kafka**: Requires ZooKeeper or KRaft, multiple brokers, partition management, replication configuration, monitoring of multiple components
- **Infrastructure overhead**: Redis leverages existing deployment; Kafka would require new infrastructure patterns and monitoring

### Future Extensibility
- **WebSocket push notifications**: Can leverage Redis Pub/Sub alongside Streams for real-time delivery
- **10x growth**: Redis Streams scales horizontally via sharding; can add Redis instances or migrate to Redis Cluster if needed
- **Migration path**: If requirements outgrow Redis Streams, can migrate to Kafka with minimal application changes (both support consumer group semantics)

## Consequences

### Positive
- Faster time-to-value: production-ready within 1-2 weeks vs 4-8 weeks for Kafka
- Lower operational overhead: leverages existing Redis expertise and infrastructure
- Reduced infrastructure costs: no additional services or managed Kafka subscriptions
- Team confidence: working with familiar technology reduces risk
- Adequate performance for current and projected scale
- Simple monitoring: extends existing Redis observability

### Negative
- **Message retention**: Limited to configured `MAXLEN` (typically days) vs Kafka's weeks/months — acceptable for notifications where replay beyond retry window is unnecessary
- **Exactly-once semantics**: Requires application-level idempotency and deduplication vs Kafka's transactional support — adds development complexity but manageable
- **Horizontal scaling**: Requires manual sharding or Redis Cluster for extreme scale vs Kafka's built-in partitioning — not a concern for 10x growth target
- **Ecosystem maturity**: Fewer tools and integrations compared to Kafka's mature ecosystem — sufficient for our use case
- **Long-term flexibility**: If requirements evolve to event sourcing or complex stream processing, migration to Kafka may be necessary — acceptable trade-off for current constraints

## Alternatives Considered

### Apache Kafka

**Rejected because:**

1. **Operational complexity exceeds team capacity**: No dedicated infrastructure engineer; Kafka requires expertise in ZooKeeper/KRaft, broker management, partitioning, replication, and monitoring. Learning curve would delay delivery beyond 2-week constraint.

2. **Budget constraints**: Self-hosted Kafka requires multiple instances (minimum 3 brokers for production), increasing infrastructure costs. Managed Confluent Cloud at full scale exceeds modest budget.

3. **Over-engineering for current scale**: Kafka's million-messages-per-second throughput and enterprise features (exactly-once transactions, compacted topics) are unnecessary for ~300k notifications/day. We would pay complexity we don't need.

4. **Timeline risk**: Even with managed Kafka, team would need to learn Kafka concepts (producers, consumers, consumer groups, offsets, partitions, serialization), configure schemas, and establish operational practices. High risk of missing 2-week delivery target.

5. **No existing expertise**: Team has no Kafka experience. Redis is already in production and well-understood. Choosing Kafka introduces unnecessary risk for a critical subsystem.

Kafka would be the right choice if we had: (a) dedicated infrastructure engineering, (b) requirements for event sourcing or complex stream processing, (c) message volumes in the millions per hour, or (d) budget for managed services. None of these apply today.