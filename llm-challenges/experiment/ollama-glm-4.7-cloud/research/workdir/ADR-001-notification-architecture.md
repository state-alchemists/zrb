# ADR-001: Notification Subsystem Architecture

## Status
Proposed

## Context

We operate a SaaS project management platform with 85,000 monthly active users, experiencing ~500 req/s peak traffic. The current notification system handles emails and webhooks synchronously within the HTTP request cycle, causing:

- **Request timeouts**: 800ms average latency, spiking to 8s during peak hours
- **Silent failures**: No retry mechanism or dead-letter queue for failed deliveries
- **Cascading failures**: Slow webhook endpoints have caused connection pool exhaustion, taking down unrelated features
- **No delivery guarantees**: Billing-critical notifications ("trial expired", "payment failed") lack exactly-once semantics

We need to decouple notifications from the request cycle, support retry with exponential backoff, guarantee at-least-once delivery for billing events (exactly-once where feasible), and handle 10x traffic growth within 2 quarters.

**Constraints:**
- Engineering team: 6 people (3 senior, 3 mid-level), no dedicated infrastructure engineer
- Already run Redis in production for session storage and rate limiting
- No Kafka experience on the team
- Must deliver value within 2 weeks of setup/migration
- Modest budget — cannot afford managed Confluent Cloud at full scale
- Must maintain exactly-once semantics for billing notifications

## Decision

**Choose Redis Streams** for the notification subsystem.

Redis Streams provides sufficient throughput, ordering guarantees, and consumer group support to meet our requirements while aligning with our team size, existing infrastructure, and timeline constraints.

### Justification

**1. Operational Complexity Matches Team Capacity**
- Redis Streams requires no additional infrastructure components beyond our existing Redis deployment
- No ZooKeeper/KRaft cluster management, broker configuration, or partition planning
- Team already has Redis operational experience; learning curve is minimal
- Can be deployed and tested within 1 week, leaving 1 week for migration

**2. Throughput Adequacy for 10x Growth**
- Current: ~500 req/s peak → ~2M tasks/month
- 10x target: ~5,000 req/s peak → ~20M tasks/month
- Redis Streams handles 100K+ messages/second on modest hardware; our peak is well within capacity
- Consumer groups (XREADGROUP) enable horizontal scaling across multiple workers

**3. Ordering and Retention Requirements Met**
- Per-stream ordering guarantees ensure notifications are processed in sequence
- Configurable retention (XADD with MAXLEN) allows keeping messages for retry windows (e.g., 7 days)
- Persistent storage (RDB/AOF) prevents data loss during restarts

**4. Exactly-Once Semantics Achievable via Application-Level Idempotency**
- Redis Streams does not provide native exactly-once semantics
- However, we can achieve exactly-once for billing notifications using PostgreSQL:
  - Create a `notification_deliveries` table with unique constraint on `(notification_id, recipient)`
  - Workers check this table before processing; duplicates are skipped
  - This pattern is simpler than Kafka's transactional exactly-once and leverages our existing database

**5. Cost and Timeline Alignment**
- No additional infrastructure costs — Redis already running
- No managed service fees (unlike Confluent Cloud at $1000+/month for our scale)
- 2-week timeline achievable: 3 days setup, 5 days implementation, 2 days testing/migration

**6. Future WebSocket Support**
- Redis Streams can serve as the backbone for real-time push notifications
- Pub/Sub channels can be layered on top for WebSocket delivery
- Single technology stack reduces cognitive load

## Consequences

### Positive

- **Rapid time-to-value**: Production-ready within 2 weeks vs. 4-6 weeks for Kafka
- **Low operational overhead**: Single Redis instance vs. 3+ Kafka brokers + ZooKeeper/KRaft
- **Cost-effective**: No additional infrastructure spend; leverages existing Redis
- **Team confidence**: Builds on existing Redis knowledge rather than introducing unfamiliar technology
- **Sufficient scalability**: Handles 10x growth without re-architecture
- **Retry and dead-letter support**: Consumer groups with pending entries list enable retry logic
- **Monitoring simplicity**: Redis INFO command and existing monitoring tools vs. Kafka's complex metrics

### Negative

- **No native exactly-once semantics**: Requires application-level idempotency implementation
- **Limited message retention**: In-memory with optional persistence; not suitable for weeks-long retention without careful configuration
- **Single point of failure**: Redis cluster required for high availability (adds complexity but still simpler than Kafka)
- **Less mature ecosystem**: Fewer tools and integrations compared to Kafka's rich ecosystem
- **Cross-datacenter replication**: More complex than Kafka's built-in replication (if we ever need multi-region)
- **Message replay limitations**: Cannot easily replay from arbitrary offsets like Kafka

### Mitigations

- For exactly-once: Implement PostgreSQL-based idempotency with unique constraints
- For retention: Configure MAXLEN with approximate trimming; use Redis persistence (AOF) for durability
- For high availability: Deploy Redis Cluster with 3 masters + replicas (still simpler than Kafka)
- For monitoring: Extend existing Redis monitoring; add custom metrics for stream lag

## Alternatives Considered

### Apache Kafka

**Why Rejected:**

1. **Operational complexity exceeds team capacity**
   - Requires managing 3+ brokers, ZooKeeper/KRaft, topic partitions, consumer groups
   - No dedicated infrastructure engineer; would burden senior developers
   - Learning curve steep: team has zero Kafka experience

2. **Timeline incompatible with 2-week constraint**
   - Production-grade Kafka setup: 4-6 weeks minimum for team with no experience
   - Includes: cluster planning, security configuration, monitoring setup, disaster recovery testing
   - Would delay notification improvements by 1+ month

3. **Cost prohibitive at scale**
   - Self-hosted: 3+ m5.large instances ($300+/month) + ZooKeeper/KRaft overhead
   - Managed (Confluent Cloud): $1000+/month for our projected scale
   - Budget constraints rule out both options

4. **Over-engineering for current and near-term needs**
   - Kafka designed for millions of messages/second; our peak is ~5,000 req/s
   - Features like cross-datacenter replication, schema registry, and KSQL are unnecessary
   - Complexity outweighs benefits for our use case

5. **Exactly-once semantics not a differentiator**
   - Kafka's exactly-once requires transactions and careful idempotent producer configuration
   - Our PostgreSQL-based idempotency approach achieves the same result with simpler tooling
   - Billing notifications are low-volume; application-level deduplication is sufficient

**When Kafka Would Be Appropriate:**
- Team grows to include dedicated infrastructure engineer
- Traffic reaches 50K+ req/s or requires multi-region deployment
- Need for complex event sourcing, stream processing, or real-time analytics
- Budget allows for managed Kafka services

### Other Alternatives Briefly Evaluated

- **RabbitMQ**: Rejected due to operational complexity (Erlang runtime, cluster management) and lower throughput than Redis Streams
- **AWS SQS/SNS**: Rejected due to vendor lock-in and cost at scale; also introduces additional service dependency
- **Database polling**: Rejected due to inefficiency and lack of real-time guarantees

## Implementation Plan

1. **Week 1: Setup and Infrastructure**
   - Enable Redis Streams on existing Redis instance (or deploy Redis Cluster for HA)
   - Configure persistence (AOF) and retention policies
   - Set up monitoring for stream lag and consumer group health

2. **Week 2: Implementation and Migration**
   - Implement producer: Flask app publishes to Redis Stream on task events
   - Implement consumer: Worker processes stream with XREADGROUP, handles retries
   - Add PostgreSQL idempotency table for billing notifications
   - Migrate existing notification logic to async pattern
   - Deploy and validate with canary traffic

3. **Post-Launch: Optimization**
   - Add dead-letter queue for failed deliveries
   - Implement exponential backoff in consumer
   - Add metrics and alerting for delivery failures
   - Plan WebSocket integration for real-time push notifications

## References

- Redis Streams documentation: https://redis.io/docs/data-types/streams/
- Kafka vs Redis Streams comparison: https://redis.io/docs/manual/patterns/distributed-locks/
- Team constraints from system_context.md