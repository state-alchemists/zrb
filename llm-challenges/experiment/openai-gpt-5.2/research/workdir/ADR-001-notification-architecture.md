Title
Adopt Redis Streams as the notification event bus (with idempotent consumers and an outbox pattern for billing events)

Status
Proposed

Context
We operate a SaaS project management platform (85k MAU, ~2M tasks/month, peak ~500 req/s) on a Python/Flask monolith backed by PostgreSQL. Notifications (email + webhooks) currently run synchronously in the HTTP request path, causing high and spiky latencies, request timeouts, and cascading failures when downstream providers/webhook endpoints are slow.

We need to decouple notification delivery from the request cycle and add:
- Asynchronous processing with retry + exponential backoff
- Consumer-group style parallelism for workers
- Message retention sufficient for recovery/replays and operational debugging
- At-least-once delivery generally, and exactly-once semantics for billing-critical notifications (e.g., payment failed)
- A path to add real-time WebSocket push notifications within ~2 quarters
- Capacity for ~10x traffic growth without needing to redesign the messaging layer

Constraints:
- Team of 6 engineers, no dedicated infrastructure engineer
- Redis already runs in production (sessions/rate limiting)
- No Kafka experience on the team
- Must deliver value within ~2 weeks (setup/migration)
- Modest budget; cannot rely on Confluent Cloud at full scale today
- Exactly-once semantics must be maintained for billing notifications

Decision
Choose Redis Streams for the notification subsystem.

Justification:
- Time-to-value and operational complexity: Redis is already deployed and operated by the team; Redis Streams adds a minimal incremental operational burden compared with introducing Kafka (brokers, Zookeeper/KRaft, topic management, partition planning, monitoring, upgrades). Given the “≤2 weeks” constraint and lack of Kafka experience, Redis Streams is the lower-risk path to decouple notifications quickly.
- Throughput fit: At current scale (peak ~500 req/s) and anticipated 10x growth, Redis Streams can handle high message rates on a modest cluster when designed correctly (append-only stream writes, consumer groups, horizontal worker scaling). Kafka can likely handle higher ceiling throughput, but the system’s bottlenecks for notifications are more likely downstream I/O (email/webhooks) than broker throughput.
- Ordering and parallelism: Redis Streams preserves order within a stream (by ID) and supports consumer groups with per-message acknowledgment. We can structure streams by notification “topic” (e.g., billing, task_updates, webhooks) and, where strict ordering matters (per user, per organization, or per webhook endpoint), use stream-per-key or consistent routing keys to avoid cross-key reordering. Kafka offers ordering per partition; Redis offers ordering per stream. Both require deliberate sharding to align ordering requirements with parallelism.
- Retention and replay: Redis Streams supports trimming (MAXLEN) and querying by ID for replay within retention. While Kafka is stronger for long retention and large-scale replay, our immediate need is reliable async delivery, retries, and short-to-medium retention for debugging and recovery. If we later require multi-day/week retention at large volumes, that becomes a re-evaluation point.
- Exactly-once semantics: In practice, “exactly once” for notifications is achieved by making delivery idempotent (dedupe keys) and using transactional production of events from the database (outbox) rather than relying solely on broker-level exactly-once.
  - Redis Streams provides at-least-once delivery with consumer groups; duplicates can occur (e.g., worker crash after side effects but before ACK). We will enforce exactly-once for billing notifications by:
    1) using a PostgreSQL outbox table written in the same transaction as the billing state change,
    2) emitting to Redis Streams from an outbox publisher, and
    3) having consumers write a “delivered” record keyed by event_id (or provider idempotency key) before side effects (or using provider idempotency tokens where supported).
  - Kafka’s “exactly-once semantics” (EOS) primarily guarantees exactly-once processing within Kafka (producer/consumer transactions) but still does not guarantee exactly-once delivery to external systems like email/webhook endpoints without idempotency. Kafka would not remove the need for idempotent consumers/outbox for billing events.
- Fit for WebSocket push: WebSocket notification fanout often needs low-latency, short-lived retention, and consumer-group processing. Redis Streams integrates naturally with Redis Pub/Sub patterns and in-memory data structures; Streams can serve as the durable queue while WebSocket servers maintain online-user routing state in Redis.

Consequences
Pros:
- Fastest path to decouple notifications from HTTP requests; leverages existing Redis operations and team familiarity.
- Built-in consumer groups with explicit ACKs enable horizontal scaling of workers and at-least-once processing.
- Lower operational burden and cost than running Kafka ourselves; meets the 2-week delivery constraint.
- Adequate ordering guarantees within a stream; can be shaped to meet per-entity ordering where needed.
- Works well for mixed workloads: email/webhook retries, scheduled backoff (via delayed-queue pattern), and later WebSocket push.

Cons:
- We do not get broker-level end-to-end exactly-once; we must implement exactly-once for billing via outbox + idempotency/deduplication (which we would also need with Kafka for external side effects).
- Retention/replay is more limited and operationally sensitive (memory/disk) than Kafka’s log storage model; long retention at high volume may require Redis Cluster, careful sizing, and stream trimming policies.
- Consumer-group semantics differ from Kafka; features like multi-topic consumption patterns and ecosystem tooling are more limited.
- Handling delayed retries requires an explicit pattern (e.g., sorted-set scheduler or separate “delay” streams), whereas Kafka ecosystems often standardize this via tooling.

Alternatives Considered
Apache Kafka
Rejected because:
- Operational complexity and setup time: Running Kafka reliably in AWS without a dedicated infra engineer adds significant complexity (cluster sizing, partition planning, upgrades, monitoring, incident response). Meeting the “≤2 weeks” constraint while also building the notification pipeline is unlikely.
- Team experience: No Kafka experience today increases delivery risk and on-call risk.
- Budget constraints: Managed Kafka (e.g., Confluent Cloud) is explicitly out of budget “at full scale today,” and self-managing Kafka shifts cost into engineering time and operational risk.
- Exactly-once is not a silver bullet: Kafka EOS does not guarantee exactly-once delivery to email/webhook providers; we still need an outbox/idempotency strategy for billing notifications. Given we must build that anyway, Kafka’s incremental benefit is mostly long-retention/replay and ecosystem tooling, which is not the primary immediate constraint.

That said, Kafka remains a strong option if retention/replay requirements grow substantially (e.g., multi-week event logs), if we add multiple independent downstream consumers requiring high fanout with strong isolation, or if traffic grows beyond what is economical to host in Redis memory/storage. In that case, re-evaluate with a managed Kafka option (MSK/Confluent) and a dedicated operational owner.
