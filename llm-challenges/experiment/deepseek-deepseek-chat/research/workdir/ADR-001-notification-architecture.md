# ADR-001: Notification Subsystem Architecture

## Title
Notification Subsystem: Redis Streams over Apache Kafka

## Status
Accepted

## Context
Our SaaS project management platform (85k MAU, ~500 req/s peak) currently handles notifications synchronously within HTTP request cycles, causing:
1. Request timeouts (800ms avg latency, 8s spikes)
2. Silent failures when external services are down
3. Cascading failures from slow webhook endpoints
4. No delivery guarantees for billing-critical notifications

We need to decouple notifications from request processing, support retry with exponential backoff, guarantee at-least-once delivery (exactly-once for billing events), add WebSocket push notifications within 2 quarters, and handle 10x traffic growth.

Constraints:
- Team of 6 (3 senior, 3 mid-level), no dedicated infrastructure engineer
- Already running Redis in production for session/rate limiting
- No Kafka experience on the team
- Must deliver value within 2 weeks of setup/migration
- Modest budget (cannot afford managed Confluent Cloud at scale)
- Must maintain exactly-once semantics for billing notifications

## Decision
We choose **Redis Streams** over Apache Kafka for our notification subsystem.

Primary justification: Redis Streams provides sufficient throughput (handles our 500 req/s peak with 10x headroom), strong ordering guarantees, and exactly-once semantics via consumer groups and message IDs—all while leveraging our existing Redis infrastructure and team familiarity.

Key technical reasons:
1. **Operational simplicity**: Redis is already in production; adding Streams requires no new infrastructure or specialized operational knowledge
2. **Time-to-value**: Implementation can be completed within the 2-week constraint using existing Redis client libraries
3. **Cost efficiency**: No additional infrastructure costs beyond our current Redis instance
4. **Team expertise**: The team understands Redis patterns; Kafka would require significant learning investment
5. **Sufficient scale**: Redis Streams can handle ~50k ops/sec per shard, far exceeding our 5k req/s 10x growth target

## Consequences

### Pros
1. **Rapid deployment**: Can implement within 2 weeks using Python Redis clients
2. **Lower operational burden**: No Kafka cluster management, monitoring, or tuning required
3. **Cost effective**: No additional infrastructure costs
4. **Familiar patterns**: Team can leverage existing Redis knowledge for debugging and maintenance
5. **Good enough guarantees**: Redis Streams provide at-least-once delivery with exactly-once semantics achievable via idempotent consumers
6. **WebSocket integration**: Redis Pub/Sub can be used alongside Streams for real-time push notifications

### Cons
1. **Lower throughput ceiling**: While sufficient for our needs (~5k req/s), Redis has lower maximum throughput than Kafka (~100k+ req/s)
2. **Limited retention**: Redis is memory-bound; we'll need to implement archival for long-term message storage
3. **Less mature ecosystem**: Fewer monitoring tools and client libraries compared to Kafka
4. **Scalability limitations**: Horizontal scaling requires Redis Cluster, which adds complexity for cross-slot operations
5. **No built-in schema registry**: Message schema evolution must be managed manually

## Alternatives Considered

### Apache Kafka (Rejected)

**Why it was attractive:**
- Industry-standard for event streaming with proven scale
- Strong durability guarantees with disk-based storage
- Rich ecosystem (Kafka Connect, Schema Registry, KSQL)
- Superior throughput for massive scale (>100k req/s)
- Built-in log compaction for exactly-once semantics

**Why we rejected it:**
1. **Operational complexity**: Requires 3-5 node cluster minimum, ZooKeeper dependency, and specialized monitoring
2. **Team learning curve**: No Kafka experience on the team; would require months to become proficient
3. **Time-to-value**: Setup, testing, and migration would exceed 2-week constraint
4. **Cost**: Self-managed Kafka requires significant operational overhead; managed Confluent Cloud is budget-prohibitive
5. **Over-engineering**: Our scale (500 req/s peak, 5k req/s target) doesn't justify Kafka's complexity
6. **Infrastructure mismatch**: Would require new AWS instances, security groups, and monitoring dashboards

**Technical mismatch with constraints:**
- Kafka's exactly-once semantics require significant configuration and consumer logic
- Consumer group rebalancing can cause latency spikes unsuitable for real-time notifications
- No existing team expertise would slow incident response and increase risk

### Redis Streams vs. Other Alternatives
We considered but rejected:
- **RabbitMQ**: Requires separate infrastructure, less familiar to team
- **AWS SQS/SNS**: Vendor lock-in, higher cost at scale
- **PostgreSQL LISTEN/NOTIFY**: Limited scalability, no consumer groups
- **In-house queue**: Too much development time, reinventing the wheel

Redis Streams strikes the optimal balance between capability, simplicity, and alignment with our team's skills and existing infrastructure.