# ADR-001: Notification Subsystem Architecture

## Status

**Proposed**

## Context

Our notification subsystem currently processes emails and webhooks synchronously within the HTTP request cycle. This has caused request timeouts (800ms average, 8s spikes during peak), silent failures with no retry mechanism, cascading failures from slow webhook endpoints, and no delivery guarantees for billing-critical events.

We must decouple notifications from the HTTP request cycle, support retry with exponential backoff, guarantee at-least-once delivery (exactly-once for billing events), and support future real-time WebSocket push notifications. The solution must handle 10x traffic growth without re-architecting.

### Constraints

- **Team**: 6 engineers (3 senior, 3 mid-level), no dedicated infrastructure engineer
- **Existing infrastructure**: Redis already in production (sessions, rate limiting)
- **No Kafka experience** on the team today
- **Deadline**: Maximum 2 weeks setup/migration before delivering value
- **Budget**: Modest; cannot afford managed Confluent Cloud at scale
- **Critical requirement**: Exactly-once semantics for billing notifications

## Decision

**We will use Redis Streams** as the message bus for our notification subsystem.

### Justification

Redis Streams is the optimal choice given our constraints, even though Kafka is technically superior for large-scale streaming. The deciding factors are operational fit with our small team, existing expertise, and strict timeline—not raw throughput capabilities.

**Redis Streams satisfies our technical requirements:**

| Requirement | Redis Streams Capability |
|-------------|--------------------------|
| **Decoupled processing** | Producer/consumer pattern via `XADD`/`XREADGROUP` |
| **Message ordering** | Per-stream ordering guarantees (sufficient for our scale) |
| **Consumer groups** | Built-in with automatic load balancing and failover |
| **Retry with backoff** | `XPENDING`/`XCLAIM` enable dead-letter patterns; implement exponential backoff in consumer |
| **At-least-once delivery** | ACK-based consumption with pending entry list tracking |
| **Exactly-once for billing** | Achievable via idempotent consumers + Redis Stream offsets (store processed billing event IDs in PostgreSQL) |
| **Message retention** | `XTRIM` or `MAXLEN` policies; we can retain 30 days per stream |
| **Real-time WebSocket (future)** | Redis Pub/Sub or blocking `XREAD` for push notifications |

**Critical operational advantages:**

1. **Zero new infrastructure**: We already run Redis for sessions and rate limiting. Adding Streams uses existing capacity—no new clusters to provision, monitor, or maintain.

2. **Team expertise**: All engineers understand Redis data structures. Learning curve is minimal versus Kafka's ZooKeeper/KRaft, partitions, rebalancing, and consumer group protocols.

3. **Meets our throughput needs**: At 500 req/s peak with 10x growth (5,000 req/s), Redis Streams handles this comfortably. A single Redis instance can process 100k+ messages/sec. Our bottleneck will be webhook/email latency, not the message bus.

4. **2-week feasibility**: Migration involves:
   - Week 1: Create Streams, implement producer, build consumer framework
   - Week 2: Migrate billing notifications first (highest value), add DLQ logic
   - Compare: Kafka would require cluster setup, topic design, consumer group tuning, and operational runbook development—optimistically 4-6 weeks.

5. **Cost**: Uses existing Redis infrastructure. No additional managed service costs versus Confluent/MSK (~$500-2000/month at scale).

6. **Exactly-once billing solution**: We'll implement idempotency keys at the application layer:
   - Producer: Include `billing_event_id` (UUIDv7) in message payload
   - Consumer: Store processed `billing_event_id` in PostgreSQL with unique constraint
   - Before processing: Check if event already handled; skip if found
   - This pattern works regardless of transport (Redis or Kafka) due to our small scale.

## Consequences

### Pros

- **Fastest path to value**: 2-week migration versus 6+ weeks for Kafka
- **No operational burden**: Single Redis instance already understood and monitored
- **Cost-effective**: Zero incremental infrastructure cost
- **Sufficient for scale**: 5,000 req/s is well within Redis Streams capacity
- **Simpler mental model**: Team can reason about streams immediately; no distributed systems expertise required
- **Easy local development**: No Docker Compose orchestration for Kafka/Zookeeper
- **`redis-py` ecosystem**: Mature Python client with Stream support built in
- **Future WebSocket integration**: Can leverage existing Redis Pub/Sub for real-time push

### Cons

- **Durability trade-off**: Redis is in-memory with optional AOF persistence; Kafka's log-based storage is more durable. **Mitigation**: Enable AOF with `appendfsync everysec`; accept small window of loss (acceptable for non-billing events).

- **No infinite retention**: Streams require explicit trimming; cannot retain forever like Kafka. **Mitigation**: 30-day retention suits our retry windows; archive to S3 if needed for audit.

- **Limited consumer group flexibility**: Fixed consumer group semantics; cannot dynamically reassign partitions like Kafka. **Mitigation**: Our consumer count is small (4 web servers); static assignment acceptable.

- **No native exactly-once semantics**: Must implement idempotency at application layer. **Mitigation**: Required anyway for webhook/email providers; adds minimal complexity (single lookup table).

- **Manual scaling**: Vertical scaling only unless we adopt Redis Cluster. **Mitigation**: Our 10x growth target fits single-instance vertical scaling; Redis Cluster migration is future-work if we exceed that.

## Alternatives Considered

### Apache Kafka (Rejected)

**Technical strengths:**
- Superior durability (replicated log storage)
- Infinite retention policies
- Industry-standard for high-throughput streaming
- Native consumer rebalancing and partition assignment
- Strong ecosystem (Kafka Connect, Schema Registry)
- Exactly-once semantics via idempotent producers and transactions

**Why rejected:**

1. **Operational overhead**: Running self-managed Kafka requires 3+ brokers, ZooKeeper or KRaft quorum, partition management, and careful tuning. With no infrastructure engineer, our 6-person team cannot support this responsibly.

2. **Learning curve**: Zero team experience means 4-6+ weeks to production including educational overhead, operational runbook development, and incident response preparation.

3. **Cost at scale**: Managed options (Confluent Cloud, MSK) exceed our modest budget. Self-managed requires additional EC2 instances.

4. **Over-provisioned for needs**: Kafka excels at 100k+ msg/sec with complex stream processing. Our 5k req/s target is 20x below Kafka's sweet spot. We would carry operational complexity without utilizing its strengths.

5. **Timeline mismatch**: The 2-week constraint makes Kafka impossible. We cannot deliver value in time.

**Conclusion**: Kafka is the "right" architectural choice for a streaming platform at scale, but the wrong choice for a small team with time constraints and modest throughput needs. The operational tax outweighs the technical benefits.

---

**Author:** Architecture Review Board  
**Date:** 2026-05-17  
**Supersedes:** N/A
