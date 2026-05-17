# ADR-001: Notification Subsystem Architecture

## Status

**Proposed**

## Context

Our SaaS project management platform currently processes notifications synchronously within the HTTP request cycle. This has created critical operational issues:

- **Request timeouts**: Average latency of 800ms, spiking to 8s during peak hours (~500 req/s)
- **No failure recovery**: Notification failures are silently dropped with no retry mechanism
- **Cascading failures**: Slow webhook endpoints have caused connection pool exhaustion, taking down unrelated features (2 incidents this year)
- **Missing delivery guarantees**: Billing-critical notifications (e.g., "payment failed", "trial expired") have no delivery guarantees

We need to decouple notification processing from HTTP responses, implement retry with exponential backoff, and establish at-least-once delivery (exactly-once for billing events). The system must support 10x traffic growth (5,000 req/s) without re-architecting, and lay groundwork for real-time WebSocket push notifications within 2 quarters.

### Constraints

- Engineering team: 6 people (3 senior, 3 mid-level), no dedicated infrastructure engineer
- Redis already deployed and operational for sessions/rate limiting
- No Kafka experience on the team
- Maximum 2 weeks for initial setup and migration before delivering value
- Modest budget — managed Kafka (Confluent Cloud) is cost-prohibitive at scale

## Decision

**We will use Redis Streams as the notification message bus.**

Redis Streams provides sufficient throughput for our current and projected scale (5,000 req/s) while requiring minimal operational overhead since Redis is already production-hardened in our environment. It supports consumer groups for horizontal scaling and pending entry lists for implementing retry logic. The 2-week timeline is achievable because it builds on existing infrastructure rather than introducing new systems.

For exactly-once semantics on billing notifications, we will implement **idempotency keys** combined with consumer-side deduplication using a dedicated Redis keyspace that tracks successfully processed billing events with a TTL matching our audit window (30 days).

## Consequences

### Positive

- **Rapid deployment**: Can deliver working async notifications within days, not weeks, since Redis is already operational
- **Low operational burden**: No new infrastructure to monitor, back up, or tune; leverages existing Redis operational expertise
- **Sufficient throughput**: Redis Streams handles 100K+ messages/second per node — 20x our 10x growth target
- **Native consumer groups**: Built-in support for multiple consumers, automatic rebalancing, and claim mechanism for failed message redelivery
- **Retry support**: Pending entry list (`XPENDING`, `XCLAIM`) enables implementing exponential backoff without additional infrastructure
- **WebSocket readiness**: Streams naturally extends to Redis Pub/Sub for real-time WebSocket push notifications in Q3/Q4
- **Cost efficient**: Uses existing infrastructure; no additional service fees or significant compute costs

### Negative

- **Exactly-once requires application logic**: Redis Streams provides at-least-once delivery; exactly-once semantics rely on idempotency keys and consumer tracking, adding complexity to billing event handlers
- **Memory-bound retention**: Message retention is constrained by available RAM; long-term audit trails require archival to PostgreSQL
- **No built-in compaction**: Unlike Kafka's log compaction, stream trimming is time/size-based; historical replay capabilities are limited
- **Operational risk**: Redis becomes a critical path dependency for notifications; existing session/rate-limiting traffic now shares infrastructure with business-critical notifications
- **Scaling ceiling**: While sufficient for 10x growth, extreme scale (100K+ req/s) would eventually require migration to Kafka

## Alternatives Considered

### Apache Kafka (Rejected)

Kafka would provide superior exactly-once semantics (idempotent producers, transactional delivery), disk-based retention, and indefinite scalability. These are genuine advantages for a notification system.

However, we rejected Kafka based on **operational reality**:

1. **Learning curve**: The team has zero Kafka experience. Self-hosting requires expertise in broker tuning, partition rebalancing, consumer group protocols, and cluster coordination (ZooKeeper or KRaft).

2. **Setup timeline**: A production-ready Kafka deployment with proper replication, monitoring, and alerting requires 3–4 weeks minimum — exceeding our 2-week constraint.

3. **Operational overhead**: Without a dedicated infrastructure engineer, Kafka cluster maintenance becomes a significant distraction from product development. The risk of misconfiguration causing data loss or extended outages outweighs the technical benefits at our current scale.

4. **Cost**: Managed Kafka (Confluent Cloud) provides operational simplicity but exceeds our modest budget at full scale.

We will **revisit Kafka when**:
- We approach Redis Streams throughput limits (>50K messages/second sustained)
- We need multi-day message retention for audit/compliance
- The team grows to include infrastructure expertise

## Implementation Notes

- Use Redis Stream per notification priority: `notifications:critical`, `notifications:standard`, `notifications:low`
- Implement billing idempotency via `SET billing:event:{idempotency_key} 1 EX 2592000 NX` before processing
- Archive billing events to PostgreSQL after delivery confirmation for audit trail
- Monitor Redis memory usage; configure `MAXLEN` trims on streams to prevent unbounded growth

---

*Proposed by: Architecture Review Board*  
*Date: 2024-XX-XX*
