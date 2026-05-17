# ADR-001: Notification Subsystem Message Broker

## Status
Proposed

## Context

The current notification system in our SaaS project management platform processes notifications synchronously within HTTP request cycles. This architecture has become unsustainable as we've scaled to 85,000 monthly active users and ~2M tasks per month, causing:

- Request timeouts (800ms average, 8s peak) blocking user responses
- Silent failures when email/webhook providers are unavailable
- Cascading failures from slow webhook endpoints exhausting connection pools
- No delivery guarantees for billing-critical notifications

We need an asynchronous, durable, retry-capable system that:
- Decouples notifications from the HTTP request cycle
- Provides at-least-once delivery for billing events, exactly-once where feasible
- Supports retry with exponential backoff
- Handles 10x traffic growth without re-architecture
- Can support future real-time WebSocket push notifications

**Constraints:**
- 6-person engineering team (3 senior, 3 mid-level), no dedicated infrastructure engineer
- Already run Redis in production for sessions/rate limiting
- No Kafka experience on the team
- Maximum 2-week setup/migration window before delivering value
- Modest budget — cannot afford managed Confluent Cloud at full scale today
- Must maintain exactly-once semantics for billing notifications

## Decision

**We choose Redis Streams as the message broker for the notification subsystem, with a future migration path to Kafka if scale dictates.**

While Kafka provides stronger guarantees at massive scale, Redis Streams meets all current requirements, fits our team constraints, and can be implemented within the 2-week window. We will implement application-level idempotency to achieve exactly-once semantics for billing notifications.

## Consequences

### Positive Consequences

**Immediate Benefits:**
- **Zero new infrastructure**: Leverage existing Redis deployment, reducing operational complexity and cost
- **Fast implementation**: 2-week timeline is achievable; team is already familiar with Redis
- **Adequate performance**: Redis Streams can easily handle 500 req/s peak and 10x growth (5,000 req/s is well within Redis capabilities)
- **Consumer groups support**: Multiple consumers can process different notification types in parallel without duplication
- **Ordering guarantees**: Per-stream ordering ensures notifications are processed sequentially per-entity
- **Message retention**: Configurable retention policies (time-based or length-based) prevent unbounded memory growth
- **Simple monitoring**: Leverage existing Redis monitoring tools and team knowledge
- **Backpressure handling**: Consumers can ack messages individually, preventing overwhelm during slow webhook responses

**Architecture Alignment:**
- **At-least-once delivery**: Redis Streams guarantee message durability as long as messages are acknowledged; unreceived messages remain in the stream
- **Exactly-once semantics**: Achievable through application-level idempotency (deduplication by event_id in database) for billing notifications
- **Retry logic**: Explicit consumer error handling with exponential backoff implemented in application code
- **Dead-letter queue**: Separate stream for failed messages after max retry attempts
- **Migration path**: Consumer groups are compatible between Redis Streams and Kafka, facilitating future migration if needed

**Cost:**
- No additional infrastructure costs; uses existing Redis resources
- No managed service fees

### Negative Consequences

**Technical Trade-offs:**
- **Weaker durability guarantees**: Redis is an in-memory data store; messages are lost if Redis fails before persistence. Mitigated by AOF persistence and appropriate fsync settings.
- **No built-in exactly-once semantics**: Requires application-level idempotency implementation for billing events
- **Fewer enterprise features**: No schema registry, no built-in advanced monitoring, no transactional API across partitions
- **Scaling complexity**: Redis Streams scale vertically; high throughput (>100k msg/s) may require sharding across multiple Redis instances
- **Message format**: All messages must fit in memory; extremely large payloads require out-of-band storage

**Operational Trade-offs:**
- **Single point of failure**: Existing Redis becomes more critical; requires robust backup and failover procedures
- **Memory pressure**: Message retention and load compete for memory; requires careful capacity planning
- **Limited Kafka parity**: Team must learn Kafka anyway if scale demands migration within 2-3 years
- **Fewer third-party integrations**: Smaller ecosystem compared to Kafka Connect/KSQL

## Alternatives Considered

### Apache Kafka

**Why we rejected it:**

1. **Violates 2-week implementation constraint**: Setting up Kafka (even with Docker Compose) and establishing operational procedures (monitoring, topic management, consumer group balancing) would exceed the timeline. The team has no prior Kafka experience.

2. **Operational complexity exceeds team capacity**: Kafka requires:
   - ZooKeeper (or KRaft mode) cluster management
   - Broker configuration (replication, partitioning, retention)
   - Topic partitioning strategy aligned with consumer scaling
   - JVM-based monitoring and tuning
   - Isolated infrastructure or managed service (Confluent Cloud is cost-prohibitive)

3. **Over-engineering for current scale**: Kafka shines at millions of messages per second with durable, ordered, partitioned streaming. Our peak load is 500 req/s (~2M notifications/day); Kafka's capabilities are underutilized at this scale.

4. **Runs counter to "simple solutions first" philosophy**: Redis Streams solves the problem today with minimal complexity; Kafka introduces operational burden that doesn't map to immediate pain points.

5. **Infrastructure budget constraints**: Self-hosting Kafka requires dedicated servers or significant cloud resources. Managed Confluent Cloud is expensive at full scale.

**When we would reconsider Kafka:**
- Sustained message rates exceed 50,000 msg/s
- Need cross-datacenter replication for disaster recovery
- Require advanced stream processing (joins, aggregations) on notification events
- Team grows to include dedicated infrastructure engineer
- Budget allows for fully managed Kafka service

**Kafka's strengths remain:**
- Strong durability guarantees (replicated log storage)
- Native exactly-once semantics with idempotent producers
- Superior horizontal scaling via partitioning
- Robust ecosystem and enterprise tooling
- Message compression reducing storage/network costs

### Why Not Other Alternatives

**RabbitMQ:**
- Offers similar feature set to Redis Streams but requires additional infrastructure
- No operational team experience; adds monitoring overhead
- Stronger AMQP features (confirms, dead-letter exchanges) but overkill for current needs

**Amazon SQS:**
- Managed service eliminates operational burden
- Provides built-in dead-letter queues and at-least-once delivery
- Higher long-term costs at scale ($0.40 per 1M requests)
- Would require learning AWS-specific tooling; team prefers open source

**Message queues without persistence (e.g., asyncio.Queue):**
- No durability guarantees — violates billing notification requirements
- Messages lost during web server restarts or deployments

## Implementation Plan

1. **Week 1**: Implement producer publishing notifications to Redis Streams
2. **Week 1**: Build consumer groups for email, webhook, and billing notification types
3. **Week 2**: Implement retry logic with exponential backoff and dead-letter queue
4. **Week 2**: Add application-level idempotency for billing events using event_id deduplication
5. **Week 2**: Migration strategy: feature flag to gradually shift traffic from sync to async

## Monitoring and Observability

Key metrics to track:
- Message backlog by consumer group
- Consumer lag and processing time
- Redis memory usage and eviction rate
- Retry and dead-letter queue volumes
- End-to-end notification latency

## References

- Redis Streams documentation: https://redis.io/docs/data-types/streams/
- Kafka comparison with Redis Streams: https://redis.io/docs/manual/patterns/redis-append-only-file/
- Our current infrastructure sizing and capacity planning documents