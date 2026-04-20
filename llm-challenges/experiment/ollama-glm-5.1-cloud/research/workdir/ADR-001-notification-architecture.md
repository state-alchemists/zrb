# ADR-001: Notification Subsystem Message Broker

**Status**: Proposed

## Context

Our SaaS project management platform (85k MAU, ~2M tasks/month, 500 req/s peak) handles notifications synchronously inside the HTTP request cycle. This has caused request timeouts (800ms avg, 8s spikes), silent failures with no retry or dead-letter queue, two cascading-failure incidents from slow webhook endpoints, and zero delivery guarantees for billing-critical notifications.

We need to decouple notification processing from request handling to achieve:

1. **Async processing** — notifications must not block HTTP responses
2. **Retry with exponential backoff** — no more silently dropped notifications
3. **At-least-once delivery** for all events; **exactly-once** for billing notifications where feasible
4. **WebSocket push** support within 2 quarters
5. **10x traffic growth** without re-architecting (target: 5,000 req/s peak)

Hard constraints:

- 6-person engineering team (3 senior, 3 mid-level), **no dedicated infrastructure engineer**
- **Redis already in production** for sessions and rate limiting
- **No Kafka experience** on the team
- **2 weeks maximum** before the migration delivers value
- **Modest budget** — managed Confluent Cloud at full scale is not affordable
- Billing notifications require exactly-once semantics

## Decision

**We choose Redis Streams as the message broker for the notification subsystem.**

Redis Streams provides consumer groups, persistent message history, and sufficient throughput for our current and projected scale — while fitting within our team's expertise, timeline, and budget. Kafka is the stronger system in isolation, but the operational and organizational cost of adopting it makes it the wrong choice for our current situation.

We will implement exactly-once semantics for billing notifications through **application-level idempotency** (idempotency keys persisted in PostgreSQL, deduplication at the consumer), which is required regardless of broker choice.

## Consequences

### Pros

- **Fast time-to-value.** We can begin producing to Redis Streams within days. No new infrastructure to provision, monitor, or patch. The team already operates Redis in production and understands its failure modes, persistence options (AOF/RDB), and memory management.
- **Operational simplicity.** One fewer distributed system to run. No Zookeeper/KRaft cluster, no broker configuration tuning, no partition rebalancing drills. A 6-person team with no infra engineer cannot afford the operational surface area of Kafka.
- **Sufficient throughput.** Redis Streams handles well over 100k messages/s on a single instance. Our 10x target (5,000 req/s peak, with perhaps 10–20 notification events per request at the outer bound) is orders of magnitude below Redis's ceiling. We will not hit a throughput wall.
- **Consumer groups.** `XREADGROUP` with `XACK` gives us the fan-out and competing-consumer semantics we need: multiple notification workers consuming in parallel, each message delivered to one worker per group. This directly addresses our cascading-failure problem by isolating consumers.
- **Message retention.** `XADD` with `MAXLEN` gives us bounded retention. We can set `MAXLEN ~100000` per stream, retaining enough history for replay and debugging while keeping memory predictable. For billing-critical streams, we can use longer retention or offload to PostgreSQL before trimming.
- **Dead-letter handling.** After N failed retries, a consumer can move a message to a dedicated `notifications:dead-letter` stream. This is a simple, auditable pattern.
- **Cost.** No new infrastructure spend. Our existing Redis instance (or a second, modestly sized one for isolation) costs a fraction of even a small Confluent Cloud cluster.
- **WebSocket alignment.** Redis Pub/Sub (already on our roadmap for real-time push) pairs naturally with Redis Streams. The same operational skillset covers both.

### Cons

- **No native exactly-once semantics.** Redis Streams provides at-least-once delivery. Exactly-once requires application-level idempotency — we will implement this via idempotency keys in PostgreSQL at the consumer. This is not unique to Redis; Kafka's "exactly-once" (EOS) applies only to Kafka-to-Kafka stream processing (Kafka Streams), not to end-to-end delivery to external systems like email providers or HTTP webhooks. **Both options require application-level idempotency for billing notifications.**
- **Memory-bound retention.** Unlike Kafka's disk-based log, Redis Streams live in memory (with AOF/RDB persistence). Very long retention or very high throughput streams consume RAM. We mitigate this with `MAXLEN` trimming and a separate Redis instance for the notification workload so it cannot starve session storage.
- **No native partitioning.** Kafka partitions provide parallelism and ordering guarantees per key. Redis Streams are single-shard structures (though Redis Cluster shards keys across nodes). For our use case, we will use separate streams per notification type (`notifications:email`, `notifications:webhook`, `notifications:billing`) to achieve parallelism. Ordering within a type is preserved (Redis Streams are strictly ordered by ID).
- **No built-in schema registry.** Kafka's Schema Registry enforces contract evolution. We will enforce message schemas at the application layer (Pydantic models in the producer/consumer) and version messages explicitly.
- **Smaller ecosystem.** Fewer observability tools, fewer battle-tested client libraries, less community knowledge for complex event routing. For a notification subsystem — not a multi-team event-driven platform — this is acceptable.
- **Potential re-evaluation.** If we eventually grow into a multi-team event-driven architecture with complex streaming joins or materialized views, Redis Streams will become limiting. We accept this; the 2-week constraint and current team reality make Kafka adoption premature.

## Alternatives Considered

### Apache Kafka

Kafka is the industry-standard distributed event streaming platform and would be the stronger technical choice in a vacuum. Specific advantages we acknowledge:

- **Superior throughput at extreme scale.** Kafka handles millions of events/second with sub-second latency across clusters. For 10x our current load, this is overspecified.
- **Disk-based retention.** Kafka retains messages on disk for configurable periods (days to weeks) without memory pressure. This is genuinely better than Redis's memory-bound model.
- **Partition-based parallelism and ordering.** Messages with the same key are always delivered to the same partition in order. This is a cleaner model than separate streams per type.
- **Exactly-once semantics (Kafka Streams).** Kafka's transactional producer and idempotent producer provide exactly-once within the Kafka ecosystem. As noted above, this does not extend to external systems — the billing-notification requirement still demands application-level idempotency.
- **Rich ecosystem.** Schema Registry, Kafka Connect, ksqlDB, mature monitoring tools (Burrow, Cruise Control), and battle-tested client libraries.

**Why we reject Kafka for this decision:**

| Factor | Kafka | Impact |
|--------|-------|--------|
| **Operational complexity** | Requires Zookeeper or KRaft, broker management, partition rebalancing, topic configuration | Without a dedicated infra engineer, our 6-person team would spend disproportionate time operating Kafka instead of building product |
| **Team experience** | Zero | Learning curve slows the 2-week delivery constraint to likely 6–8 weeks before first value |
| **Budget** | Self-hosted: requires 3+ brokers for production, plus monitoring — significant EC2 and engineering cost. Managed (Confluent Cloud): explicitly stated as unaffordable at our scale | Either option exceeds our modest budget |
| **Time-to-value** | Minimum 3–4 weeks to stand up a production cluster, tune producer/consumer configs, and implement the notification pipeline | Violates the 2-week constraint |
| **Current scale** | 500 req/s peak, targeting 5,000 req/s | Kafka is designed for 10–100x this volume. We would be operating a system whose complexity is not justified by our load |
| **Exactly-once** | Only within Kafka, not end-to-end | Still requires application-level idempotency for billing — same work we must do with Redis |

Kafka is the right tool when you need a durable, replayable event backbone for a multi-team, multi-service architecture. We are a single monolith with 6 engineers trying to solve a specific async-processing problem. Adopting Kafka now would be over-engineering that delays value delivery.

**If we outgrow Redis Streams** (sustained throughput exceeding single-instance capacity, need for multi-team event routing, or complex stream processing), we will revisit Kafka in a future ADR. At that point, we will have the operational maturity, team size, and budget to adopt it responsibly.