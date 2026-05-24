# ADR-001: Notification Subsystem — Async Processing with Redis Streams

**Status:** Proposed

---

## Context

The Notifier subsystem runs synchronously inside the Flask HTTP request cycle, causing request timeouts (800ms avg, 8s peak), silent failures on downstream outages, and cascading connection-pool exhaustion. Billing-critical notifications require exactly-once delivery; no such guarantee exists today.

We must decouple notification dispatch from the request cycle within a **2-week setup window**, supporting:

- Async dispatch with retry and exponential backoff
- At-least-once delivery for billing events; exactly-once where feasible
- Real-time WebSocket push within two quarters
- 10x traffic growth (~5,000 req/s peak) without re-architecting

**Constraints that narrow the field:**
- Engineering team of 6, no dedicated infra engineer
- Existing Redis deployment (sessions, rate limiting) — no Kafka experience on staff
- Modest budget — managed Confluent Cloud is out of scope
- 2-week time-to-value cap

---

## Decision

**Adopt Redis Streams** as the notification message broker. Defer Kafka indefinitely.

### Architecture Sketch

```
┌─────────┐     ┌──────────────┐     ┌───────────────┐
│ Flask   │────>│  Redis       │────>│  Consumer     │────> Email/SMS/Webhook
│ Request │     │  Streams     │     │  Workers      │
│ Handler │     │ (notification│     │ (async, retry)│
└─────────┘     │  streams)    │     └───────────────┘
                └──────────────┘           │
                     │                     │ (XACK on success)
                     │               ┌─────▼─────────┐
                     │               │ Dead-Letter   │
                     └──────────────>│ Streams       │
                                     │ (after N retry)│
                                     └───────────────┘
```

- Each notifier type (email, webhook, in-app) gets its own stream for independent consumer-group scaling
- Workers run as separate processes (or background threads) reading via `XREADGROUP`
- `XACK` marks completion; failed deliveries re-enter via pending-entry list (`XPENDING` + `XCLAIM`)
- Billing events carry an idempotency key (deterministic hash of event type + entity ID + timestamp) stored in PostgreSQL with a unique constraint — this delivers **effectively-once** semantics from the consumer side

---

## Consequences

### Pros

1. **Zero new infrastructure.** Redis is already in production. No brokers to provision, no ZooKeeper/KRaft, no JVM to tune. The 2-week timeline is achievable.

2. **Team velocity preserved.** Every engineer knows Redis. The Streams API (`XADD`, `XREADGROUP`, `XACK`, `XCLAIM`) is learnable in hours. No Kafka learning curve, no partitioning strategy to design upfront.

3. **Sufficient throughput.** A single Redis instance handles 100k+ msg/s; our peak is 500 req/s today, 5,000 req/s at 10x. Not a bottleneck. If it someday becomes one, sharding by notification type across Redis nodes is straightforward.

4. **Consumer groups with tracking.** `XREADGROUP` gives at-least-once delivery by default. Pending entries survive consumer crashes and can be claimed by other workers.

5. **Dead-letter queues are trivial.** A separate stream + a reaper consumer that checks pending-entry age and `XDEL`/`XADD` to a DLQ stream after the retry budget is exhausted.

6. **WebSocket path is clear.** Use Redis Pub/Sub alongside Streams. The same Redis instance feeds both: Streams for durable dispatch, Pub/Sub for real-time push to WebSocket servers. Kafka would need a separate architecture for this.

7. **Cost: free.** No new AWS resources, no license, no managed-service premium.

### Cons

1. **No broker-level exactly-once.** Redis Streams guarantees at-least-once. Exactly-once must be built on the consumer side. **Mitigation:** Use deterministic idempotency keys with a unique constraint in PostgreSQL. This gives effectively-once delivery for billing — sufficient for audit compliance and simpler than Kafka's transaction API.

2. **Memory-bound retention.** Streams live in RAM (with optional persistence via AOF/RDB). Notifications are ephemeral (consumed in seconds); the retention risk is near-zero. **Mitigation:** Set `MAXLEN ~ 10,000` per stream to cap memory. DLQ entries can be archived to S3 if audit retention is required.

3. **No automatic partitioning.** A single stream on one Redis node is a throughput ceiling. **Mitigation:** At 5,000 req/s peak, we won't hit it. If we do, split into per-type streams (already planned) and add Redis replicas.

4. **No built-in stream processing.** Kafka Streams / ksqlDB provide SQL-like stream processing. We don't need it today — our workers are simple dispatch-and-retry. When we need event sourcing or analytics, we can add a proper event store.

---

## Alternatives Considered

### Apache Kafka (Rejected)

Kafka is the obvious alternative and the stronger technology on paper. We rejected it for these specific reasons:

| Property | Kafka | Redis Streams | Impact at Our Scale |
|---|---|---|---|
| Setup time | 2–4 weeks (ZK/KRaft + brokers + monitoring) | <1 week (config only) | **Kafka fails the 2-week constraint** |
| Team experience | Zero | Production daily | **6-month ramp vs. no ramp** |
| Throughput | Millions/s | 100k+/s | Both vastly exceed 5k/s peak |
| Exactly-once | Native (EOS) | Consumer-side idempotency | **Both solve it; Kafka's is heavier** |
| Operational cost | Self-host: EC2 + EBS + monitoring; MSK: $200+/mo | $0 (existing Redis) | **Kafka is real cost; Redis is free** |
| WebSocket push | Requires separate infra | Pub/Sub on same Redis | **Redis Streams simpler path** |

Kafka's superior partitioning, disk-based retention, and native exactly-once are real advantages — but they address problems we do not have at our current or projected scale. The cost of Kafka is paid upfront (setup time, learning curve, operational burden, infrastructure cost), while its benefits kick in at a scale (`>100k msg/s`, multi-team consumers, long-term event sourcing) we may never reach.

For a 6-person team with no Kafka experience and a 2-week delivery deadline, adopting Kafka would be prioritising theoretical scalability over practical delivery.

---

## Recommendation

Adopt Redis Streams now. The decision is reversible: if we outgrow it, the stream abstraction is clean enough to swap the transport layer behind a common interface. But at our scale and with our constraints, Redis Streams delivers every requirement with a fraction of the operational cost.

**The 80% solution that ships in 1 week beats the 95% solution that ships in 4 months.**

---

*Authors: Engineering Team*
*Last updated: 2026-05-24*
