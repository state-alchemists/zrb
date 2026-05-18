# ADR-001: Notification Subsystem Architecture

## Status

Proposed

## Context

Our SaaS project management platform serves 85,000 monthly active users with ~500 requests/second at peak. The current notification system sends emails and webhooks synchronously within the HTTP request cycle, causing:

- **Request timeouts**: Average latency 800ms, spikes to 8s during peak hours
- **Silent failures**: No retry mechanism or dead-letter queue; notifications are dropped when providers fail
- **Cascading failures**: Slow webhook endpoints have exhausted connection pools twice this year
- **No delivery guarantees**: Billing-critical notifications (trial expiration, payment failures) require exactly-once delivery

We need to decouple notification processing from HTTP requests, support retry with exponential backoff, guarantee at-least-once delivery for all notifications (exactly-once for billing), and handle 10x traffic growth (up to 5,000 req/s peak) without re-architecting.

**Constraints:**
- 6-person engineering team (no dedicated infrastructure engineer)
- Redis already in production for sessions and rate limiting
- No Kafka operational experience
- Must demonstrate value within 2 weeks of starting
- Budget cannot accommodate managed Confluent Cloud at scale
- Exactly-once semantics required for billing notifications

## Decision

**We will use Redis Streams** for the notification subsystem.

### Justification

Redis Streams meets our throughput requirements while fitting our team composition, timeline, and budget constraints. The decision is driven by four factors:

1. **Operational fit**: Our 6-person team has no dedicated infrastructure engineer. We cannot staff dedicated Kafka operations, whereas we already run Redis in production and have operational familiarity.

2. **Time to value**: Redis Streams can be integrated into our Flask application within days, using our existing Redis 7+ instance. Kafka would require 2-4 weeks minimum for cluster setup, topic configuration, and producer/consumer implementation—exceeding our 2-week constraint.

3. **Throughput adequacy**: Our peak load of 500 req/s (projected 5,000 req/s at 10x) is well within Redis Streams' capacity (100k+ messages/second on modest hardware). Kafka's superior throughput (millions/sec) is overkill for our use case and adds operational overhead we cannot justify.

4. **Cost alignment**: Redis Streams has zero incremental infrastructure cost beyond our existing Redis deployment. Self-hosted Kafka requires dedicated broker nodes and ZooKeeper, increasing operational burden and AWS costs. Managed Kafka (Confluent Cloud) exceeds our budget.

## Consequences

### Pros

- **Rapid deployment**: Existing Redis instance reduces initial setup to application-level integration. First notification can flow through async processing within 3-5 days.

- **Lower operational overhead**: Single technology for caching, sessions, and queuing reduces cognitive load. Team already knows Redis CLI, monitoring, and failure modes.

- **Adequate throughput**: Redis Streams handles 100k+ messages/second. At 10x growth (5,000 req/s peak), we operate at 5% of theoretical capacity.

- **Consumer group support**: XREADGROUP provides partition-like semantics with automatic message delivery tracking. XACK enables acknowledgment-based delivery confirmation.

- **Message persistence**: RDB/AOF persistence and configurable stream length (XTRIM) allow retention of unprocessed messages across restarts. We can set MAXLEN ~1,000,000 to keep last several hours of notifications.

- **WebSocket compatibility**: Redis pub/sub (already in our roadmap for real-time notifications) pairs naturally with Streams. Web-socket servers can subscribe to notification streams for real-time push without additional infrastructure.

- **Exponential backoff ready**: Application-level retry logic with Redis' ZSET for delayed delivery scheduling (simpler than Kafka's lack of native delayed queues).

### Cons

- **No native exactly-once semantics**: Kafka provides broker-level exactly-once via transactional writes. Redis Streams requires application-level deduplication using unique message IDs and idempotent handlers. For billing notifications, we will implement:
  - UUID-based message IDs persisted in PostgreSQL before stream write
  - Consumer-side deduplication via Redis SET tracking processed IDs (24-hour TTL)
  - PostgreSQL update marking notification "delivered" only after successful send

- **Memory-bound retention**: Unlike Kafka's disk-based log retention (days/weeks default), Redis streams are memory-resident. We must tune MAXLEN to balance message history vs. memory. A consumer outage exceeding retention window results in lost messages. Mitigation: persist critical billing notifications to PostgreSQL before stream write.

- **Less mature ecosystem**: Fewer third-party monitoring, schema registry, and governance tools compared to Kafka. Our Python consumers will use `redis-py` directly rather than higher-level frameworks.

- **Scaling friction beyond clustered mode**: If we ever exceed single Redis node capacity, migrating to Redis Cluster requires application-level changes (hash slot awareness). Kafka scales horizontally without application code changes.

- **Consumer rebalancing complexity**: Kafka's consumer group protocol handles partition assignment automatically during scaling events. Redis Streams lacks native rebalancing; our initial implementation assigns workers via simple round-robin or application-level consistent hashing, which works at 6-person team scale but requires engineering if we grow the consumer fleet significantly.

## Alternatives Considered

### Apache Kafka

**Why rejected:**

- **Operational mismatch**: Kafka requires dedicated infrastructure expertise (broker management, ZooKeeper configuration, topic partition strategy, replication factor tuning). Our team has no Kafka experience and cannot spare engineers to acquire it. Misconfigured Kafka is worse than no queue—it corrupts data during failures.

- **Timeline violation**: Minimum viable Kafka deployment (self-hosted: 3 brokers + 3 ZooKeeper nodes for HA) requires 2-4 weeks of setup, monitoring integration, and application development. This exceeds our 2-week delivery constraint.

- **Cost**: Self-hosted Kafka requires dedicated EC2 instances (m5.large or larger). At our scale, this adds $300-500/month plus engineering time for maintenance. Managed Kafka (Confluent Cloud) costs $0.10-0.23/GB throughput—prohibitively expensive at 10x growth when budget is constrained.

- **Over-engineering**: Kafka's strengths (exactly-once transactions, infinite retention, multi-datacenter replication) solve problems we don't have. Our billing notification volume is ~500/week (not billions/day). Redis Streams with application-level deduplication achieves equivalent guarantees at lower complexity.

Kafka would be appropriate if we had: (a) dedicated infrastructure team, (b) multi-year retention requirements, (c) microservices architecture requiring event sourcing, (d) 100k+ req/s throughput needs, or (e) budget for managed services. None apply today. We can revisit if our scaling trajectory changes—Redis Streams architecture migrates to Kafka cleanly (both are log-based).