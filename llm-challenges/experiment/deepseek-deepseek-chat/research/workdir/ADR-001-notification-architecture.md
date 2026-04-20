# ADR-001: Notification Subsystem Architecture

## Status
Accepted

## Context
Our SaaS project management platform currently handles notifications synchronously within the HTTP request cycle, causing:
1. Request timeouts (800ms average latency, 8s spikes)
2. Silent failures when external services are down
3. Cascading failures from slow webhook endpoints
4. No delivery guarantees for billing-critical notifications

We need to decouple notifications from request processing while supporting:
- 500 req/s peak (with 10x growth capacity)
- Retry with exponential backoff
- At-least-once delivery for all notifications, exactly-once for billing events
- Real-time WebSocket push notifications within 2 quarters
- Minimal operational overhead for a 6-person engineering team with no dedicated infrastructure engineer

## Decision
We will implement the notification subsystem using **Redis Streams**.

## Justification
Given our constraints—team size (6 engineers, no infrastructure specialist), existing Redis deployment, 2-week implementation timeline, and modest budget—Redis Streams provides the optimal balance of capability and operational simplicity:

1. **Operational Simplicity**: We already run Redis for sessions and rate limiting. Adding Streams requires no new infrastructure, no cluster management, and leverages existing team familiarity.

2. **Implementation Velocity**: Redis Streams' Python client integration is straightforward. We can implement a producer-consumer pattern within days, not weeks, delivering immediate value.

3. **Sufficient Throughput**: At 500 req/s peak (5,000 req/s at 10x growth), Redis Streams can handle ~100K ops/sec on a single node—well above our requirements without clustering complexity.

4. **Delivery Guarantees**: Redis Streams support consumer groups with explicit acknowledgment, enabling at-least-once delivery. Exactly-once semantics for billing events can be achieved through idempotent processing with Redis-backed deduplication.

5. **Real-time Capabilities**: Redis Pub/Sub (already in use) seamlessly integrates with Streams for WebSocket push notifications, avoiding a separate messaging system.

6. **Cost Efficiency**: No additional infrastructure costs beyond our existing Redis instance, avoiding Kafka's operational overhead or managed service expenses.

## Consequences

### Pros
- **Rapid Deployment**: Functional within 2 weeks, addressing immediate latency issues
- **Low Operational Burden**: No new infrastructure to monitor, maintain, or scale
- **Team Familiarity**: Leverages existing Redis knowledge, reducing learning curve
- **Cost Effective**: No additional licensing or managed service fees
- **Integrated Ecosystem**: Streams + Pub/Sub provides both queueing and real-time messaging
- **Adequate Retention**: Configurable message retention (hours to days) suits notification use case

### Cons
- **Scale Limitations**: Single-node Redis has practical limits (~1M ops/sec); clustering adds complexity
- **Less Mature Ecosystem**: Fewer monitoring tools and client libraries than Kafka
- **No Built-in Schema Registry**: Message schema evolution requires manual management
- **Limited Replay Capabilities**: Compared to Kafka's long-term retention for replay
- **Weaker Ordering Guarantees**: Partitioning requires careful design for strict ordering

## Alternatives Considered

### Apache Kafka (Rejected)
While Kafka offers superior scale, stronger ordering guarantees, and a richer ecosystem, it introduces unacceptable complexity for our team:

1. **Operational Overhead**: Kafka requires dedicated expertise for cluster management, monitoring, and tuning—beyond our team's capacity.
2. **Implementation Timeline**: Learning curve and setup would exceed our 2-week constraint before delivering value.
3. **Cost**: Self-managed Kafka clusters require 3+ nodes for reliability; managed Confluent Cloud exceeds our modest budget.
4. **Over-engineering**: Kafka's enterprise-scale features (multi-datacenter replication, exactly-once semantics) exceed our notification subsystem needs.
5. **Integration Complexity**: Adding Kafka to our Python/Flask monolith requires new client libraries, configuration, and deployment processes.

Redis Streams meets our functional requirements with significantly lower complexity, enabling us to solve the immediate latency and reliability problems while maintaining capacity for 10x growth.

### Other Alternatives
- **RabbitMQ**: Requires additional infrastructure with similar operational burden to Redis
- **SQS/SNS**: Vendor lock-in and per-message costs at scale
- **Database Queues**: Would not solve the database connection pool exhaustion problem

Redis Streams represents the minimal viable architecture that addresses all critical requirements while respecting team constraints and timeline.