Title
Notifier Subsystem Architecture: Kafka vs Redis Streams

Status
Proposed

Context
Our current Python/Flask monolith sends emails and webhooks synchronously in the HTTP request cycle. This causes unacceptable latency (average 800 ms, spikes to 8 s), silent notification drops when downstream providers are unavailable, and cascading failures when slow webhook endpoints exhaust connection pools. We must decouple notification processing from request handling, introduce durable queuing with retries and dead-letter handling, and provide at-least-once delivery for all notifications and exactly-once (or practical equivalent) for billing-critical events (e.g., trial expiration, payment failure). We also need a foundation that can support real-time WebSocket push within two quarters and scale to roughly 10× current load (from ~500 req/s peak to ~5,000 req/s) without a fundamental re-architecture. The engineering team is small (6 engineers, no dedicated infra engineer), already operates Redis in production, has no existing Kafka expertise, and cannot afford significant managed Kafka spend. We must deliver meaningful value (offloading notifications from the request path with durable processing and retries) within approximately two weeks of focused work.

Decision
Adopt Redis Streams as the core messaging substrate for the notification subsystem, using Redis consumer groups for parallel workers and idempotent billing notification handlers to achieve effective exactly-once semantics, while reserving the option to migrate high-throughput, analytics-style streams to Kafka in the future if scale or complexity demands it.

We choose Redis Streams over Kafka because, at our current and projected scale, Redis Streams provides sufficient throughput, persistence, ordering, and consumer-group semantics with substantially lower operational complexity, shorter time-to-value, and better alignment with our existing stack and team skills. With proper stream design (separate streams for billing vs. general notifications), consumer groups, and idempotent processing keyed by business identifiers (e.g., invoice ID + event type), we can provide at-least-once delivery and practical exactly-once behavior for billing events without introducing the operational overhead of running and tuning a Kafka cluster.

Consequences
Pros
- Lower operational complexity and faster adoption
  - We already run Redis in production; adding Streams uses the same operational surface area (monitoring, backups, firewalling, patching) instead of introducing a new distributed system.
  - No need to provision and manage a multi-broker Kafka cluster, ZooKeeper/KIP-500 configuration, or specialized tooling; this fits a 6-person engineering team without a dedicated infra engineer.
  - Initial implementation (producer integration from Flask + worker processes using Redis Streams consumer groups) is realistically achievable within the 2-week setup/migration budget.

- Sufficient throughput and latency characteristics
  - Redis Streams on a properly sized Redis instance can comfortably handle our projected traffic: order-of-magnitude 5,000 notifications/s peak is well within typical Redis single-node capabilities for simple XADD/XREADGROUP patterns.
  - Single-threaded command execution with in-memory indexing provides low-latency appends and reads; notification enqueueing adds only a few milliseconds to request latency.

- Durability, ordering, and consumption model
  - Streams provide append-only log semantics with message IDs and persisted history (subject to configured trimming policy), enabling replay and backfill when needed.
  - Ordering is preserved within a single stream; we can use per-tenant or per-billing-entity stream partitioning where strict ordering within that entity matters.
  - Consumer groups give us scalable parallel processing and tracking of pending messages per consumer, supporting worker restarts and redistribution of unacked messages.

- Delivery guarantees and retries
  - At-least-once delivery is straightforward: workers only acknowledge (XACK) messages after successful email/webhook delivery; unacked messages remain in the pending entries list and can be claimed for retry with backoff logic.
  - Exactly-once semantics for billing notifications can be achieved at the application level via idempotence: store a processed-event table keyed by (event_id or message_id, notification_type) in PostgreSQL; workers check and atomically insert before side effects, ensuring each logical billing event is applied at most once even if the underlying Redis message is redelivered.
  - We can implement dead-letter behavior by moving messages that exceed retry thresholds to a dedicated DLQ stream for investigation and manual or automated remediation.

- Alignment with future WebSocket push
  - WebSocket push workers can subscribe to the same Redis Streams (or derived, filtered streams) to fan out real-time notifications to connected clients, without introducing another messaging layer.

Cons
- Single-node and memory-centric constraints
  - Redis is typically memory-bound; Streams data resides in-memory with disk persistence, so very long retention or extremely high message volume may require careful memory sizing and eviction/trimming policies.
  - Compared to Kafka’s disk-based log and long-term retention model, Redis Streams is less suited for multi-day to multi-week retention at massive scale; we will likely configure relatively short retention windows (hours to a few days) and rely on downstream stores for long-term analytics.

- Weaker built-in semantics for exactly-once than Kafka’s transactional model
  - Redis Streams does not provide end-to-end transactional exactly-once semantics across producer, stream, and consumer as Kafka’s idempotent producer + transactions can; we depend on application-level idempotency and database constraints.
  - This places more responsibility on our application design (idempotent operations, deduplication keys, careful use of DB transactions) to meet the billing requirements.

- Operational risk of overloading the existing Redis deployment
  - Using the same Redis cluster for both critical application caching (sessions, rate limiting) and durable streaming could introduce noisy neighbor effects under heavy notification load.
  - We will likely need to provision a separate Redis instance or logical cluster for Streams to isolate risk, which still increases operational footprint (though much less than Kafka).

- Fewer ecosystem features compared to Kafka
  - Kafka has a richer ecosystem for stream processing (Kafka Streams, ksqlDB), connectors, and external integrations; with Redis Streams, custom glue code is required for complex routing, transformations, or external sinks.
  - If we later need sophisticated streaming analytics pipelines, we may need to augment or partially replace Redis with Kafka or a similar system.

Alternatives Considered
Apache Kafka

We considered adopting Apache Kafka as the backbone for the notification subsystem. Kafka offers strong ordering per partition, high throughput (hundreds of thousands to millions of messages per second on a modest cluster), durable disk-based retention, robust consumer group semantics, and built-in features for exactly-once processing (idempotent producers and transactional APIs) in some client libraries.

However, we rejected Kafka as the primary solution at this time for the following reasons:

- Operational complexity vs. team size and experience
  - Running Kafka reliably requires managing a multi-broker cluster, tuning replication factors, partition counts, storage, and monitoring specific metrics (ISR size, controller health, log segment usage). Our 6-person engineering team lacks Kafka experience and has no dedicated infra engineer.
  - Even with managed offerings (e.g., MSK, Confluent Cloud), there is non-trivial setup, configuration, and cost overhead. Our budget cannot support fully managed Kafka at the scale required for production with high availability, and self-managing Kafka would exceed our operational capacity and 2-week implementation window.

- Time-to-value constraints
  - Integrating Kafka into our current Flask monolith, provisioning a cluster, securing it, setting up observability, and building robust producer/consumer components is unlikely to fit within the 2-week budget for initial value delivery.
  - Redis Streams can be integrated using existing Redis clients with simpler configuration, allowing us to decouple notifications from the request path significantly faster.

- Scale-mismatch and premature optimization
  - Our projected 10× traffic (on the order of thousands of notifications per second) is well within what a properly sized Redis deployment can handle. Kafka’s design shines at much larger scales and multi-tenant data pipelines; adopting it now would optimize for a scale we have not yet reached while increasing complexity.

- Cost considerations
  - A production-grade Kafka deployment (self-managed or managed) would require additional infrastructure, storage, and operational overhead that are difficult to justify given our modest budget and current needs.

Future Evolution
If, in the future, notification volume, retention requirements, or streaming analytics needs grow beyond what is comfortable for Redis Streams, we can:
- Introduce Kafka for high-volume, long-retention, or analytics-oriented streams while keeping Redis Streams for latency-sensitive notification delivery; or
- Gradually migrate the notification event bus to Kafka once the team has bandwidth and justification to operate it.

For now, Redis Streams offers the best balance between delivery guarantees, throughput, operational simplicity, cost, and our team’s constraints, while still providing a viable migration path to Kafka if and when our requirements outgrow Redis.
