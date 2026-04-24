# Title

ADR-001: Choose Redis Streams for the Notification Subsystem

# Status

Proposed

# Context

The current notification subsystem sends emails and webhooks synchronously inside the Flask HTTP request cycle. At current load, this causes high request latency, request timeouts, silent delivery failures, and cascading failures when downstream webhook targets are slow or unavailable. The system must be redesigned so notification processing is asynchronous and isolated from user-facing requests.

The target state must support retries with exponential backoff, at-least-once delivery for general notifications, and exactly-once delivery for billing-critical notifications where feasible. It must also support future fan-out to additional consumers, including real-time WebSocket notifications within two quarters, and absorb roughly 10x traffic growth without another architectural rewrite.

The decision is constrained by the organization’s operating reality. The team is six engineers with no dedicated infrastructure engineer. They already run Redis in production, but they have no Kafka experience. The solution must start delivering value within two weeks, and the budget does not support a fully managed Kafka offering such as Confluent Cloud at expected scale. Exactly-once semantics for billing notifications are a hard requirement, which means broker guarantees alone are insufficient; the end-to-end design must include idempotent consumers and durable deduplication.

The options under evaluation are Apache Kafka and Redis Streams.

# Decision

Choose **Redis Streams** as the notification subsystem backbone.

Redis Streams is the better fit for the current team, timeline, and operational constraints. It provides the core capabilities this subsystem needs immediately: asynchronous decoupling from HTTP requests, consumer groups, ordered append-only streams, pending-entry tracking, replay of unacknowledged messages, and configurable retention. It can be introduced using infrastructure the team already understands and operates, which makes delivery within two weeks realistic.

For this workload, Redis Streams throughput is sufficient. Even with 10x growth from the current peak of ~500 req/s, the projected notification volume is still well within what Redis can handle for stream-based workloads on modest infrastructure. Consumer groups allow horizontal scaling of workers for email, webhooks, and future WebSocket fan-out. Ordering guarantees are acceptable because Redis Streams preserve order within a stream, which is enough for per-stream event processing if events are partitioned by notification type or tenant as needed.

Kafka is stronger on raw throughput, long-term retention, partitioned ordering, and built-in stream ecosystem support. It also offers stronger broker-level durability and mature exactly-once semantics for Kafka-to-Kafka processing. However, those benefits are not decisive here because the bottleneck is not broker throughput today; it is implementation speed, operational simplicity, and team capability. Running Kafka well requires more operational expertise, more infrastructure, and more time than this team can reasonably absorb right now.

Exactly-once delivery for billing notifications should be implemented at the application layer with Redis Streams as the transport: persist a unique event ID in PostgreSQL, publish only after the database transaction commits, and make workers idempotent by recording processed billing notification IDs before invoking email/webhook side effects. This achieves effectively exactly-once business behavior, which is the only form of exactly-once that matters for external side effects. Kafka’s exactly-once semantics would not by themselves guarantee exactly-once delivery to email providers or third-party webhooks.

# Consequences

## Pros

- **Fastest path to value**: Redis is already in production, so setup and migration effort is materially lower than Kafka and fits the two-week constraint.
- **Lower operational complexity**: No ZooKeeper/KRaft cluster design, broker partition planning, or Kafka-specific operational runbooks are required beyond extending an existing Redis footprint.
- **Sufficient throughput headroom**: Redis Streams can comfortably support the current workload and expected 10x growth for a notification subsystem of this size.
- **Consumer groups built in**: Multiple worker processes can independently consume and acknowledge messages, enabling retries and isolation across notification channels.
- **Ordering support**: Streams are append-ordered, which is adequate for notification workflows when stream design is aligned with ordering needs.
- **Retention and replay available**: Messages remain in the stream until trimmed, and pending entries can be reclaimed for retry after worker failure.
- **Good fit for short-lived operational queues**: Notifications typically need hours or days of retention, not indefinite event log storage.
- **Easy future expansion**: Additional consumers for WebSocket push notifications can be added using separate consumer groups without changing producers.

## Cons

- **Weaker exactly-once semantics than Kafka**: Redis Streams do not provide Kafka-style transactional exactly-once processing, so correctness depends on careful idempotency design in application code.
- **Less suitable for long-term event retention**: Redis is memory-oriented and retention must be actively managed; keeping large historical notification logs is more expensive and less natural than in Kafka.
- **Less mature replay/audit model**: Kafka is better for long-lived event history, reprocessing from arbitrary offsets, and broader event-stream architectures.
- **Ordering is less flexible at scale**: Redis Streams provide stream order, but Kafka’s partition model gives more explicit scaling and ordering tradeoffs for very large multi-consumer systems.
- **Potential memory pressure**: If consumers lag badly or retention is misconfigured, stream data can compete with existing Redis workloads such as sessions and rate limiting.

# Alternatives Considered

## Apache Kafka

Kafka was rejected because it is the wrong tradeoff for the current operating environment, despite being the more powerful event backbone in absolute terms.

Kafka offers very high throughput, durable disk-based retention, consumer groups, partition-based ordering, dead-letter patterns, and mature exactly-once semantics for transactional stream processing. If the company already had Kafka expertise, a platform team, or a broader event-driven roadmap requiring long-lived replayable event logs across many domains, Kafka could be the strategic choice.

However, those strengths are outweighed here by practical constraints:

- **Operational complexity is significantly higher**: Kafka cluster sizing, broker management, partition planning, monitoring, and failure recovery are non-trivial, especially without a dedicated infrastructure engineer.
- **Team familiarity is near zero**: No Kafka experience means higher migration risk and a slower path to a reliable production rollout.
- **Two-week time limit is unrealistic**: Standing up Kafka safely, integrating it into the monolith, building worker processes, and establishing operational confidence would likely exceed the allowed timeline.
- **Budget is misaligned**: A managed Kafka service would reduce complexity but is explicitly out of budget at expected scale.
- **Exactly-once for billing is still not solved end-to-end by Kafka alone**: External side effects such as sending email or calling third-party webhooks still require idempotent consumers and deduplication, so Kafka does not eliminate the need for application-level correctness controls.

For these reasons, Kafka is a stronger long-term platform technology than Redis Streams, but not the right decision for this subsystem today. Redis Streams delivers the needed reliability and scalability improvements with materially lower implementation and operational risk.