# ADR-001 — Notification Subsystem: Choose Redis Streams over Apache Kafka

- **Status**: Proposed
- **Date**: 2026-05-17

## Context

The current notification pipeline is synchronous, causing request latency spikes (800 ms average, up to 8 s), silent failures on provider outages, cascading failures via connection pool exhaustion, and no delivery guarantees for billing-critical events. The team must decouple notifications while satisfying:

- At-least-once delivery (all events), exactly-once for billing events
- Retry with exponential backoff and dead-letter handling
- Support 10× growth from current ~500 req/s peak
- 85,000 MAU, ~2M notifications/month (~700/day, ~25,000/month after growth)
- Team constraints: 6 engineers (no Kafka experience), no dedicated infra engineer
- Budget: modest; cannot afford managed Kafka (Confluent Cloud)
- Operational cap: ≤2 weeks setup/migration

## Decision

We will adopt **Redis Streams** as the notification backbone.

## Rationale

Redis Streams satisfies all non-negotiable requirements with significantly lower operational and cognitive overhead for this team and scale:

| Requirement | Redis Streams support | Kafka comparison |
|-------------|----------------------|------------------|
| **Throughput** | 100K+ ops/s on a single node (our peak ~500 req/s, growth to ~5K req/s is trivial) | Overkill; even minimal Kafka cluster far exceeds current needs |
| **Exactly-once semantics** | Supported via `XGROUP` + `XREADGROUP` + client-side idempotency; simpler than Kafka's transactional producer because our workloads are already idempotent (idempotent billing APIs, idempotent email sends) | Requires transactional producer + consumer group coordination; more complex failure scenarios |
| **Consumer groups / retry** | `XREADGROUP` with `GROUP` + `PEEK` mode + `XACK` gives built-in retry semantics; missed messages can be reprocessed with `XCLAIM` after timeout | Requires custom retry logic or sidecar (e.g., KafkaDLQ); more moving parts |
| **Message retention** | `MAXLEN ~` option; can retain 30+ days for reprocessing without extra cost | Requires topic-level `retention.ms`; default retention adds storage cost |
| **Operational complexity** | We already run Redis; one `redis-cli` command to create streams/groups | New cluster, monitors, alerts, backup策略 and team training required |

**Operational leverage**: With Redis already in production for sessions/rate limiting, the new streams integrate into existing monitoring, logging, and backup policies. No new network security groups, IAM roles, or scaling policies needed. A Redis stream setup (create stream, create consumer group, configure consumer) can be scripted and deployed in <4 hours—well under the 2-week constraint.

**Team risk**: The 3 mid-level engineers can learn Redis Streams API in <1 day of hands-on work versus 1–2 weeks to grok Kafka concepts (partitions, replicas, controller quorum, ISR shrinkage, etc.) and debug production incidents without infrastructure support.

## Alternatives Considered

**Apache Kafka**
- *Rejected*: offers higher throughput and more mature ecosystem but is overengineered for our current scale (25K notifications/month → ~1K/day → ~0.015 msg/s baseline, peaks ~5 msg/s). Kafka's operational maturity does not offset its steep learning curve and ongoing maintenance overhead for a 6-person team with no Kafka expertise. The extra complexity (partition assignment, consumer rebalancing, log compaction tuning) creates unnecessary failure modes when we need reliability delivered by simplicity. If next-quarter user growth exceeds 5× current MAU (reaching high millions), this decision is revisitable.

**RabbitMQ / Celery queues**
- *Rejected*: still introduces a new messaging node (additional infra), offers no advantage in exactly-once semantics or Redis integration, and Celery's Python focus would duplicate existing Flask tasks without reducing code path length.

## Consequences

- **Positive**:
  - Same operational stack (Redis) eliminates onboarding time and reduces deployment risk.
  - Built-in exactly-once via idempotent APIs + `XACK` is simpler than Kafka's transactional producer setup.
  - `XCLAIM` enables dead-letter processing without external tooling.
  - Low barrier to adoption: engineers can prototype a consumer in <2 hours using `redis-py`.

- **Negative**:
  - Throughput ceiling: Redis Streams on a single node maxes around 100K ops/s; this is **not** a constraint today (our projected peak is ~5 msg/s) but would require revisiting if MAU grows 50×.
  - No built-in replication across regions (we currently run a single PostgreSQL region); if multi-region latency becomes critical, consider Redis Cluster or Redis Cloud Streams.
  - Limited ecosystem for connectors vs Kafka (but email/webhook integrations are simple Python producers/consumers).

- **Follow-ups**:
  1. Implement producer: enqueue notification messages with `XADD notifications_stream * event_type=<type> payload=<json>`.
  2. Create consumer group: `XGROUP CREATE notifications_stream notification-consumer-group $`.  
  3. Deploy Python worker using `redis-py` with `XREADGROUP GROUP notification-consumer-group CONSUMER <hostname> COUNT 10 BLOCK 5000 STREAMS notifications_stream >` loop.
  4. Add `XCLAIM`-based retry after 5-minute `PEEK` timeout and dead-letter queue (`XADD notifications_dlq * original_id=<id> error=<msg>`) after 3 retries.
  5. Instrument `XLEN notifications_stream` and `XINFO STREAM notifications_stream Consumer Groups` in existing Redis monitoring.
