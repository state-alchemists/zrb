**Title**

ADR-001: Notification Subsystem Messaging Backbone

**Status**

Proposed

**Context**

The current notification subsystem runs synchronously inside the Flask HTTP request cycle, which is causing high latency, request timeouts, silent notification loss, and cascading failures when downstream email or webhook providers are slow or unavailable. The system must be redesigned to process notifications asynchronously, support retries with exponential backoff, and provide stronger delivery guarantees for billing-critical events.

The platform currently serves 85,000 monthly active users, processes about 2 million tasks per month, and peaks at roughly 500 requests per second. The target is to support 10x traffic growth and add real-time WebSocket notifications within two quarters without another major re-architecture.

Two messaging options are under consideration: Apache Kafka and Redis Streams. The decision must account for technical requirements and organizational constraints. The team has 6 engineers, no dedicated infrastructure engineer, already operates Redis in production, has no Kafka experience, must deliver value within 2 weeks, and has a modest budget that rules out a fully managed Kafka offering at scale.

From a technical standpoint, the subsystem needs consumer groups, durable message retention, replay capability, ordering guarantees at least within a notification stream or key, and support for at-least-once delivery. Billing notifications additionally require exactly-once semantics where feasible. In practice, exactly-once end-to-end delivery to external systems such as email providers and webhook endpoints cannot be guaranteed solely by the broker; it must be implemented with idempotency keys, deduplication, and transactional state in the application layer. Therefore, the broker choice should be evaluated on whether it enables reliable at-least-once processing, preserves ordering where needed, and can be operated safely by the current team.

**Decision**

Choose **Redis Streams** as the notification subsystem backbone.

Redis Streams is the better fit for the current system because it solves the immediate production problem with the lowest operational and migration cost while still meeting the likely throughput requirements. The existing traffic profile does not justify Kafka's operational complexity today: even with 10x growth, the notification workload is still well within Redis Streams capacity for a single subsystem, especially since notification events are far lower volume than raw HTTP requests and can be partitioned across streams or consumers if needed.

Redis Streams provides the key features required for this phase: append-only streams, consumer groups, pending-entry tracking, explicit acknowledgment, and message retention controls. That is enough to decouple notification work from requests, implement retries and dead-letter handling in workers, and support real-time fan-out patterns later for WebSocket notifications. It also preserves stream order, which is useful for per-entity notification sequencing, though strict global ordering is neither realistic nor required.

Kafka is stronger on raw throughput, long-term retention, replay, partitioned ordering, and broker-level exactly-once semantics within Kafka workflows. However, those advantages are not decisive here because the team cannot absorb Kafka's setup and operational overhead within the 2-week delivery window, and Kafka's exactly-once guarantees do not extend to external side effects like sending emails or invoking webhooks. Billing-critical exactly-once behavior will still require application-level idempotency backed by PostgreSQL regardless of broker choice.

The recommended design is to use Redis Streams for transport and PostgreSQL-backed idempotency records for billing notifications. This gives at-least-once broker delivery, practical exactly-once processing for billing events, and a fast path to production with tooling the team already knows.

**Consequences**

Pros:
- Low operational complexity because Redis is already deployed and understood by the team.
- Fastest path to value; likely achievable within the required 2-week setup and migration window.
- Supports consumer groups, acknowledgments, retries, and pending-message recovery needed to stop silent failures.
- Good enough throughput for current load and expected 10x growth of the notification subsystem.
- Easier integration with the existing Flask monolith and future WebSocket notification workers.
- Lower infrastructure cost than standing up and operating Kafka.

Cons:
- Weaker durability and retention model than Kafka, especially for very long replay windows or event-history use cases.
- Exactly-once semantics are not provided by Redis Streams; billing correctness must be enforced in application logic with idempotency keys and transactional writes.
- Ordering guarantees are limited to stream order and worker behavior; scaling out consumers requires careful partitioning if per-entity order matters.
- Retry scheduling with exponential backoff and dead-letter handling must be built in application code rather than relying on richer ecosystem tooling.
- If the platform evolves into a much larger event-driven architecture with many independent consumers and long-lived replay needs, Redis Streams may be outgrown and require future migration.

**Alternatives Considered**

**Apache Kafka** was rejected for now.

Kafka is technically the more powerful event platform. It offers very high throughput, durable retention, strong replay support, partition-based ordering, mature consumer group semantics, and broker-assisted exactly-once semantics for Kafka-to-Kafka processing. If the company already had Kafka expertise, a platform team, or a broader event-streaming roadmap, Kafka could be the better long-term foundation.

However, it is the wrong choice under the current constraints. The team has no Kafka experience, no dedicated infrastructure engineer, a strict 2-week window before value must be delivered, and a limited budget that cannot support a fully managed Kafka service at the desired scale. Self-managing Kafka on AWS would add substantial operational risk around cluster sizing, broker management, partition planning, monitoring, upgrades, and failure recovery. That complexity is disproportionate to the current notification workload.

Kafka also does not eliminate the hardest requirement by itself: exactly-once delivery for billing notifications to external systems. Once a worker sends an email or webhook, correctness still depends on application-level idempotency and transactional tracking, not just broker semantics. Because Redis Streams already satisfies the core async processing needs and keeps implementation and operational scope aligned with team capacity, Kafka is not justified at this stage.
