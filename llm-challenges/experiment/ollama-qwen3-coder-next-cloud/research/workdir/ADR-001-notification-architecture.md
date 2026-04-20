# ADR-001: Notification Subsystem Architecture — Redis Streams vs Apache Kafka

**Status:** Proposed  
**Date:** 2026-04-20  
**Author:** Architecture Team

---

## Context

The current synchronous notification system causes:

1. **Request timeouts** (800ms avg, up to 8s during peak) due to blocking email/webhook sends
2. **Silent failures** with no retry logic or dead-letter storage
3. **Cascading failures** from slow webhook endpoints exhausting connection pools
4. **No delivery guarantees** — billing-critical notifications lack exactly-once semantics

Current load: ~2M notifications/month (~667/hour avg; ~500 req/s spikes). Scaling target: 10x growth.

**Key requirements:**
- Async decoupling from HTTP request cycle
- Retry with exponential backoff
- At-least-once delivery for all, exactly-once for billing events
- Real-time WebSocket capability within 2 quarters
- Operational complexity must fit 6-engineer team (no infra specialist)

---

## Decision

**Choose Redis Streams.**

### Justification

| Factor | Redis Streams | Apache Kafka |
|--------|---------------|--------------|
| **Operational Complexity** | Zero-new-infrastructure — integrates into existing Redis deployment. No cluster setup, no schema evolution, no connector management. | Requires dedicated Kafka cluster (3+ brokers minimum for HA), ZK or KRaft coordination, topic management, replica configuration. Needs dedicated monitoring. |
| **Team Experience** | Redis is already in production for sessions/rate limiting — team has production knowledge. | Zero Kafka experience on team. Learning curve + operational risk during critical migration. |
| **Setup Time** | Implementation: 3–5 days. Migration: can be rolled out incrementally via dual-write during transition (~1 week). Total ≤2 weeks. | Provisioning, config, testing, team onboarding: 3–4 weeks minimum before first production deployment. |
| **Throughput** | Sustained 100k+ messages/sec per node. With our 667 msg/hr baseline → ~0.19 msg/s avg, **>500x headroom** for 10x growth. | Kafka can handle millions of msg/sec — overprovisioned for current needs. |
| **Delivery Guarantees** | Supports exactly-once via `XADD + MULTI/EXEC` with idempotent consumer processing (idempotent key per event). Consumer offset management + deduplication (e.g., event_id + consumer_group) provides the necessary semantics. | Kafka has built-in exactly-once semantics (EOS) via transactional producers + consumer configuration, but requires careful configuration and increases latency. |
| **Billing Exactness** | Achievable with idempotent consumer logic (store processed event_ids in PostgreSQL, e.g., `notifications_delivered` table). Idempotent idempotency keys (e.g., `event_type:object_id:timestamp`) prevent duplicates. | Kafka EOS is robust but overkill — the same deduplication pattern works more simply with Redis. |
| **Real-time WebSocket Support** | Redis Pub/Sub can coexist with Streams for WebSocket broadcasting. Use a lightweight pub/sub publisher + Stream consumer to bridge. | Kafka Connect or KStreams needed — additional moving parts. |
| **Budget** | Zero additional infrastructure cost — already paid for Redis. | Self-managed: $150–300/mo for 3-broker AWS setup. Managed (Confluent): $1,500+/mo at current scale — unaffordable under constraints. |

---

## Consequences

### Pros
- **Rapid delivery** — implementation in <2 weeks, minimal risk
- **Operational simplicity** — one less infra stack to maintain; existing Redis monitoring/backup apply
- **Sufficient scalability** — 10x growth (6,600 msg/hr → ~2 hr peak) remains well within Redis Streams capacity
- **Simpler debugging** — `redis-cli`, `redis-graphie`, and application logs provide full traceability
- **Gradual migration** — can dual-write to Redis + existing system during transition, then rip out old code

### Cons
- **No native tiered storage** — Redis memory-backed; messages must be purged after retention window (e.g., 7–30 days), whereas Kafka can retain years on disk. Mitigation: keep only billing retention period + buffer; archive to S3 if needed (rare; billing events are transient).
- **Single-point-of-failure risk** — but Redis is already HA (ElastiCache cluster with multi-AZ) — same reliability SLA as today.
- **Limited replay capability** — can’t rewind years of data Like Kafka’s retention policies. Acceptable: current SLA requires billing notifications for 90 days; Redis can retain this duration with `MAXMEMORY-policy allkeys-lru + persistence`.

---

## Alternatives Considered

### Apache Kafka — Rejected

**Why not Kafka:**
1. **Team bandwidth mismatch** — No Kafka experience on a 6-person team (no infra specialist). Kafka setup, tuning, and failure recovery requires expertise we don’t have today.
2. **Timeline misalignment** — Kafka rollout would consume >2 months of engineering effort (onboarding, staging, migration, testing). ADR goal: deliver value in ≤2 weeks.
3. **Over-engineering** — Throughput and durability guarantees exceed current need (667 msg/hr). Kafka’s strengths shine at 10k+ msg/s; we’re three orders of magnitude below that.
4. **Cost** — Managed Kafka (Confluent) is financially prohibitive (~$1.5k/mo minimum); self-managed introduces unsupportable operational risk.

Kafka remains viable for future re-evaluation when:
- Traffic reaches 1k+ msg/hr sustained
- Team has dedicated infra engineer or Kafka proficiency
- Budget allows for managed service or 24/7 on-call

### Other Options (Briefly)
- **RabbitMQ**: More operational overhead than Redis, same throughput — no advantage.
- **SNS/SQS (AWS)**: Adds cost ($0.50/mo per 1M requests + data transfer), lock-in, and still requires consumer infrastructure — no simplification.
- **Database Jobs Table**: Already considered and rejected — poor concurrency, no efficient consumer groups, locking contention at scale.

---

## Implementation Plan (Next Steps)

1. **Week 1**
   - Provision Redis Streams (use existing ElastiCache cluster; enable AOF for persistence)
   - Create producer library (`notify_producer.py`) with retry logic and idempotent event IDs
   - Add event store table in PostgreSQL (`notifications_events`) for deduplication
2. **Week 2**
   - Implement consumer worker (`notify_consumer.py`) with exponential backoff, max retries, dead-letter stream
   - Dual-write: enqueue to Redis Streams + retain in DB during transition
   - Deploy with feature flag, monitor latencies/consumer lag
3. **Week 3**
   - Gradually shift traffic, decommission old synchronous notifications code
   - Enable WebSocket bridge via Redis Pub/Sub for real-time push target

---

## Rollback Plan

If Redis Streams integration fails:
- Keep old synchronous code + dual-write
- Disable Redis producer via feature flag (`NOTIFY_STREAM_ENABLED=false`)
- Replay pending events from PostgreSQL `notifications_events` table (maintained during transition)

---

## References

- Redis Streams docs: https://redis.io/docs/latest/develop/data-types/streams/
- Exactly-once semantics pattern: https://redis.io/docs/latest/develop/interact/transactions/
- Kafka vs Redis use cases: https://developer.redis.com/use-cases/streaming-iot/redis-streams-vs-kafka/
