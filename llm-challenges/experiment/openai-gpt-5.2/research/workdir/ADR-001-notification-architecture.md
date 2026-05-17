Title
Notification Subsystem Event Bus: Redis Streams vs Apache Kafka

Status
Proposed

Context — the problem and constraints
We need to move notification delivery (email, webhooks, and upcoming WebSocket pushes) out of the synchronous HTTP request cycle in a Python/Flask monolith. Current synchronous delivery causes request timeouts (800ms average, spikes to 8s), silent drops when downstream providers are unhealthy, and cascading failures (slow webhooks exhausting connection pools). We must add retries with exponential backoff, introduce observability/operational controls (e.g., dead-lettering), and support 10x traffic growth without another major re-architecture.

Key constraints:
- Team size is 6 with no dedicated infrastructure engineer.
- Redis is already running in production; Kafka is not.
- No Kafka experience on the team.
- We must deliver value within 2 weeks of setup/migration.
- Budget is modest; full-scale managed Kafka (e.g., Confluent Cloud) is not currently affordable.
- Billing-critical notifications must maintain exactly-once semantics (or the closest feasible practical equivalent), and other notifications need at-least-once delivery.

The decision is specifically between:
1) Apache Kafka
2) Redis Streams

Decision — which option you choose and a clear justification
Choose Redis Streams for the notification subsystem event bus.

Justification:
- Time-to-value and operational fit: Redis is already in production and understood by the team. Redis Streams can be introduced with minimal new infrastructure (reuse existing Redis cluster/instance, with capacity planning) and a small operational surface area. This aligns with the “<2 weeks to deliver value” constraint and the lack of a dedicated infra engineer.
- Consumer groups and ordering: Redis Streams provide consumer groups with pending entry lists (PEL) and explicit acknowledgements, enabling at-least-once delivery and backpressure control. Ordering is preserved within a stream by stream ID; for notifications this is typically sufficient when we model streams per aggregate (e.g., per workspace/tenant or per event type) or accept global ordering not being required.
- Retention: Streams support trimming (MAXLEN) and time-based eviction patterns at the application level, enabling bounded retention appropriate for notifications (where we generally need hours-to-days, not months). Kafka’s long retention and replay features are powerful but not essential for this subsystem’s primary goals.
- Throughput scalability relative to needs: With current peak ~500 req/s and a 10x target (~5,000 req/s), Redis Streams can handle this scale on appropriately sized infrastructure (and can be sharded by stream key / tenant). Kafka can handle far higher throughput, but that headroom comes with significant operational complexity.
- Exactly-once semantics: Neither Kafka nor Redis Streams can guarantee true end-to-end exactly-once delivery to external side effects (email providers, webhook endpoints) without idempotency at the consumer and a durable deduplication strategy. Kafka offers stronger tooling for transactional “exactly-once processing” within Kafka/Kafka Streams, but in our Python/Flask environment and with external providers, we will still need an application-level idempotency key + dedupe store (e.g., PostgreSQL unique constraint on notification_id or outbox pattern). Given that, Kafka’s EOS advantage does not fully translate to our actual delivery endpoints.
- Budget: Running Kafka reliably (multi-broker, ZooKeeper/KRaft, monitoring, upgrades, storage sizing) is materially more expensive in engineering time and infrastructure than expanding Redis usage for a bounded-notification workload.

Consequences — pros AND cons of your decision
Pros:
- Fast migration: minimal new infrastructure and can deliver async processing, retries, and dead-lettering quickly.
- Lower operational complexity: single familiar technology (Redis) plus application workers; easier on-call burden for a small team.
- Consumer groups + acking: supports at-least-once delivery with retry (claiming pending messages, timeouts, and reprocessing).
- Good fit for notification workload: bounded retention and relatively small payloads; easy fan-out via multiple streams or consumer groups.
- Cost-effective at current and 10x scale: can scale Redis vertically and, if needed, horizontally via sharding/Redis Cluster.

Cons:
- Weaker built-in replay/retention semantics than Kafka: replaying historical events for long periods is not a first-class Streams feature; trimming must be carefully designed.
- Operational risk if Redis is overloaded: Redis is currently used for sessions/rate limiting; adding Streams increases criticality and may require separating workloads (dedicated Redis instance/cluster) to avoid contention and noisy-neighbor effects.
- Exactly-once still requires application design: must implement idempotent consumers and a deduplication mechanism (e.g., notification_id stored in Postgres with a unique constraint) for billing-critical events.
- Scaling patterns are more application-driven: achieving very high throughput and partition-like parallelism requires explicit sharding (multiple streams) and careful keying.
- Limited ecosystem compared to Kafka: fewer mature off-the-shelf connectors, schema registry patterns, and operational tooling.

Alternatives Considered — why you rejected the other option
Apache Kafka was rejected for now due to:
- Setup/migration timeline risk: standing up a production-grade Kafka cluster (or selecting and integrating a managed offering within budget) plus building operational maturity (monitoring, alerting, upgrades, capacity planning) is unlikely to be safely accomplished within the 2-week constraint.
- Team experience mismatch: the team has no Kafka experience; the learning curve plus operational pitfalls (partitioning strategy, retention/storage sizing, broker failures, rebalances) increases delivery and reliability risk.
- Cost and operational overhead: Kafka’s benefits (high throughput, durable retention, strong ordering per partition, rich ecosystem) come with significant infra complexity; without a dedicated infra engineer and with modest budget (no Confluent Cloud at full scale), this is a poor fit.
- Exactly-once in practice: Kafka’s exactly-once semantics are strongest within Kafka transactional boundaries and Kafka Streams; for Python consumers producing external side effects (email/webhooks), we still need idempotency/deduplication. That reduces the practical advantage vs Redis Streams for this particular subsystem.

Definitive recommendation: implement Redis Streams as the notification event bus now (paired with application-level idempotency for billing events, plus retries and DLQ), and revisit Kafka only if we later need long-term retention/replay, cross-team data streaming, or connector-heavy integrations that justify the added operational investment.
