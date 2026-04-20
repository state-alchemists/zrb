# ADR-001: Notification Subsystem Architecture

## Status
Proposed

## Context

Our SaaS project management platform (85k MAU, 500 req/s peak) currently handles notifications synchronously within the HTTP request cycle. This architecture has caused:

- **Request timeouts**: 800ms average latency, spiking to 8s during peak hours
- **Silent failures**: No retry or dead-letter queue when email/webhook providers are down
- **Cascading failures**: Slow webhook endpoints have caused connection pool exhaustion, taking down unrelated features
- **No delivery guarantees**: Billing-critical notifications ("trial expired", "payment failed") lack exactly-once semantics

We need to:
- Decouple notifications from the HTTP request cycle
- Support retry with exponential backoff
- Guarantee at-least-once delivery for billing events, exactly-once where feasible
- Add real-time WebSocket push notifications within 2 quarters
- Handle 10x traffic growth (to ~5000 req/s) without re-architecting

**Constraints:**
- 6-person team (3 senior, 3 mid-level), no dedicated infrastructure engineer
- Redis already in production (session storage, rate limiting)
- No Kafka experience on the team
- Must deliver value within 2 weeks of setup/migration
- Modest budget - cannot afford managed Confluent Cloud at full scale
- Must maintain exactly-once semantics for billing notifications

## Decision

**Choose Redis Streams** for the notification subsystem.

Redis Streams provides sufficient throughput, ordering guarantees, and consumer group semantics to meet our requirements while staying within our team's operational capacity and timeline constraints.

### Justification

**1. Throughput Requirements**
- Current peak: 500 req/s → 10x target: 5000 req/s
- Redis Streams can handle 100K-1M messages/second on a single instance
- Our notification volume is bounded by request rate, not independent event generation
- Redis Streams comfortably exceeds our 10x growth target

**2. Ordering Guarantees**
- Both Kafka and Redis Streams provide strong ordering guarantees per stream/partition
- For notifications, per-user or per-task ordering is sufficient
- Redis Streams maintains strict ordering within each stream

**3. Message Retention**
- Kafka: Disk-based, configurable retention (days to years)
- Redis Streams: Memory-based with configurable MAXLEN, can persist to disk via AOF/RDB
- For notifications, 7-30 day retention is adequate for debugging and replay
- Redis Streams with XADD MAXLEN ~10000 per stream provides sufficient window

**4. Consumer Groups**
- Both technologies support consumer groups with offset management
- Redis Streams XREADGROUP provides identical semantics for our use case
- Enables horizontal scaling of notification workers

**5. Exactly-Once Semantics**
- Kafka: Native exactly-once with transactions (requires careful setup, idempotent producers)
- Redis Streams: No native exactly-once, but achievable via application-level idempotency
- For billing notifications, we will implement idempotent processing using unique message IDs stored in PostgreSQL
- This pattern is well-understood and aligns with our existing database architecture

**6. Operational Complexity**
- Kafka: Requires ZooKeeper/KRaft, multiple brokers, partition management, monitoring, rebalancing
- Redis Streams: Single Redis instance, already in production, minimal additional complexity
- Our team has no Kafka experience; learning curve would exceed 2-week timeline
- Redis operational knowledge already exists on the team

**7. Setup Time**
- Kafka: 2-4 weeks minimum for production-ready deployment with a team new to Kafka
- Redis Streams: < 1 week to implement producer/consumer, test, and deploy
- Meets our 2-week constraint with buffer for testing

**8. Cost**
- Kafka: Self-hosted requires 3+ brokers for HA; managed Confluent exceeds budget
- Redis Streams: No additional cost - already running Redis
- Fits modest budget constraints

**9. Future WebSocket Support**
- Redis Streams can serve as the backbone for real-time push notifications
- Consumers can publish to WebSocket channels upon processing
- No architectural change needed when adding WebSocket support

## Consequences

### Positive

- **Fast time-to-value**: Can deliver async notifications within 2 weeks
- **Low operational overhead**: Leverages existing Redis infrastructure and team knowledge
- **Sufficient scalability**: Handles 10x growth without architectural changes
- **Cost-effective**: No additional infrastructure costs
- **Clean migration path**: Can incrementally move from sync to async without big-bang rewrite
- **Built-in retry**: Consumer groups with pending entries list enable retry with exponential backoff
- **Dead-letter queue**: Can implement using separate Redis stream for failed messages

### Negative

- **No native exactly-once**: Requires application-level idempotency implementation
- **Memory-based retention**: Longer retention requires more RAM; disk persistence adds latency
- **Single point of failure**: Redis instance becomes critical (mitigated by existing Redis HA setup)
- **Limited ecosystem**: Fewer tools and integrations compared to Kafka ecosystem
- **Future re-architecture**: If we exceed Redis Streams capacity (unlikely given our growth profile), migration to Kafka would be required

### Mitigations

- Implement idempotent processing for billing notifications using PostgreSQL unique constraints
- Configure Redis with AOF persistence for durability
- Monitor Redis memory usage and set appropriate MAXLEN policies
- Plan for Redis Cluster if single instance becomes bottleneck
- Document message schema to ease future migration if needed

## Alternatives Considered

### Apache Kafka

**Rejected because:**

1. **Operational complexity exceeds team capacity**: Kafka requires dedicated infrastructure expertise. Our 6-person team has no Kafka experience. Learning curve, setup, and operational burden would exceed 2-week timeline and ongoing maintenance capacity.

2. **Cost constraints**: Self-hosted Kafka requires 3+ brokers for high availability, increasing infrastructure costs. Managed Confluent Cloud at our scale exceeds budget constraints.

3. **Over-engineering for current needs**: Kafka's strength is massive scale (millions of messages/second) and complex event sourcing. Our notification volume is bounded by request rate (~5000 req/s target). Redis Streams provides sufficient throughput with 1/10th the complexity.

4. **Timeline risk**: Even with managed Kafka, setup, schema design, producer/consumer implementation, testing, and deployment would exceed 2-week window for a team with no prior experience.

5. **Exactly-once complexity**: While Kafka supports exactly-once semantics, implementing it correctly requires transactional producers, idempotent consumers, and careful offset management. This complexity is not justified given we can achieve the same result with application-level idempotency in Redis Streams.

Kafka would be the right choice if we had:
- Dedicated infrastructure engineer
- Higher message volume (independent event generation, not request-bounded)
- Need for long-term event replay (months/years)
- Budget for managed services
- Longer timeline for migration

None of these conditions apply to our current situation.