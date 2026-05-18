Title
Choose Redis Streams for Notification Subsystem Event Queue

Status
Proposed

Context — the problem and constraints
We need to decouple notification delivery (email, webhooks, and upcoming WebSocket pushes) from the synchronous HTTP request cycle in a Python/Flask monolith. Today, notifications are sent inline, causing request latency spikes and timeouts (avg ~800ms, spikes to ~8s), silent drops on downstream failure, and cascading failures (slow webhooks exhausting connection pools).

The new subsystem must:
- Process notifications asynchronously with consumer groups and horizontal scaling.
- Provide retry with exponential backoff and a dead-letter path for poison messages.
- Provide at-least-once delivery for most events, and exactly-once semantics for billing-critical notifications ("trial expired", "payment failed") where feasible.
- Support a 10x traffic growth target without requiring another re-architecture.
- Be deliverable quickly: no more than ~2 weeks of setup/migration before delivering value.

Constraints:
- Team of 6 engineers, no dedicated infrastructure engineer.
- Redis is already in production for sessions/rate limiting.
- No Kafka experience on the team.
- Modest budget; cannot rely on Confluent Cloud at full scale.

Decision — which option you choose and a clear justification
Choose Redis Streams as the initial event backbone for the notification subsystem.

Justification:
- Time-to-value and operational fit dominate: Redis is already operated in production, and Redis Streams adds a durable, ordered append-only log with consumer groups without introducing an additional distributed system (Kafka brokers + ZooKeeper/KRaft, monitoring, capacity planning, upgrades). Given the "< 2 weeks" constraint and no Kafka experience, Redis Streams is the only option likely to meet the delivery timeline without disproportionate operational risk.
- Required semantics are achievable with Redis Streams plus application-level idempotency:
  - Redis Streams provides at-least-once delivery via consumer groups (pending entries list and explicit acknowledgements). This directly addresses silent drops.
  - Exactly-once for billing notifications is not something we should promise purely from the broker choice in this environment. Even with Kafka, end-to-end exactly-once requires careful producer/consumer transaction design and usually a stream processing stack; for external side effects (emails/webhooks) it still reduces to idempotent consumers.
  - With Redis Streams we can enforce exactly-once effects for billing events using a deterministic event id and a deduplication/transactional outbox pattern backed by PostgreSQL (source of truth) and/or Redis atomicity: consumers write a "processed" marker keyed by event id (or a DB row with a unique constraint) in the same unit of work as updating internal state; external sends use an idempotency key to avoid duplicates.
- Throughput/latency headroom: our current peak is ~500 req/s and the target is 10x. Notification events per request vary, but Redis Streams can comfortably handle tens of thousands of messages/sec per instance in typical deployments; Kafka can do more, but that headroom is not the bottleneck given our near-term scale and the need to ship.
- Ordering guarantees map to our needs: per-stream ordering is preserved in Redis Streams. We can model ordering-sensitive flows (e.g., per-user notifications, per-task updates) by partitioning streams by key (e.g., stream per tenant or per shard) to bound out-of-order effects. Kafka would require topic partitioning and keying similarly; neither system gives global ordering at scale.
- Retention: notifications are operational events, not an analytics/event-sourcing log. We need enough retention to replay after outages and to support retries/DLQ, not multi-week retention. Redis Streams supports trimming by length or approximate MAXLEN; Kafka’s long retention and replay are valuable, but not required for this subsystem’s initial scope.

Decision summary: Redis Streams best satisfies the constraints (team skill, budget, <2 weeks) while meeting functional requirements (async, retries, consumer groups, at-least-once) and enabling exactly-once effects for billing via idempotency and dedupe.

Consequences — pros AND cons of your decision
Pros:
- Fast adoption: reuses existing Redis footprint and operational knowledge; minimal additional infrastructure.
- Consumer groups and pending messages: enables at-least-once processing, explicit ack, redelivery of unacked messages, and visibility into stuck consumers.
- Lower operational complexity than Kafka: fewer moving parts (single Redis cluster/replication + monitoring), simpler upgrades and capacity planning.
- Low latency: good fit for near-real-time notification fanout and forthcoming WebSocket pushes.
- Cost-effective: avoids standing up and operating a Kafka cluster or paying for managed Kafka.

Cons:
- Weaker built-in durability/retention story than Kafka: retention is limited by memory/disk configuration and trimming; long replays are less practical.
- Scaling model is less flexible than Kafka at very high throughput: Redis is typically scaled vertically or via clustering/sharding; Kafka scales horizontally by adding partitions/brokers and is the standard choice for very large event volumes.
- Exactly-once is not broker-provided end-to-end: we must implement idempotent consumers (and likely an outbox/dedupe store) carefully, especially for billing events.
- Operational risk concentration: Redis already supports sessions/rate limiting; adding Streams increases the blast radius of Redis incidents unless we isolate via separate Redis instances/clusters or strict resource limits.

Alternatives Considered — why you rejected the other option
Apache Kafka
Rejected for now due to mismatch with team constraints and time-to-value:
- Operational complexity: running Kafka reliably (brokers, replication, KRaft quorum, partition management, upgrades, monitoring/alerting, disk capacity planning) is a significant ongoing effort. With no infrastructure engineer and no Kafka experience, this increases outage risk.
- Setup/migration timeline: standing up Kafka, integrating producers/consumers, establishing observability, and hardening failure modes is unlikely to fit the "≤ 2 weeks" requirement.
- Cost: managed Kafka (e.g., Confluent Cloud/MSK) could reduce ops burden but conflicts with the "modest budget" constraint at full scale; self-managed Kafka brings the ops burden back.
- Exactly-once expectations: Kafka offers exactly-once semantics for Kafka-to-Kafka processing with transactions and idempotent producers, but end-to-end exactly-once with external side effects (email/webhooks) still requires idempotent consumer design. Kafka does not remove the need for deduplication and careful side-effect handling for billing notifications.

Revisit conditions: If notification volume or retention needs materially increase (e.g., event-sourcing requirements, multi-day replay, cross-service event bus) or if we split the monolith into services, Kafka may become the preferred backbone. For the current monolith + small team + rapid delivery constraints, Redis Streams is the better fit.
