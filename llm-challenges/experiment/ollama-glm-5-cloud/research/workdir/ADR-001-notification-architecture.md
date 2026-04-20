# ADR-001: Notification Subsystem Architecture

## Status

**Proposed**

## Context

Our SaaS project management platform (85,000 MAU, ~2M tasks/month, peak 500 req/s) handles notifications synchronously within the HTTP request cycle. This has caused:

1. **Request timeouts** — Average latency 800ms, spikes to 8s during peak hours as notifications block responses
2. **Silent failures** — No retry or dead-letter queue when email providers or webhook endpoints fail
3. **Cascading failures** — Two incidents this year where slow webhooks exhausted connection pools, taking down unrelated features
4. **No delivery guarantees** — Billing-critical notifications (trial expiry, payment failures) require exactly-once delivery

We need to decouple notifications from the request cycle with async processing that supports:
- Retry with exponential backoff
- At-least-once delivery for all notifications, exactly-once for billing events
- Real-time WebSocket push notifications within 2 quarters
- 10x traffic growth without re-architecting

**Constraints:**
- Engineering team: 6 people (3 senior, 3 mid-level), no dedicated infrastructure engineer
- Redis already in production for sessions and rate limiting
- No Kafka experience on the team
- Must deliver value within 2 weeks
- Modest budget — cannot afford managed Confluent Cloud at scale
- Exactly-once semantics required for billing notifications

## Decision

**We will use Redis Streams as the backbone for the notification subsystem.**

### Justification

| Factor | Redis Streams | Apache Kafka |
|--------|---------------|--------------|
| **Operational Complexity** | Low — leveraging existing Redis deployment | High — requires new cluster management, ZooKeeper/KRaft, monitoring |
| **Time to Value** | Days — team already knows Redis, client library familiar | Weeks to months — steep learning curve, no team experience |
| **Team Fit** | Excellent — minimal new operational burden | Poor — no dedicated infra engineer, no Kafka expertise |
| **Throughput** | Sufficient — 100K+ msg/sec easily handles 500 req/s peak with room for 10x growth | Overkill — designed for millions/sec, beyond our scale |
| **Message Retention** | Days-based (configurable) — sufficient for notification replay | Weeks to months — more than needed for our use case |
| **Consumer Groups** | Native consumer groups with `XGROUP` — supports parallel processing, offset management | Mature consumer groups — more sophisticated but unnecessary complexity |
| **Exactly-Once Semantics** | Achievable via idempotency keys + deterministic message IDs | Native support via idempotent producers + transactions |
| **Cost** | Zero marginal infra cost — reuse existing Redis | High — self-hosted requires dedicated ops time; managed services expensive |

**Key Technical Decision Points:**

1. **Throughput is NOT the deciding factor.** At 500 req/s peak with notification fan-out of ~3x, we need ~1,500 messages/sec. Redis Streams handles 100K+ easily. Kafka's millions/sec capacity is architectural overkill.

2. **Operational burden is the deciding factor.** A 6-person team with no infra engineer cannot maintain a Kafka cluster without significant risk. Redis Streams runs on infrastructure we already operate.

3. **Time-to-value constraint is binding.** Kafka would require weeks of learning, setup, and operational tuning before delivering producer/consumer code. Redis Streams delivers working async notification processing within the 2-week window.

4. **Exactly-once for billing is achievable.** Redis Streams supports exactly-once-through-idempotency: we will use deterministic message IDs (e.g., `billing:{tenant_id}:{event_id}`) and maintain a processed-events Redis set with TTL. Consumers check this set before processing and atomically mark as complete. This is the same pattern used by mature Redis-based queue systems.

## Consequences

### Pros

1. **Rapid deployment** — Production-ready async notifications achievable in 1-2 weeks vs. 4-8 weeks for Kafka
2. **Zero additional infrastructure** — Reuses existing Redis cluster; no new VMs, containers, or managed services
3. **Lower operational risk** — Team already understands Redis monitoring, backup, failover
4. **Adequate performance headroom** — 100x current throughput capacity; supports 10x growth easily
5. **Simpler debugging** — Single system to trace; familiar Redis CLI tools (`XREAD`, `XRANGE`, `XINFO`)
6. **Cost-efficient** — No Kafka license fees, no additional AWS resources, no managed service overhead
7. **Consumer group support** — Native `XGROUP` enables horizontal notification worker scaling without custom coordination logic

### Cons

1. **Memory-bound retention** — Redis Streams retain messages in memory; long retention periods increase memory pressure. We mitigate with sensible defaults (24-48 hour retention) and disk-backed persistence (AOF/RDB) for durability.
2. **No native exactly-once** — Requires application-level idempotency implementation (idempotency keys + processed-events set). This adds code complexity but is well-understood and auditable.
3. **Smaller ecosystem** — Fewer tooling options compared to Kafka (no equivalent to Kafka Connect, fewer monitoring dashboards). We accept this given our modest scale.
4. **Single point of failure risk** — Redis cluster dependency means Redis outage affects notifications. Mitigation: Redis Sentinel or cluster mode already provides HA for session storage; same for notifications.
5. **Long-term scaling ceiling** — If we exceed ~100x current scale (50,000+ req/s), Redis Streams may become a bottleneck requiring migration. This is outside the 10x growth target; revisit in 18-24 months if velocity exceeds projections.
6. **Persistence tuning required** — Default Redis async persistence (RDB snapshots) risks message loss on crash. We will enable AOF with `appendfsync everysec` for durability without extreme performance impact.

## Alternatives Considered

### Apache Kafka

**Why we rejected it:**

1. **Operational complexity mismatch** — Kafka requires cluster management, partition planning, consumer offset coordination, and dedicated monitoring. Our team has no infra engineer and no Kafka experience. This is a significant operational risk.

2. **Time-to-value violation** — Setting up Kafka (self-hosted or managed), learning the ecosystem, and achieving production deployment would take 4-8 weeks minimum. This violates the 2-week delivery requirement.

3. **Feature overkill** — Kafka's strengths (massive throughput, multi-topic stream processing, long-term event storage, Kafka Connect ecosystem) address problems we don't have. Our use case is straightforward: reliable async notification processing with retries.

4. **Cost structure** — Managed Kafka (Confluent Cloud, AWS MSK) is expensive at scale and exceeds budget. Self-hosted Kafka shifts operational burden to our small team without infra expertise.

5. **Learning curve tax** — Every team member would need Kafka literacy: client libraries, consumer group semantics, partition strategies, monitoring tools. This is ongoing cognitive overhead for a feature we could build faster with familiar technology.

**When Kafka would be the right choice:**

Kafka would be appropriate if we had: event sourcing requirements, multi-team data platform needs, 100x+ current throughput, dedicated infrastructure engineering, or long-term event replay (months/years). We have none of these.

## Next Steps

1. **Week 1:** Implement Redis Streams producer in Flask app for notification events
2. **Week 1-2:** Build notification worker service with consumer group, retry logic, exponential backoff
3. **Week 2:** Deploy to staging, validate delivery guarantees with integration tests
4. **Week 2:** Implement idempotency check for billing notifications (Redis SET with TTL)
5. **Post-launch:** Add dead-letter queue (separate Redis stream) for failed notifications requiring manual review
6. **Q+2:** Extend infrastructure for WebSocket push (same Redis Streams, new consumer type)

---

**Author:** Architecture Review  
**Date:** 2026-04-21