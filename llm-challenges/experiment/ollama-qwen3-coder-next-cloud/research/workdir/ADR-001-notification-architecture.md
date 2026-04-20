# ADR-001: Notification Subsystem Architecture

**Status:** Proposed

## Context

The notifications subsystem currently operates synchronously within the HTTP request cycle, causing three critical issues:

1. **Request latency degradation**: 800ms average, spiking to 8s at peak, directly damaging user experience
2. **Reliability failures**: Silent drops during provider outages, no retry mechanism
3. **Cascading failure risk**: Two incidents this year where slow webhook endpoints exhausted connection pools, affecting unrelated features

We require a message queue that enables async processing with:
- At-least-once delivery for all notifications
- Exactly-once semantics for billing-critical events
- Exponential backoff retry without custom code
- Real-time WebSocket support within 6 months
- 10x scalability headroom (current burst: 500 req/s → target 5,000 events/s)

Team constraints matter: 6 engineers (3 senior, 3 mid), no Kafka expertise, no dedicated infra engineer, and must be operational within 2 weeks.

## Decision

**Adopt Redis Streams with consumer groups.**

**Justification:** Redis Streams delivers the right balance of capabilities and operational simplicity for our constraints:

1. **Exactly-once semantics via consumer groups + idempotent processing** — Consumer groups maintain offset state. Each worker can process messages idempotently (e.g., dedupe on billing_event_id), achieving exactly-once behavior for critical paths. We already use Redis for rate limiting and sessions, reducing operational surface.

2. **Sufficient throughput for our scale** — Redis Streams handles ~50,000+ messages/second on a single instance ([Redis Labs benchmarks](https://redis.com/blog/redis-streams-performance/)). Our peak is 500 req/s → ~5,000 notification events/s after 10x growth, well below capacity. Kafka would be overkill for this throughput.

3. **Faster time-to-value (1-2 weeks vs 4-6 weeks)** — Redis Streams requires no new service deployment. We configure streams, update producers to push to Redis, and deploy worker consumers. Kafka would require operator training, cluster provisioning (EC2 or EKS setup), broker configuration, znode management, and schema registry consideration. Given zero Kafka experience on the team, this adds significant risk and delay.

4. **Native retry with backoff via Lua scripting** — We can implement exponential backoff directly in Redis using a sorted set (ZRANGE for scheduled messages, ZADD with timestamp score). This avoids the complexity of Kafka's retry topic patterns while remaining simpler than building consumer-group-level retry logic.

5. **Gateway to WebSocket push** — Redis Pub/Sub works alongside Streams for real-time notifications, enabling WebSocket servers to subscribe to live events. Kafka would require additional infrastructure to bridge to WebSockets.

## Consequences

| Pros | Cons |
|------|------|
| ✅ Leverages existing Redis infrastructure (no new service) | ⚠️ Streams don't natively support exactly-once; idempotency must be enforced at consumer level |
| ✅ 1-2 week deployment timeline (team can own) | ⚠️ Persistence is disk-based but durability guarantees weaker than Kafka (for rare failure scenarios— acceptable given retry + idempotency) |
| ✅ Simple Python client (redis-py) with low learning curve | ⚠️ No built-in dead-letter queue; must implement via second stream or external store |
| ✅ Consumer groups provide parallel processing with load balancing | ⚠️ No cross-data-center replication (we run single AWS region currently, acceptable) |
| ✅ Low operational overhead (no broker scaling, no zookeeper) | ⚠️ Memory usage grows if consumers fall behind (monitoring needed) |

## Alternatives Considered

### Apache Kafka

Why rejected:

- **Operational complexity mismatch**: Kafka requires 4-6 weeks of infrastructure setup and team training. With no Kafka experience, we would need external consultants or significant engineering time, risking the 2-week constraint. Kafka's strengths (high durability, multi-region replication, partition scaling) are unnecessary for our 5k events/s workload.

- **Provisioning overhead**: Kafka on AWS would require either EKS-based deployment (complex) or Confluent Cloud (budget concern—$150+/month at low volume, scaling to $1k+/month as we grow). Redis is already paid for in our AWS Elasticache plan.

- **Over-engineering risk**: Kafka's exactly-once semantics require consumer-side offset management + idempotent producers + transactions, a complex pattern for a mid-sized team. Redis consumer groups + idempotent consumers provide 95% of the benefit with 10% of the code.

- **Timing mismatch**: Kafka would delay delivery by 3–4 weeks, extending the current degradation period during which we experience billing notification failures.

Redis Streams is the optimal choice given our throughput needs, team skill mix, and time-to-value constraint. It provides sufficient reliability for billing-critical events while enabling rapid iteration.

## Implementation Checklist

- [ ] Create Redis Streams (`notifications:billing`, `notifications:standard`)
- [ ] Add idempotency check (Redis SETNX) in notification worker before processing
- [ ] Implement retry stream with timestamp-scored sorted set for exponential backoff
- [ ] Deploy notification worker as separate service (2–3 days)
- [ ] Update backend to push notifications instead of sending synchronously (1 day)
- [ ] Wire Redis Streams to existing email/webhook handlers (2 days)
- [ ] Monitor: consumer lag, retry rate, dead-letter queue size

---

*Last modified: 2026-04-21*