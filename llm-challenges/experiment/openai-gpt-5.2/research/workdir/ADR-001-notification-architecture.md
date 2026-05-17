Title
Notification Subsystem Event Backbone: Redis Streams vs Apache Kafka

Status
Proposed

Context — the problem and constraints
We need to move notification delivery (email, webhooks, and upcoming WebSocket push) out of the synchronous Flask request path. Today, notification I/O causes request timeouts (800ms avg, 8s spikes), silent drops on downstream failures, and cascading incidents from slow webhook endpoints exhausting resources.

The target state requires:
- Asynchronous processing to decouple notifications from HTTP requests.
- Retries with exponential backoff and a dead-letter path.
- At-least-once delivery for billing events and exactly-once semantics where feasible.
- Headroom for 10x traffic growth and support for real-time push within ~2 quarters.

Constraints:
- Team size is 6 with no dedicated infrastructure engineer.
- Redis is already running in production; Kafka is not.
- No Kafka experience on the team.
- We must deliver initial value within 2 weeks of setup/migration.
- Budget is modest; full-scale managed Confluent Cloud is not an option.

Decision — which option you choose and a clear justification
Choose Redis Streams as the initial backbone for the notification subsystem.

Justification:
- Time-to-value and operational complexity dominate given the 2-week constraint, small team, and existing Redis footprint. Redis Streams can be introduced with minimal new infrastructure (extend current Redis deployment/cluster posture), whereas Kafka adds a new distributed system with substantially higher operational surface area (brokers, partitions, replication, leader election, capacity planning, upgrades, on-call runbooks).
- Redis Streams provides the core primitives we need immediately: ordered append-only streams, consumer groups for competing workers, acknowledgements (pending entries list) for at-least-once processing, and the ability to implement retry/backoff and dead-letter streams.
- Throughput requirements are within Redis Streams’ practical range for the next 2 quarters: peak ~500 req/s today, even at 10x growth we are in the low-thousands of events/sec domain for notifications (assuming a small multiple of events per request). Redis can sustain this when properly sized and when stream trimming/retention are configured.
- Exactly-once semantics are not realistically guaranteed end-to-end by either choice without application-level idempotency, because external side effects (email provider, webhook delivery) cannot be “rolled back.” Therefore, we will enforce exactly-once for billing notifications via an idempotency key + transactional outbox pattern in PostgreSQL (write billing event + unique event id in the same DB transaction, then publish/consume with dedupe). Redis Streams’ at-least-once delivery combined with dedupe at the consumer is sufficient to meet the business requirement.
- WebSocket push within 2 quarters can be supported by adding another consumer group (or separate stream) for real-time fanout, without having to introduce Kafka just for pub/sub. Ordering per entity/user can be maintained by consistent stream keying and consumer design.

Decision scope note: this decision selects Redis Streams as the message backbone now, with the explicit intent to keep the event schema, idempotency, and outbox design portable so we can migrate to Kafka later if retention/replay/multi-team integration needs outgrow Redis.

Consequences — pros AND cons of your decision
Pros:
- Fast delivery: can implement within the 2-week window leveraging existing Redis operations and knowledge.
- Lower operational burden: one less distributed system to deploy and run; simpler scaling knobs for the team.
- Consumer groups + ACK model: supports at-least-once processing, worker pools, and recovery of stuck jobs via pending-entries inspection.
- Ordering: preserves order within a single stream; with careful stream partitioning (e.g., per notification type or per tenant) we can maintain ordering where it matters.
- Retention control: stream trimming (MAXLEN/approx) can bound memory, and we can route dead-letter events to separate streams for audit and manual replay.

Cons:
- Retention and replay are weaker than Kafka: Redis Streams are memory-backed by default; long retention at high volume can be expensive and trimming policies can complicate audits/replays.
- Exactly-once is not provided by the broker: we must implement idempotency/deduplication (especially for billing) and handle reprocessing safely.
- Scaling model is less flexible than Kafka for very large fanout and long-lived history: Kafka’s partitioning and disk-based log can scale to much higher sustained throughput and retention with better tooling.
- Operational risk concentration: Redis is already critical (sessions/rate limiting). Adding notification workloads increases Redis importance and requires careful isolation (separate Redis instance/cluster or at minimum separate logical DB, quotas, monitoring, and protection against runaway stream growth).

Alternatives Considered — why you rejected the other option
Apache Kafka
Rejected for now due to setup/operational overhead and time-to-value constraints.
- Operational complexity: running Kafka reliably (brokers, partitions, replication, upgrades, capacity planning, monitoring, incident response) is a significant lift without a dedicated infrastructure engineer.
- Team experience gap: no Kafka experience increases delivery and reliability risk in the first implementation.
- 2-week migration constraint: standing up Kafka (self-managed) plus building producer/consumer pipelines, retry/DLQ strategy, and secure operations is unlikely to be safely completed and production-hardened within the window.

Kafka strengths acknowledged (why it might be revisited later):
- High throughput with strong partition-based ordering guarantees and robust consumer group semantics at scale.
- Disk-based log with configurable retention, easy replay, and stronger auditability.
- Exactly-once semantics are available within Kafka for Kafka-to-Kafka workflows (idempotent producers, transactions), but they still do not guarantee exactly-once for external side effects like emails/webhooks; application-level idempotency would still be required.

Given current constraints, Redis Streams is the best fit to deliver immediate reliability improvements (async + retries + DLQ + backpressure) quickly, while meeting the billing exactly-once requirement via an outbox + idempotency design.
