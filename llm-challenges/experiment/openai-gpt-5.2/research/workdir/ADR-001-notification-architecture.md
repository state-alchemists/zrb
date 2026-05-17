Title
Decouple Notification Delivery via Redis Streams + PostgreSQL Outbox

Status
Proposed

Context — the problem and constraints
We currently send emails and webhooks synchronously inside the Flask request cycle. At peak (~500 req/s), this causes high tail latency (spikes to 8s) and timeouts, and webhook slowness has exhausted shared connection pools, taking down unrelated features. Failures are silently dropped with no retries or dead-lettering.

We need an asynchronous notification subsystem that:
- Decouples notification processing from HTTP request handling.
- Supports retries with exponential backoff and a dead-letter path.
- Provides at-least-once delivery for most notifications.
- Maintains exactly-once semantics for billing-critical notifications (“payment failed”, “trial expired”) where feasible.
- Can grow ~10x without another re-architecture and can support near-real-time fanout for WebSocket push within 2 quarters.

Constraints:
- Team of 6 (no dedicated infra engineer).
- Redis already runs in production; Kafka is not currently in use.
- No Kafka experience on the team.
- Must deliver value within ~2 weeks of setup/migration.
- Modest budget; cannot rely on Confluent Cloud at full scale.

Decision — which option you choose and a clear justification
Choose Redis Streams (with consumer groups) as the notification event backbone, combined with a PostgreSQL outbox + idempotent consumers for billing-critical “exactly once” effects.

Justification:
- Fastest path to value under the 2-week constraint: Redis is already deployed and operated by the team; Redis Streams requires incremental configuration rather than standing up a new distributed log stack.
- Operational complexity: Kafka introduces a larger operational surface area (brokers, controllers, partitions, rebalancing, monitoring, upgrades, capacity planning) that is risky for a small team without Kafka experience and no infra specialist—especially without managed Kafka budget.
- Throughput and latency fit: Redis Streams can handle high throughput at low latency for this workload (notifications/webhooks/email fanout), and scaling 10x from today’s volume is feasible by sharding streams by notification type/tenant and adding consumer instances.
- Ordering guarantees match the domain: per-stream ordering is preserved; we can partition streams (e.g., by project/tenant or notification key) to maintain ordering where it matters (e.g., per user or per subscription).
- Consumer groups provide horizontal scaling: Redis Streams consumer groups allow multiple workers to share a stream with at-least-once processing semantics and pending entry tracking for redelivery.
- Exactly-once semantics: neither Redis Streams nor Kafka guarantees end-to-end exactly-once delivery to external side effects (email/webhook providers). We will meet the “exactly once” business requirement for billing notifications by implementing:
  1) a PostgreSQL outbox transactionally written with the billing state change, and
  2) idempotency keys + deduplication in the notification processor (e.g., unique constraint on notification_id / billing_event_id).
  This yields exactly-once effects (no double emails/webhooks) even under retries, crashes, or redeliveries.

Consequences — pros AND cons of your decision
Pros:
- Low setup and migration time: leverages existing Redis; minimal new infrastructure.
- Lower operational burden than Kafka: fewer moving parts; easier on-call for a 6-person team.
- Good fit for async workers: consumer groups + pending entries enable reliable at-least-once processing with worker failover.
- Real-time capability: Redis’ low latency supports future WebSocket push fanout (workers can publish to WS gateway or per-user channels).
- Cost-effective: avoids the immediate need for a managed Kafka offering.

Cons:
- Retention and replay are weaker than Kafka’s log model: Streams can retain entries, but long-term retention and multi-day replay at scale increase Redis memory cost; large backfills are less ergonomic than Kafka.
- Exactly-once is not native: requires careful outbox + idempotency design and discipline in every consumer that triggers external effects.
- Stream scaling requires planning: Redis Streams scale vertically and via sharding (multiple streams / Redis Cluster), but the scaling story is less standardized than Kafka for very large event pipelines.
- Operational risk to Redis: Redis is already critical (sessions/rate limiting). Increasing load and memory pressure for streams must be isolated (dedicated Redis instance/cluster) to avoid impacting existing uses.

Alternatives Considered — why you rejected the other option
Apache Kafka
Rejected for now due to mismatch with current team and constraints:
- Operational complexity and expertise gap: self-managing Kafka on AWS without a dedicated infra engineer and without Kafka experience is high risk for reliability and delivery timeline.
- Setup/migration timeline: standing up Kafka (or MSK), defining topics/partitions, client libraries, observability, and runbooks is unlikely to fit the “<2 weeks to value” constraint.
- Budget constraint: a fully managed offering that reduces operational burden (e.g., Confluent Cloud at scale) is not currently affordable; MSK reduces some toil but still requires significant operational maturity.
- Exactly-once semantics are not a silver bullet: Kafka’s exactly-once semantics primarily apply to Kafka-to-Kafka processing with transactional producers/consumers; once we trigger external side effects (email/webhooks), we still need idempotency/outbox patterns. Given we must build that anyway, Kafka’s incremental benefit doesn’t justify its cost and complexity today.

