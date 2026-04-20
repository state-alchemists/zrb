# ADR-001: Notification Subsystem Message Broker Selection

## Status

**Proposed**

## Context

We operate a SaaS project management platform serving 85,000 monthly active users, generating ~2 million tasks per month. The notification subsystem currently executes synchronously within the HTTP request cycle, causing:

1. **Request timeouts**: Average latency 800ms, spikes to 8s during peak hours (~500 req/s)
2. **Silent failures**: Downstream provider issues result in dropped notifications with no retry mechanism
3. **Cascading failures**: Two incidents where slow webhook endpoints caused connection pool exhaustion, degrading unrelated features
4. **No delivery guarantees**: Billing-critical notifications (trial expired, payment failed) lack exactly-once semantics

**Scaling Requirements:**
- Decouple notifications from HTTP request cycle (async processing)
- Retry with exponential backoff and dead-letter queue
- At-least-once delivery minimum, exactly-once for billing events
- Support WebSocket push notifications within 2 quarters
- Handle 10x traffic growth (5,000 req/s peak)

**Team Constraints:**
- 6 engineers (3 senior, 3 mid-level), no dedicated infrastructure engineer
- No Kafka experience currently on the team
- Existing Redis deployment (session storage, rate limiting)
- 2-week maximum migration window before delivering value
- Modest budget (cannot afford managed Confluent Cloud at full scale)

## Decision

**Chosen Option: Redis Streams**

Redis Streams is selected as the notification subsystem's message broker. This decision is driven by the team's existing Redis expertise, operational simplicity, sufficient throughput characteristics, and alignment with the 2-week delivery constraint.

## Rationale

### Apache Kafka Evaluation

| Property | Kafka | Assessment for Our Use Case |
|----------|-------|----------------------------|
| Throughput | Millions of events/sec | Excessive; 100-500K req/s is adequate |
| Ordering guarantees | Per-partition ordering | Solid, but adds partitioning complexity |
| Message retention | Configurable (days/weeks) | Overkill for notification workloads |
| Consumer groups | Mature, sophisticated | Powerful but steep learning curve |
| Exactly-once | Native transactions (EOS) | Best-in-class, but complex to implement |
| Operational complexity | High | Requires cluster sizing, replication factor, broker monitoring, partition management |
| Setup time | 2+ weeks minimum | Exceeds constraint for initial value delivery |
| Team familiarity | None | 6-month ramp-up typical for production mastery |

**Key weaknesses for our context:**
- Zero Kafka experience necessitates significant learning investment
- Self-managed Kafka on AWS requires dedicated infrastructure expertise we lack
- Managed alternatives (Confluent Cloud, AWS MSK) exceed modest budget at scale
- Operational burden (monitoring, partition rebalancing, broker failures) unsuitable for 6-person team

### Redis Streams Evaluation

| Property | Redis Streams | Assessment for Our Use Case |
|----------|---------------|----------------------------|
| Throughput | 100K-500K events/sec | Sufficient for 10x growth target (5K req/s) |
| Ordering guarantees | Per-stream FIFO | Solid for notification sequencing |
| Message retention | Maxlen or exact TTL (up to bytes) | Adequate; configure based on retry window |
| Consumer groups | XREADGROUP, XACK, XPENDING | Mature ACKs with pending entry inspection |
| Exactly-once | Idempotent consumers (dedup keys) | Achievable; requires application-layer dedup |
| Operational complexity | Low-Medium | Leverages existing Redis deployment |
| Setup time | 1-3 days | Aligns with 2-week migration window |
| Team familiarity | High | Daily production use for sessions/rate limiting |

**Key strengths for our context:**
- Zero additional infrastructure; extend existing Redis deployment
- Team possesses operational expertise for Redis failure modes
- Consumer groups provide at-least-once with XPENDING inspection for retry logic
- XACK + idempotency keys in application layer achieve effectively-once for billing events
- Minimal operational overhead suitable for 6-person team

## Consequences

### Positive Consequences

1. **Fast time-to-value**: Redis Streams can be operational within days, not weeks. Initial async notification processing can ship within the 2-week constraint.
2. **Operational continuity**: Existing Redis monitoring, backups, and failover procedures extend naturally to Streams. No new infrastructure to operate.
3. **Sufficient throughput**: Current Redis Streams handle 100K-500K events/sec. At 500 req/s peak (likely 2-3 events per request = 1,500 events/sec), we have 66x headroom before needing to consider partitioning or sharding.
4. **Exactly-once for billing**: Application-layer idempotency keys (e.g., `notification:{event_id}` in Redis with 24-hour TTL) combined with XACK prevents duplicate delivery.
5. **Retry infrastructure**: XPENDING exposes messages pending acknowledgment, enabling exponential backoff via XCLAIM with retry count tracking in message headers.
6. **WebSocket foundation**: Redis Pub/Sub or Streams can serve as the backbone for real-time push notifications within the 2-quarter window.
7. **Cost efficiency**: No additional managed service costs. Self-managed Redis on existing infrastructure or ElastiCache at modest tier.

### Negative Consequences

1. **Scaling ceiling**: Redis Streams scales to ~500K events/sec on a single instance. Beyond 10x growth (50K req/s), sharding or migration to Kafka becomes necessary.
2. **Exactly-once complexity**: True exactly-once requires application-layer dedup logic. Kafka provides this natively with EOS transactions; Redis requires careful implementation of idempotency keys.
3. **Message retention trade-offs**: Redis Streams retention is limited compared to Kafka. If notification processing stalls for days, messages may expire before retry completes (mitigated via MAXLEN ~ large value + separate pending stream).
4. **No native cross-datacenter replication**: Redis Streams replication is primary-replica based. Multi-region deployment requires Redis Cluster or external tooling. Kafka's mirror-making is more mature.
5. **Operational blind spots**: Unlike Kafka's mature ecosystem (Kafka Connect, Schema Registry, Cruise Control), Redis Streams lacks comprehensive monitoring tooling. Custom dashboards for stream lag, consumer lag, and pending counts require additional effort.
6. **Limited message replay**: Once messages are acknowledged (XACK), they are removed. For debugging/replay scenarios, a separate audit stream must be maintained manually.

## Alternatives Considered

### Apache Kafka (Rejected)

**Rejected理由:**

1. **Learning curve incompatibility**: No Kafka experience on a 6-person team means 2-4 engineers spending 3-6 months becoming proficient while maintaining current features. This exceeds the 2-week setup constraint by an order of magnitude.

2. **Operational expertise gap**: Production Kafka requires understanding of:
   - Partition count and replication factor sizing
   - Broker failure detection and recovery
   - Partition leadership rebalancing
   - Consumer group lag monitoring
   - JVM tuning for Kafka (if self-managed)

   Without a dedicated infrastructure engineer, operational incidents will consume senior engineer time disproportionately.

3. **Budget misalignment**: 
   - Self-managed Kafka: 3+ brokers minimum for HA, each with sufficient storage for message retention
   - Managed Confluent Cloud: Excellent product but pricing at 500K events/sec with 7-day retention exceeds modest budget
   - AWS MSK: More affordable but still requires cluster sizing expertise

4. **Overengineering for current scale**: Our peak throughput is ~500 req/s (likely 1,500 notification events/sec including emails/webhooks). Kafka's strengths (million/sec throughput, multi-day retention, sophisticated consumer groups) solve problems we do not yet have.

**Future reconsideration**: If traffic grows 50x beyond current projections, or if regulatory requirements mandate long-term message retention with audit trails, Kafka becomes the appropriate choice. At that point, the team will have grown or gained experience through other means.

### Alternative: AWS SQS/SNS (Not Evaluated)

SQS/SNS were considered but excluded from primary evaluation because:
- SQS offers standard queues (at-most-once) and FIFO queues (exactly-once at additional cost)
- FIFO throughput limited to 300 req/s per queue without batching
- Combined SQS + SNS pattern adds operational complexity (two services to monitor)
- Cost at scale (5,000 req/s × notification events) becomes significant

For the constraints given, Redis Streams provides better cost efficiency and operational simplicity.

## Summary

| Criteria | Redis Streams | Apache Kafka |
|----------|--------------|--------------|
| Setup time | 1-3 days | 2+ weeks |
| Team familiarity | High | None |
| Peak throughput (current) | 1,500 events/sec ✓ | 1,500 events/sec ✓ |
| 10x growth capacity | 15,000 events/sec ✓ | 15,000 events/sec ✓ |
| Exactly-once delivery | App-layer idempotency | Native EOS |
| Operational complexity | Low | High |
| Additional infrastructure | None | 3+ brokers |
| Budget impact | Minimal | Moderate-High |
| WebSocket readiness | Yes | Yes |

**Decision**: Implement Redis Streams for the notification subsystem. Leverage existing Redis expertise for rapid delivery within the 2-week constraint. Accept application-layer idempotency for exactly-once billing notifications. Design the consumer implementation with migration path to Kafka if scale exceeds 50x current projections.

---

*Document version: 1.0*  
*Created: 2026-04-21*  
*Decision owner: Engineering Team*
