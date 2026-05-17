# ADR-001: Notification Subsystem — Async Processing Architecture

**Status**: Proposed

---

## Context

The notifications module (email, webhooks) currently runs synchronously inside the Flask HTTP request cycle on our project management platform (85k MAU, ~2M tasks/month, ~500 req/s peak). This has produced four interconnected failures:

1. **Request timeouts** — Average notification latency is 800ms, spiking to 8s at peak, degrading the entire API experience.
2. **Silent failures** — External providers or webhook endpoints going down drops notifications permanently. No retry, no visibility.
3. **Cascading failures** — Two production incidents this year where a slow webhook exhausted the connection pool, taking down unrelated features.
4. **No delivery guarantees** — Billing-critical events ("trial expired", "payment failed") need exactly-once delivery but the current system provides none.

We need to decouple notifications from the HTTP request cycle into an asynchronous processing pipeline that supports retry with exponential backoff, at-least-once delivery with exactly-once for billing events, and future WebSocket push notifications. The system must handle 10x traffic growth without re-architecting.

### Key Constraints

- **Team**: 6 engineers (3 senior, 3 mid-level), no dedicated infrastructure engineer.
- **Existing infrastructure**: Redis is already in production for session storage and rate limiting.
- **No Kafka experience** on the team.
- **Setup budget**: Must deliver value within 2 weeks of migration work.
- **Budget**: Modest — cannot afford managed Confluent Cloud at full scale.
- **Exactly-once semantics** required for billing notifications.

---

## Decision

**Adopt Redis Streams** as the notification queue substrate.

Redis Streams provides the right balance of capability and operational simplicity for a 6-person team without dedicated infrastructure support. The already-running Redis instance eliminates a new stateful service from the stack, and the team can be productive within the 2-week constraint because Redis and its Python client (`redis-py`) are already familiar.

---

## Consequences

### Positive

1. **Zero new infrastructure** — Redis is already deployed, monitored, and backed up for session storage. Adding streams reuses the existing cluster (with a modest memory budget increase). No new service to learn, deploy, or troubleshoot.

2. **Fast time-to-value** — The team knows Redis. `redis-py` supports streams natively. A producer (HTTP handler) → consumer (background worker) pipeline can be built and deployed in days, not weeks. This meets the 2-week constraint comfortably.

3. **Consumer groups with at-least-once delivery** — Redis Streams consumer groups track per-consumer delivery state. A consumer that crashes mid-processing does not acknowledge its message; on restart, it re-reads pending entries, giving at-least-once semantics out of the box. For billing notifications, we pair this with a consumer-side idempotency key in PostgreSQL to achieve exactly-once.

4. **Bounded memory footprint** — Streams can be capped with `MAXLEN ~ N` to bound memory growth. At our current scale (~2M notifications/month ~= ~0.8/s average, ~500/s peak), even a multi-hour retention window fits comfortably in Redis memory alongside existing session data. Estimated incremental RAM: ~2-4 GB, well within a `cache.r6g.large` to `cache.r6g.xlarge` instance.

5. **Real-time WebSocket path** — Redis Streams natively supports Pub/Sub consumers that can fan out to WebSocket connections. The `SUBSCRIBE` mechanism on streams (via consumer groups or separate Pub/Sub channels) provides a clean path to the WebSocket push requirement within 2 quarters.

6. **Retry with exponential backoff** — A dead-letter stream can hold messages that exceed the retry limit. The worker reads from the main stream, writes failed deliveries to a retry stream with a per-message `next_attempt_at` timestamp, and a scheduler promotes eligible messages back to the main stream. This pattern is well-documented and straightforward to implement with streams.

7. **Operational simplicity** — No JVM tuning, no ZooKeeper/KRaft migration, no partition rebalancing, no topic configuration. A 6-person team with no infrastructure specialist can keep this running with the same runbooks they already have for Redis.

### Negative

1. **No native exactly-once** — Redis Streams does not provide exactly-once delivery at the protocol level. Consumer groups guarantee at-least-once, but duplicates are possible (e.g., a consumer processes a message, acks it, but the ack is lost before Redis persists it). We must implement idempotency keys in the consumer — this is well-understood and standard practice, but it's work we'd need to do and maintain.

2. **Throughput ceiling below Kafka** — A single Redis node can handle tens of thousands of writes per second, which covers our current and 10x growth needs (~5,000 req/s peak). However, scaling Redis Streams throughput requires cluster sharding, which adds complexity and breaks global ordering. If the platform grows 100x, Redis Streams becomes a bottleneck that Kafka would not be.

3. **No long-term message retention** — Redis is an in-memory store with optional persistence (RDB/AOF). It is not designed for weeks or months of message retention. If the team ever needs long-term audit trails for notifications (e.g., replaying months-old events), we would need to archive stream data to S3 or PostgreSQL separately. For the current use case (retries over minutes to hours), this is not a problem.

4. **Consumer rebalancing is manual** — Unlike Kafka's automatic partition rebalancing, Redis Streams requires the application to manage consumer group membership when scaling workers up or down. This is manageable with a simple heartbeat-based coordinator, but it is an additional piece of application logic the team must own.

---

## Alternatives Considered

### Apache Kafka

Kafka is the industry standard for high-throughput, durable event streaming. It offers:

- **Throughput**: Millions of messages/second — 10x our target with headroom.
- **Exactly-once semantics** at the protocol level via transactions and idempotent producers.
- **Native log compaction** and multi-day/week retention.
- **Mature consumer group protocol** with automatic rebalancing.

#### Why we rejected it

Despite Kafka's technical strengths, it is the wrong choice for this team and this problem:

1. **Operational burden on a 6-person team** — Kafka requires dedicated infrastructure expertise. Running a production cluster means managing ZooKeeper or KRaft, monitoring broker disk usage, tuning JVM heap and GC, handling partition leadership elections, and dealing with `__consumer_offsets` corruption. The team has no Kafka experience and no dedicated infrastructure engineer. A misconfigured Kafka cluster (e.g., insufficient replication factor, unclean leader election) is more dangerous than running without a queue at all.

2. **Setup cost exceeds the 2-week constraint** — Standing up a production Kafka cluster on AWS MSK is straightforward, but learning the Kafka ecosystem (producers, consumers, schema registry, Kafka Connect, offset management) would take the team 4-6 weeks before delivering value. MSK Serverless reduces operational burden but costs ~$0.75/hr minimum (~$540/month) before any provisioned throughput — and we can't use it if we need VPC peering or fine-grained access control. Self-hosting Kafka on EC2 is cheaper but requires significant operational expertise.

3. **Wrong scale for the problem** — Our peak throughput is ~500 req/s, and the 10x target is 5,000 req/s. Kafka's capabilities (millions of messages/sec) are over-provisioned by 100-1000x for this use case. We would pay the complexity tax of Kafka without needing its performance characteristics.

4. **Team learning curve** — Every team member must understand Kafka's producer acks, consumer offset commits, partition assignment strategies, and rebalancing protocol. This is weeks of learning that could instead be spent building the notification system itself.

5. **Cost at scale** — Managed Kafka (Confluent Cloud, AWS MSK) becomes expensive quickly. Confluent Cloud's basic tier starts at ~$0.10/GB ingress, plus hourly broker costs. At our message volume, this would be manageable, but the budget constraint explicitly rules out Confluent Cloud at full scale. Self-hosting trades money for operational complexity — not a trade worth making at our team size.

**Verdict**: Kafka solves problems we do not yet have, at a complexity cost we cannot afford. Revisit if the platform grows to 100x current scale or if the team hires an infrastructure specialist.

### Existing PostgreSQL with background workers

Running the queue inside PostgreSQL (via `pg_queues`, `LISTEN`/`NOTIFY`, or a simple `jobs` table) was considered as the zero-infrastructure-change option.

- **Familiarity**: The team knows PostgreSQL deeply.
- **Transactional guarantees**: Enqueue and database write in the same ACID transaction.
- **No new infrastructure**: Zero new services.

**Rejected because**: Polling a `jobs` table at 500 req/s creates unacceptable contention on the primary database — the same database that is already at the edge of its performance envelope (single primary, one read replica). `LISTEN`/`NOTIFY` lacks delivery guarantees (payload limit of 8,000 bytes, dropped on connection loss, no consumer groups). A `SELECT ... FOR UPDATE SKIP LOCKED` polling pattern works at small scale but does not scale to 5,000 req/s without adding replicas and query overhead. PostgreSQL is the wrong substrate for a message queue; it should remain the system of record for domain data.

**Verdict**: Correct in principle (leverage existing infra), wrong in execution. Keep PostgreSQL as the source of truth; use Redis Streams as the async transport layer.

---

## Specific Technical Evaluation

| Property | Redis Streams | Apache Kafka |
|---|---|---|
| **Throughput** | ~50-100k msgs/s per node — sufficient for 10x growth | ~1M+ msgs/s per broker — overkill |
| **Ordering guarantees** | Per-stream, per-shard ordering | Per-partition ordering |
| **Message retention** | Bounded by memory (MAXLEN) — hours to days | Disk-based — days to months |
| **Consumer groups** | Yes, with manual rebalancing | Yes, with automatic rebalancing |
| **At-least-once delivery** | Native (consumer groups with pending entries) | Native (committed offsets) |
| **Exactly-once delivery** | Requires consumer-side idempotency | Protocol-level with transactions |
| **Operational complexity** | Low — single process, familiar to team | High — JVM, cluster management, ZK/KRaft |
| **Time to value** | 3-5 days | 4-6 weeks |
| **Team learning curve** | Minimal (already use Redis) | Significant (no Kafka experience) |
| **Scalability ceiling** | Moderate (vertical then cluster sharding) | Very high (horizontal partitioning) |

---

## Implementation Plan (Summary)

1. **Week 1**: Add a `notification_stream` in the existing Redis instance (capped at ~100k entries). Extract notification dispatch from Flask handlers into a producer that writes to the stream. Deploy a single background worker process consuming from the stream with `XREADGROUP`. Retry logic with dead-letter stream.

2. **Week 2**: Add idempotency key generation (`sha256(notification_type + event_id)`) in the producer and deduplication in billing consumers backed by a PostgreSQL `notification_dedupe` table. Wire up metrics (stream length, consumer lag, retry counts) to Datadog/Prometheus.

3. **Q3**: Prototype WebSocket push using Redis Pub/Sub alongside the main stream. Workers publish to a Pub/Sub channel; WebSocket server subscribes and fans out to connected clients.

4. **Ongoing**: Monitor memory usage and stream length. Adjust `MAXLEN` and add a background archiver to S3 for audit trail retention if needed.

---

## Revisit Conditions

Re-evaluate this decision if any of the following become true:

- Throughput exceeds 50,000 notifications/second at peak.
- The team grows to 10+ engineers, including an infrastructure specialist.
- Retention requirements shift to weeks or months of replayable history.
- The organization adopts Kafka for a higher-priority use case (e.g., event sourcing, CDC pipelines), making it available as shared infrastructure.
