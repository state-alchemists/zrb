# ADR-001: Notification Subsystem Architecture

## Status
Proposed

## Context

Our SaaS project management platform (85k MAU, ~2M tasks/month, peak 500 req/s) currently handles notifications synchronously within HTTP requests. This architecture has caused:

- **Request timeouts**: 800ms average latency, spiking to 8s during peak hours
- **Silent failures**: No retry or dead-letter queue when email/webhook providers are down
- **Cascading failures**: Two incidents where slow webhook endpoints exhausted connection pools
- **No delivery guarantees**: Billing-critical notifications lack exactly-once semantics

We need to decouple notifications, support retry with exponential backoff, guarantee at-least-once delivery for billing events, add real-time WebSocket push within 2 quarters, and handle 10x traffic growth.

**Constraints:**
- 6-person engineering team (3 senior, 3 mid-level), no dedicated infrastructure engineer
- Redis already running in production (session storage, rate limiting)
- No Kafka experience on the team
- Must deliver value within 2 weeks of setup/migration
- Modest budget — cannot afford managed Confluent Cloud at full scale
- Exactly-once semantics required for billing notifications

## Decision

**Choose Redis Streams** for the notification subsystem.

Redis Streams provides sufficient throughput, ordering guarantees, and consumer group semantics to meet our requirements while aligning with our team size, timeline, and budget constraints. The existing Redis infrastructure reduces operational complexity and allows us to deliver value within the 2-week window.

### Justification

**Technical Fit:**
- **Throughput**: Redis Streams handles 100k+ messages/second on modest hardware, exceeding our current 500 req/s peak and 10x growth target (5,000 req/s)
- **Ordering guarantees**: Per-stream ordering ensures notifications are processed sequentially per task/user
- **Message retention**: Configurable via `MAXLEN` option; we can retain messages for 7-14 days for replay/debugging
- **Consumer groups**: Full support with `XREADGROUP`, enabling multiple worker processes with automatic offset management
- **Exactly-once semantics**: Redis provides at-least-once delivery; we achieve exactly-once for billing events via idempotent consumer logic (deduplication by notification ID in PostgreSQL)

**Operational Fit:**
- **Team expertise**: Already using Redis; no learning curve for basic operations
- **Setup time**: <1 week to implement (enable streams, add worker processes, integrate with existing Flask app)
- **Infrastructure**: Single additional Redis instance or sharding of existing instance; no new services to monitor
- **Cost**: Minimal incremental cost (already paying for Redis); no managed service fees

**Scalability Path:**
- Current single Redis instance handles 10x growth
- Future scaling via Redis Cluster or sharding by tenant/notification type
- Can migrate to Kafka if requirements exceed Redis capabilities (e.g., >100M messages/day, multi-region replication)

## Consequences

### Positive

- **Fast time-to-value**: Deliver async notifications within 2 weeks, meeting immediate pain points
- **Low operational overhead**: Single service to monitor, leverages existing Redis expertise
- **Cost-effective**: No additional infrastructure costs; scales with existing Redis deployment
- **Sufficient for requirements**: Handles current and projected load with headroom
- **Future flexibility**: Can migrate to Kafka if needed without changing application logic (both support consumer groups)

### Negative

- **Limited message retention**: Redis Streams memory-based; long retention requires more RAM or periodic archiving
- **No built-in dead-letter queue**: Must implement DLQ pattern in application code
- **Exactly-once requires application logic**: Must implement idempotent consumers for billing events (PostgreSQL deduplication table)
- **Scaling complexity**: Redis Cluster adds operational complexity if we exceed single-instance capacity
- **Fewer ecosystem tools**: Less mature monitoring and tooling compared to Kafka ecosystem

## Alternatives Considered

### Apache Kafka

**Rejected because:**

1. **Operational complexity exceeds team capacity**: Kafka requires ZooKeeper/KRaft, multiple brokers, partition management, replication configuration, and specialized monitoring. With no dedicated infrastructure engineer and no Kafka experience, this would require significant learning and operational overhead.

2. **Timeline constraint**: Production-ready Kafka deployment (including HA setup, monitoring, disaster recovery) would exceed the 2-week window. Even managed services (MSK, Confluent Cloud) require configuration and integration time.

3. **Budget constraint**: Self-hosted Kafka requires 3+ brokers for HA (additional EC2 costs). Managed Confluent Cloud at our scale would cost $500-1,000/month, which exceeds our modest budget.

4. **Over-engineering for current needs**: Kafka's strengths (millions of messages/second, multi-region replication, complex event sourcing) are not required for our use case. Our peak load (500 req/s, 5,000 req/s target) is well within Redis Streams capabilities.

5. **Team expertise gap**: No Kafka experience means slower debugging, longer incident response, and higher risk of misconfiguration.

**Kafka would be appropriate if:**
- We projected >100M messages/day
- Required multi-region active-active replication
- Needed complex event sourcing patterns
- Had a dedicated infrastructure engineer
- Budget allowed for managed services

### Other Alternatives Briefly Considered

- **RabbitMQ**: Rejected due to operational complexity similar to Kafka, with less throughput and no native streaming semantics
- **AWS SQS/SNS**: Rejected due to vendor lock-in and cost at scale; also lacks ordering guarantees without FIFO queues
- **Database polling**: Rejected due to inefficiency and lack of real-time guarantees

## Implementation Plan

1. **Week 1**: Enable Redis Streams, implement producer in Flask app, create consumer worker processes
2. **Week 2**: Add retry logic with exponential backoff, implement DLQ pattern, add idempotent consumer for billing events
3. **Week 3-4**: Monitor performance, tune retention policies, add metrics and alerting
4. **Quarter 2**: Add WebSocket push notifications using Redis Pub/Sub alongside Streams

## Success Criteria

- Notification processing latency <100ms (vs. current 800ms-8s)
- Zero silent failures (all failed notifications in DLQ)
- Exactly-once delivery for billing events (verified via deduplication logs)
- Handle 5,000 req/s peak without degradation
- Team can operate system without dedicated infrastructure engineer