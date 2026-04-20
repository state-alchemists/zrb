# Title

Notification Subsystem Architecture: Kafka vs Redis Streams

# Status

Proposed

# Context

Our SaaS project management platform currently handles notifications (emails and webhooks) synchronously within the HTTP request cycle of our Python/Flask monolith. This has led to high request latencies (average 800ms, spikes up to 8s), silent notification failures when downstream providers are unavailable, and cascading failures when slow webhook endpoints exhaust connection pools. The system provides no delivery guarantees for critical billing-related notifications, despite the requirement for at-least-once delivery and exactly-once semantics where feasible.

Traffic today is modest–peak ~500 req/s and ~2M tasks/month–but we must design for a 10x traffic increase without major re-architecture. We need to:

- Decouple notification processing from HTTP requests (asynchronous processing)
- Add durable queuing with retry and exponential backoff
- Provide at-least-once delivery for billing events and exactly-once semantics where feasible
- Support future real-time WebSocket push notifications

Constraints:

- Small engineering team: 6 engineers (3 senior, 3 mid-level), no dedicated infra/SRE
- Existing Redis deployment in production (used for sessions and rate limiting)
- No Kafka experience on the current team
- Time-to-value constraint: no more than 2 weeks to set up and migrate core notifications
- Budget constraint: cannot rely on high-cost fully managed Kafka (e.g., Confluent Cloud at full scale)
- Exactly-once semantics for billing notifications must be achieved with reasonable operational complexity

Given these constraints, we are evaluating two options for the notification subsystem’s event transport and coordination layer:

1. Apache Kafka
2. Redis Streams

# Decision

We will build the notification subsystem on **Redis Streams**, using our existing Redis cluster, and implement exactly-once semantics for billing notifications via **idempotent consumers coordinated with PostgreSQL** rather than relying on the streaming system itself for global exactly-once semantics.

Redis Streams is chosen over Kafka because:

- **Operational simplicity for a small team**: We already operate Redis in production, and Redis Streams is an extension of that stack. Kafka would require standing up and operating a multi-node Kafka cluster and ZooKeeper/Kraft, or adopting a managed Kafka service that is cost-prohibitive at our expected scale and timeframe. Operational overhead of Kafka (cluster sizing, partition rebalancing, storage tuning) exceeds what a 6-person team without infra specialists can comfortably absorb within 2 weeks.
- **Sufficient throughput and durability for current and 10x projected load**: Our current and projected notification volume (even at 10x) is easily within Redis Streams’ practical throughput (hundreds of thousands to low millions of messages per second on modest hardware). With careful stream trimming and consumer group design, Redis Streams can handle our needs without approaching its performance limits.
- **Consumer groups and ordering semantics fit the use case**: Redis Streams provides per-stream ordering and consumer groups, which allows us to implement independent consumer groups for email, webhooks, billing notifications, and future WebSocket push. We can use partitioning keys (e.g., account ID) to maintain per-tenant ordering where needed. Kafka’s partition-based ordering and consumer groups are more powerful at very large scale, but not necessary for our traffic profile.
- **Faster time to value**: Implementing producers and consumers against Redis Streams in Python (via `redis-py`) is straightforward. We can likely meet the 2-week deadline to move notifications off the request path while adding retry, DLQ, and monitoring. Kafka client and infrastructure setup has a steeper learning curve and higher integration complexity.
- **Cost alignment**: Reusing our existing Redis cluster, potentially scaled slightly, aligns with the "modest" budget constraint. Kafka would either require a materially larger infra footprint we operate ourselves, or a managed Kafka service that exceeds our current budget.

Kafka offers stronger guarantees for long-term retention, horizontal scalability, and ecosystem tooling, but these are not critical for the notification subsystem at our scale and horizon. Instead, we will implement exactly-once billing semantics using idempotency keys stored in PostgreSQL and at-least-once delivery on Redis Streams, accepting that the stream layer itself is at-least-once.

# Consequences

## Pros

1. **Reduced implementation and operational complexity**
   - We reuse existing Redis infrastructure, monitoring, and operational knowledge, minimizing new technology risk.
   - No need to operate a Kafka cluster (or manage topics, partitions, replication, and specialized tooling like Kafka Connect or Schema Registry).

2. **Meets performance and scaling targets**
   - Redis Streams can handle the current and 10x projected throughput with low-latency appends and reads, assuming reasonable hardware sizing and periodic trimming.
   - Consumer groups allow multiple independent subscriber types (email, webhook, WebSocket, analytics) to process the same events concurrently without duplicating producer logic.

3. **Supports required delivery guarantees with application-level design**
   - At-least-once delivery: Consumers will use explicit acknowledgements (`XACK`) and retries with exponential backoff based on pending entries (`XPENDING`) and `XCLAIM`/`XAUTOCLAIM`.
   - Exactly-once for billing: We will implement idempotency at the application layer by:
     - Including a unique event ID in each billing message.
     - Storing processed IDs and side effects in PostgreSQL within a single transaction.
     - Using idempotent operations with third-party billing providers where possible (e.g., idempotency keys).
     - Detecting and ignoring duplicate events based on the idempotency table.

4. **Fast path to decoupling HTTP from notifications**
   - We can quickly change the monolith so that HTTP requests only enqueue a Redis Stream entry and return immediately, significantly lowering latency and reducing cascading failures from downstream notification providers.

5. **Natural fit for real-time push**
   - We can introduce a WebSocket notification service that consumes from Redis Streams and pushes to connected clients. Redis Pub/Sub can also be layered on top later if needed, but Streams provide durability and backpressure which Pub/Sub alone does not.

## Cons

1. **We do not get Kafka’s strong ecosystem and tooling**
   - Kafka brings mature ecosystem components (Kafka Connect, ksqlDB, Schema Registry, managed offerings) that simplify integrating many systems and performing stream processing. With Redis Streams we will need more bespoke glue for any future complex event processing.

2. **Limited long-term retention and replay capabilities**
   - Redis Streams is best used with relatively short retention (trimmed by size or time) to control memory usage, whereas Kafka is designed for long-term persisted logs on disk with efficient replay. Our design will focus on notification processing, not serving as a general-purpose audit or analytics log.

3. **We must implement more logic in the application layer**
   - Exactly-once semantics for billing are not provided by Redis itself; we must design idempotent handlers and maintain deduplication state in PostgreSQL.
   - Retry and DLQ handling will require application code (e.g., writing failed messages to a separate "dead-letter" stream after N attempts), whereas Kafka commonly pairs with off-the-shelf tools and patterns for DLQs.

4. **Potential future migration cost**
   - If our system grows substantially beyond the 10x target and we require cross-team event streaming, long-lived logs, or very high throughput (millions of events/sec across many services), we may need to migrate to Kafka later, incurring migration costs.

# Alternatives Considered

## Apache Kafka

We considered using Apache Kafka as the backbone for the notification subsystem.

**Reasons to adopt Kafka:**
- **High throughput and scalability**: Kafka is designed for extremely high throughput messaging with horizontal scalability via partitions. It comfortably supports workloads far above our 10x projected traffic and would future-proof the notification pipeline for very large scale.
- **Strong ordering and consumer group semantics**: Kafka provides per-partition ordering and robust consumer group coordination, which work well for event-driven architectures.
- **Message retention and replay**: Kafka stores messages on disk with configurable retention policies (by time or size), enabling long-term retention and replay, which is valuable for debugging, analytics, and rebuilding downstream materialized views.
- **Exactly-once processing semantics (EOS)**: Kafka Streams and transactional producers/consumers support exactly-once processing semantics where both reading and writing to Kafka are part of a single transaction.

**Reasons we rejected Kafka for this decision:**
- **Operational overhead exceeds team capacity and timeline**: Running Kafka ourselves (even with Kraft) requires expertise in cluster sizing, partitioning, replication, monitoring, and recovery. With only 6 engineers and no infra specialist, we are likely to spend more than the allowed 2 weeks just standing up and hardening a production-grade cluster.
- **Managed Kafka cost vs budget**: Using a high-quality managed Kafka service (e.g., Confluent Cloud) would offload operational concerns, but cost at our required reliability and projected growth is outside our current "modest" budget. Cheaper managed offerings may still require nontrivial operational oversight.
- **Overkill for current and near-term scale**: Our current workload (~500 req/s peak, ~2M tasks/month) and 10x target do not demand Kafka’s extreme scalability and long-term log retention. Kafka’s strengths would be underutilized in a subsystem focused primarily on notifications.
- **Learning curve and integration complexity**: The team has no Kafka experience today, whereas Redis is already in use. Learning Kafka concepts (topics, partitions, offsets, transactions, consumer group balancing) and integrating Python clients reliably introduces ramp-up risk that threatens the 2-week time-to-value requirement.
- **Exactly-once constraints better handled end-to-end**: While Kafka supports EOS within its ecosystem, exactly-once notification semantics ultimately depend on idempotency with external systems (email providers, billing gateways) and our database. We still need application-level idempotent design whether or not Kafka provides EOS, so Kafka’s EOS features are less compelling here.

Given these factors, Kafka is an attractive option for a future, broader event streaming platform or if our scale grows significantly, but it is not the right fit for the notification subsystem under our current constraints. Redis Streams provides sufficient throughput, ordering, and consumer group capabilities with significantly lower operational and cognitive overhead, enabling us to deliver value within the specified time and budget.
