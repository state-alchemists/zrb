# ADR-001: Notification Subsystem Architecture

## Status

Proposed

## Context

Our SaaS project management platform currently handles notifications synchronously within the HTTP request cycle, causing severe operational issues:

- Average response latency of 800ms, spiking to 8s during peak hours (500 req/s)
- Silent notification failures with no retry mechanism or dead-letter queue
- Two incidents of cascading failures from slow webhook endpoints causing connection pool exhaustion
- No delivery guarantees for billing-critical notifications (trial expiration, payment failures)

**Scaling Requirements:**
- Decouple notification processing from HTTP request cycle
- Implement retry with exponential backoff
- Guarantee at-least-once delivery; exactly-once for billing events
- Support future real-time WebSocket push notifications
- Handle 10x traffic growth without re-architecting

**Team & Infrastructure Constraints:**
- Engineering team: 6 people (3 senior, 3 mid-level), no dedicated infrastructure engineer
- Existing Redis deployment in production (sessions, rate limiting)
- No Kafka experience on the team
- Maximum 2 weeks for setup and migration to deliver value
- Modest budget — cannot afford managed Confluent Cloud at scale

## Decision

We will use **Redis Streams** as the messaging backbone for the notification subsystem.

**Justification:**

| Criterion | Redis Streams | Apache Kafka |
|-----------|--------------|--------------|
| **Operational complexity** | Low — already production-proven, single-node operation | High — requires ZooKeeper/KRaft cluster, broker tuning, partition management |
| **Team readiness** | Immediate — 0 learning curve for existing Redis users | Significant ramp-up — 2-4 weeks just for basic proficiency |
| **Setup time** | 1-2 days — consumer groups via `XREADGROUP` | 2+ weeks — cluster provisioning, producer/consumer config, monitoring |
| **Infrastructure cost** | $0 marginal — leverage existing Redis | $500-2000/mo — 3-node minimum or managed service |
| **Exactly-once semantics** | Achievable via `XACK` + idempotent consumers | Native (idempotent producers + transactions) |
| **Peak throughput (current)** | 50K-100K msgs/sec — sufficient for 500 req/s × 10x growth | 1M+ msgs/sec — overkill for current needs |
| **Message retention** | Memory-constrained; configurable persistence | Persistent by design; infinite retention |
| **Consumer groups** | Native support via `XREADGROUP`/`XACK`/`XPENDING` | Mature, battle-tested rebalance protocol |

**Critical Decision Factors:**

1. **Time-to-value constraint (2 weeks):** Redis Streams can be production-ready in days using existing infrastructure and team knowledge. Kafka requires cluster provisioning, security configuration, and operational runbooks — likely exceeding our deadline before delivering any business value.

2. **Exactly-once for billing:** While Kafka offers superior exactly-once semantics, we can achieve the same guarantees with Redis Streams through:
   - Idempotent consumers (deduplication via notification UUID)
   - Atomic `XREADGROUP` → process → `XACK` workflow
   - Pending entry list (`XPENDING`) monitoring for stuck messages
   - Consumer group rebalancing via `XCLAIM` for failed nodes

3. **Team size and expertise:** With 6 engineers and no dedicated infrastructure role, we cannot afford the operational burden of Kafka cluster maintenance (partition rebalancing, broker failures, ZooKeeper coordination). Redis operational patterns are already established.

4. **Growth headroom:** At 500 req/s peak with 10x growth (5K req/s) and typical notification volume of 2-5 messages per request, we project ~25K msgs/sec — well within Redis Streams' sustained throughput on modest hardware.

## Consequences

### Positive Consequences

1. **Rapid migration:** Production notifications will be async within 1 week, unblocking immediate latency and reliability improvements.

2. **Zero new infrastructure:** Uses existing Redis deployment; no new services to monitor, secure, or back up.

3. **Unified operational model:** Single Redis expertise domain for sessions, rate limiting, and messaging reduces cognitive load.

4. **Sufficient exactly-once guarantees:** Idempotent consumer pattern with `XACK` acknowledgment provides billing-grade delivery guarantees without external transaction coordination.

5. **Path to WebSocket:** Redis pub/sub integration for real-time features is well-documented and operationally trivial.

### Negative Consequences

1. **Durability ceiling:** Redis is memory-first; messages lost on catastrophic node failure before `fsync`. Mitigation: enable AOF persistence with `appendfsync everysec`, and treat Redis Streams as a short-term buffer (hours to days), not permanent event store.

2. **Scaling friction beyond 100K msgs/sec:** If growth exceeds projections, we may need to re-evaluate in 18-24 months. Mitigation: abstract the stream client behind an interface to allow future Kafka migration without application changes.

3. **Manual exactly-once implementation:** Must implement consumer-side deduplication and careful acknowledgment handling. Kafka's exactly-once is turnkey. Mitigation: unit test the consumer ack path exhaustively; monitor pending message counts.

4. **Limited replay capability:** No built-in log compaction or time-based replay across multiple consumer groups. Mitigation: write notification audit log to PostgreSQL for compliance debugging.

## Alternatives Considered

### Apache Kafka (Rejected)

**Why considered:** Superior durability, native exactly-once semantics, infinite retention, and consumer group rebalance protocol are industry standard for event streaming.

**Why rejected:**

1. **Operational burden exceeds team capacity:** Kafka requires dedicated operational expertise for partition leadership election, ISR management, and consumer lag monitoring. Our 6-person team with no infrastructure specialist would face a bus factor of 1 and on-call burden inconsistent with platform maturity.

2. **Deadlines impossible:** Even with managed services (MSK, Confluent), the learning curve and migration complexity would exceed our 2-week delivery window. Kafka's exactly-once benefits are moot if we cannot ship.

3. **Cost at scale:** Self-hosted Kafka requires minimum 3 broker nodes plus ZooKeeper (or KRaft) for production. At our modest budget, this steals resources from core product engineering.

4. **Over-optimization:** Kafka's 1M+ msg/sec throughput and durable log semantics solve problems we do not have today. We need reliable async delivery at 25K msgs/sec, not a distributed event sourcing platform.

**Trade-off accepted:** We sacrifice Kafka's operational elegance and long-term scalability for Redis' immediate deliverability and team fit, with an abstraction layer preserving migration optionality.

---

*Author: Architecture Team*  
*Date: 2026-05-18*
