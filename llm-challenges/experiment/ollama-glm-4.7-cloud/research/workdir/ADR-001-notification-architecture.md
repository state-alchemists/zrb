# ADR-001: Notification Subsystem Architecture

## Status
Proposed

## Context

Our SaaS project management platform (85,000 MAU, 500 req/s peak) currently handles notifications synchronously within the HTTP request cycle. This has caused:

- Request timeouts (800ms average, 8s spikes during peak)
- Silent failures when external services are down
- Cascading failures from slow webhook endpoints
- No delivery guarantees for billing-critical events

We need to decouple notifications, support retry with exponential backoff, guarantee at-least-once delivery for billing events (exactly-once where feasible), and handle 10x traffic growth (5,000 req/s target) within 2 quarters.

**Constraints:**
- 6-person engineering team (3 senior, 3 mid-level), no dedicated infrastructure engineer
- Redis already in production for session storage and rate limiting
- No Kafka experience on the team
- Must deliver value within 2 weeks of setup/migration
- Modest budget — cannot afford managed Confluent Cloud at scale
- Exactly-once semantics required for billing notifications

## Decision

**Choose Redis Streams** for the notification subsystem.

Redis Streams provides sufficient throughput for our scale (5,000 req/s target), meets our ordering and delivery requirements, and can be implemented within our constraints. The existing Redis infrastructure and team familiarity enable rapid delivery (<1 week setup) while keeping operational complexity low.

## Consequences

### Positive

- **Rapid time-to-value**: Can be implemented in <1 week using existing Redis infrastructure, meeting the 2-week constraint
- **Low operational complexity**: Single binary already in production, no additional infrastructure to manage
- **Sufficient throughput**: Handles hundreds of thousands of messages per second, well above our 5,000 req/s target
- **Ordering guarantees**: Per-stream ordering ensures notifications are processed in sequence
- **Consumer groups**: XREADGROUP supports multiple workers with automatic offset management
- **Message retention**: Configurable via XADD MAXLEN, allowing appropriate retention windows
- **Cost-effective**: No additional infrastructure costs; leverages existing Redis investment
- **Team familiarity**: Already using Redis for sessions and rate limiting, reducing learning curve
- **Built-in retry**: Consumer group offset management enables at-least-once delivery with retry logic

### Negative

- **No native exactly-once semantics**: Requires idempotent consumer implementation for billing notifications (e.g., deduplication via message ID in PostgreSQL)
- **Limited message retention**: Unlike Kafka's log compaction, Redis Streams require explicit truncation; long retention requires more memory
- **Single point of failure**: Redis Streams without clustering introduces a single point of failure (mitigated by Redis persistence and existing backup strategy)
- **Scaling complexity**: Horizontal scaling requires Redis Cluster, which adds operational complexity at very high scale
- **Fewer ecosystem tools**: Less mature monitoring and tooling compared to Kafka's ecosystem

## Alternatives Considered

### Apache Kafka (Rejected)

Kafka was evaluated but rejected for the following reasons:

- **Operational complexity**: Requires ZooKeeper/KRaft, broker management, partition planning, and replication configuration. With no dedicated infrastructure engineer and no Kafka experience, this would exceed our operational capacity.
- **Setup time**: Production-grade Kafka setup (including monitoring, security, and failover testing) would exceed the 2-week constraint. Even a minimal viable setup would require significant learning and configuration.
- **Cost**: Managed Confluent Cloud is unaffordable at our scale. Self-hosted Kafka requires additional infrastructure (multiple brokers, ZooKeeper/KRaft nodes) and ongoing maintenance overhead.
- **Over-engineering for current scale**: Kafka's throughput (millions of messages per second) far exceeds our needs (5,000 req/s target). The complexity-to-value ratio is unfavorable.
- **Team experience gap**: No Kafka experience on the team would require significant training and risk during initial deployment.

While Kafka offers superior exactly-once semantics, longer retention, and better horizontal scaling, these benefits do not justify the operational overhead and setup time given our constraints. Redis Streams meets all functional requirements with significantly lower complexity and faster delivery.