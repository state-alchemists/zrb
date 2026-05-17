# ADR-001: Notification Subsystem Architecture

## Status
Proposed

## Context

Our SaaS project management platform (85k MAU, 2M tasks/month, 500 req/s peak) has a critical bottleneck in the notification subsystem. Notifications are currently handled synchronously within HTTP requests, causing:

- **Request timeouts**: 800ms average latency, spiking to 8s during peak hours
- **Silent failures**: No retry or dead-letter queue when email/webhook providers fail
- **Cascading failures**: Slow webhook endpoints have caused connection pool exhaustion, taking down unrelated features
- **No delivery guarantees**: Billing-critical notifications lack exactly-once semantics

We need to decouple notifications from the HTTP request cycle, support retry with exponential backoff, guarantee at-least-once delivery for billing events (exactly-once where feasible), and handle 10x traffic growth without re-architecting.

**Constraints:**
- Engineering team: 6 people (3 senior, 3 mid-level), no dedicated infrastructure engineer
- Already running Redis in production (session storage, rate limiting)
- No Kafka experience on the team
- Must deliver value within 2 weeks of setup/migration
- Modest budget — cannot afford managed Confluent Cloud at scale
- Must maintain exactly-once semantics for billing notifications

## Decision

**Choose Redis Streams** as the message streaming backbone for the notification subsystem.

Redis Streams provides sufficient throughput, ordering guarantees, and consumer group semantics to meet our requirements while aligning with our team expertise, time constraints, and budget. The exactly-once requirement for billing notifications will be achieved through idempotent consumer logic (deduplication by notification ID) rather than relying on stream-level exactly-once semantics.

## Consequences

### Positive

- **Fast time-to-value**: Leverage existing Redis infrastructure; setup and migration achievable within 2-week constraint
- **Low operational complexity**: Single additional Redis instance (or leverage existing with memory tuning); no ZooKeeper/KRaft, broker management, or partition rebalancing complexity
- **Team expertise**: Already familiar with Redis operations; minimal learning curve
- **Cost-effective**: No additional infrastructure costs; scales vertically within existing Redis deployment
- **Sufficient throughput**: Redis Streams handles 100k+ ops/sec per instance; our peak 500 req/s (5k after 10x growth) is well within capacity
- **Built-in consumer groups**: XREADGROUP enables parallel processing with automatic offset tracking
- **Configurable retention**: Time-based or size-based retention policies prevent unbounded memory growth
- **Per-stream ordering**: Guarantees ordering within each notification type (e.g., billing events processed sequentially)

### Negative

- **No stream-level exactly-once semantics**: Must implement idempotency at the consumer layer (deduplication by notification_id in PostgreSQL)
- **Vertical scaling limits**: If growth exceeds single Redis instance capacity, will require sharding or migration to Kafka
- **Limited replay capabilities**: Once messages are trimmed (per retention policy), they cannot be reprocessed; Kafka's log compaction provides stronger replay guarantees
- **Fewer ecosystem tools**: Less mature monitoring, observability, and tooling compared to Kafka's ecosystem
- **Cross-datacenter replication**: More complex than Kafka's built-in replication; may require additional tooling for multi-region deployment

## Alternatives Considered

### Apache Kafka

**Rejected for the following reasons:**

1. **Operational complexity exceeds team capacity**: Kafka requires managing ZooKeeper/KRaft, broker clusters, partition assignment, replication factors, and controller election. With no dedicated infrastructure engineer and no Kafka experience, this would significantly slow development and increase operational risk.

2. **Time constraint violation**: Setting up a production-grade Kafka cluster (even self-managed on AWS) typically exceeds 2 weeks when factoring in planning, deployment, testing, and team training. This conflicts with the requirement to deliver value quickly.

3. **Budget constraints**: Self-managed Kafka requires multiple EC2 instances (minimum 3 brokers for HA) and EBS volumes. Managed Confluent Cloud is cost-prohibitive at our scale. Redis Streams leverages existing infrastructure with minimal additional cost.

4. **Over-engineering for current scale**: Our peak 500 req/s (5k after 10x growth) is orders of magnitude below Kafka's design point. Kafka's strengths (millions of events/sec, log compaction, exactly-once transactions) are unnecessary for our use case and add complexity without proportional benefit.

5. **Team expertise mismatch**: Investing in Kafka expertise would divert focus from product development. Redis Streams builds on existing skills, allowing the team to deliver faster.

**Kafka would be appropriate if:**
- We projected 100x+ growth (50k+ req/s)
- We required log compaction for event sourcing
- We had dedicated infrastructure engineering capacity
- We needed multi-region active-active replication
- Budget allowed for managed Kafka services

Given our constraints, Redis Streams is the pragmatic choice that balances technical requirements with team capacity and time-to-market.