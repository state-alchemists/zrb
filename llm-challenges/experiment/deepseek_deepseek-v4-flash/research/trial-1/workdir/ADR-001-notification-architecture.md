# ADR-001: Notification Subsystem — Async Message Broker

**Status:** Proposed

---

## Context

The notifications module (email + webhook delivery) runs synchronously inside the Flask HTTP request cycle. This creates four interconnected problems:

1. **Request timeouts** — average notification adds 800ms to response time, spiking to 8s at peak.
2. **Silent failures** — a dead SMTP relay or webhook endpoint drops the notification unceremoniously.
3. **Cascading failures** — slow webhook endpoints exhaust the connection pool and take down unrelated features (two incidents this year).
4. **No delivery guarantees** — billing-critical notifications (trial expiry, payment failure) require exactly-once semantics but have no protection today.

We need to decouple notification production from delivery. The message broker must support:

- At-least-once delivery, with exactly-once for billing events
- Retry with exponential backoff and a dead-letter queue
- Consumer groups for parallel processing
- Message ordering within a task-level scope
- A path toward real-time WebSocket push within two quarters
- 10× traffic growth (~5,000 req/s peak) without re-architecting

### Constraints

| Constraint | Detail |
|---|---|
| **Team** | 6 engineers (3 senior, 3 mid), no dedicated infrastructure engineer |
| **Existing infra** | Redis already in production (session storage, rate limiting) |
| **Kafka experience** | Zero on the team |
| **Setup window** | Must deliver value within two weeks |
| **Budget** | Modest — managed Confluent Cloud is not an option at full scale |
| **Billing semantics** | Exactly-once for billing notifications is a hard requirement |

---

## Decision

**Use Redis Streams.**

Redis Streams is the correct choice for this team, at this stage of the system, under these constraints. We will run it on our existing Redis infrastructure (scaled appropriately) and build consumer workers in Python using `redis-py`'s `XReadGroup` API.

### Justification

**1. Existing infrastructure eliminates setup risk.** Redis is already deployed, monitored, and understood by the team. Adding streams is a configuration change and a memory-sizing exercise — not a new infrastructure project. Kafka would require provisioning a ZooKeeper/KRaft ensemble, tuning broker and JVM parameters, deploying monitoring (Kafka Exporter, JMX), and establishing backup procedures. That timeline alone exceeds the two-week constraint.

**2. Team capability matches the tool's complexity.** Redis Streams' surface area is small: `XADD`, `XREADGROUP`, `XACK`, `XCLAIM`, `XPENDING`, `XDEL`. A mid-level engineer can be productive in a day. Kafka's surface area (topics, partitions, offsets, consumer groups, rebalancing protocols, exactly-once transactions, schema registry) requires weeks to internalize and months to operate confidently. With no dedicated infra engineer, adopting Kafka means every on-call rotation becomes a Kafka-on-call rotation — a risk multiplier this team cannot absorb.

**3. Throughput headroom is sufficient.** Redis benchmarks show 100,000+ messages/second through a single Stream on modest hardware (4 vCPU, 8 GB RAM). Our peak of 500 req/s today, even at 10× growth (5,000 req/s), is well within that envelope — each request generates 1–3 notification events at most, for a peak throughput of ~15,000 msg/s. We can handle this comfortably on a single Redis node with a RAM allocation of 4–8 GB for stream buffers, far below the memory budget of a moderately sized instance (e.g., AWS ElastiCache r7g.large).

**4. Consumer group semantics map cleanly to our workload.** `XREADGROUP` with the `>` operator delivers unacknowledged messages across N consumer processes. The PEL (Pending Entry List) tracks messages delivered but not yet acknowledged. `XCLAIM` lets any consumer take over messages from a failed peer after a visibility timeout — a direct analogue of Kafka's consumer group rebalancing without the complexity of cooperative/sticky partition assignment protocols. Our mid-level team will understand this model immediately.

**5. Exactly-once for billing is achieved the same way with either tool.** Kafka's exactly-once semantics (idempotent producer + transactions) eliminate duplicate *production* but do not guarantee duplicate-*free consumption* — the consumer still needs idempotency keys or two-phase commit between the topic offset and the processing side effect. Redis Streams provides at-least-once delivery naturally; exactly-once is achieved at the application layer by making billing consumers idempotent (deduplication against a unique `notification_id` in PostgreSQL). The complexity of this pattern is identical regardless of which broker you pick, so neither tool has a meaningful advantage here. We must build idempotent consumers regardless.

**6. WebSocket push integration is simpler with Redis.** Redis Pub/Sub (already in the same process) can bridge stream events to WebSocket connections without additional infrastructure. Kafka would require Kafka Connect, a dedicated bridge service, or embedding a Kafka client in the WebSocket server — all of which add operational surface area and latency.

**7. Operational cost is a fraction of Kafka.** Redis Streams is memory-bound by design. We allocate a stream buffer, set `MAXLENGTH` or `MINID` to cap retention, and let the backlog age out naturally. Kafka brokers page aggressively to disk, requiring careful management of disk I/O, retention policies, and compaction. With no infrastructure engineer on the team, every system call, page cache tuning, and disk-space alert that fires at 2 AM for Kafka is an escalation with no clear owner. Redis' operational profile — set maxmemory, pick an eviction policy, monitor fragmentation ratio — is already part of our runbook.

---

## Consequences

### Positive

- **Week 1 deliverable.** Streams can be in production handling async notifications within the first sprint. Kafka would require 2–4 weeks for cluster provisioning alone.
- **Zero new infrastructure.** We scale up the existing Redis instance rather than provisioning, networking, and securing a new cluster.
- **Familiar failure modes.** Redis issues (memory pressure, slow commands, replication lag) are known to the team. Kafka failure modes (unclean leader election, ISR shrinkage, log truncation, rebalancing storms) are not.
- **Cheap at this scale.** The additional Redis memory for stream buffers costs tens of dollars per month, not the hundreds or thousands of Kafka cluster nodes or MSK provisioned throughput.
- **Good-enough ordering.** Streams guarantee total ordering within a single stream entry. Task-scoped ordering (e.g., "assignment event before completion event for task X") is achieved by routing all events for a given `task_id` or `project_id` to the same stream via a hash-based sharding strategy.
- **Built-in retry mechanism.** The PEL naturally serves as a retry queue — unacknowledged messages remain pending until claimed by a consumer. We layer exponential backoff by checking `XPENDING` idle time before processing, or by moving failed messages to a dedicated dead-letter stream after N retries.

### Negative

- **Memory-bound retention.** Streams live in RAM. Long retention periods (days/weeks) for replay or analytics consume expensive memory. We mitigate with `MAXLENGTH ~100k` and archive historical notification records to PostgreSQL on acknowledgment. If long-term event replay becomes a hard requirement, we revisit Kafka.
- **No built-in exactly-once at the broker level.** Unlike Kafka's transactional API, Redis Streams provides no native exactly-once guarantee. As discussed above, this is neutral in practice because consumer-side idempotency is required regardless — but it bears repeating that the team must implement deduplication discipline in every billing consumer.
- **No schema registry.** Kafka integrates with Confluent Schema Registry or Apicurio for schema evolution. We manage schema versioning in the application code (e.g., Avro with a local schema store, or a `version` field in the JSON payload). For a 6-person team, this is simpler, not harder.
- **Sharding is manual.** Kafka handles partition assignment and rebalancing transparently. With Redis Streams, we must decide how to shard work across streams (one global stream, one per task, one per project). We will start with a single stream and N consumer processes, then move to a hash-slot strategy (consumer groups partitioned by `task_id % N`) if single-stream throughput becomes the bottleneck. This is a valid concern but not an immediate one — benchmarks show a single stream handles 100k+ msg/s.
- **Less ecosystem tooling.** Kafka's ecosystem (Kafka Connect, ksqlDB, MirrorMaker, schema registry, REST proxy) is vast. Redis Streams' ecosystem is redis-py and a few community libraries. For a notification pipeline, Connect sources/sinks to S3 or data warehouses are future concerns — we can add those in a data-lake project when the need arises, and at that point Kafka may become justified.

---

## Alternatives Considered

### Apache Kafka (Rejected)

**Why it was seriously considered.** Kafka is the industry standard for event streaming. Its strengths — disk-based retention, native exactly-once semantics, transparent partition rebalancing, massive ecosystem — are well-suited to high-volume, multi-consumer event pipelines.

**Why it was rejected.** The decision is not about technical merit; it is about *readiness fit*:

- **Team inexperience dominates.** A 6-person team with zero Kafka experience cannot responsibly operate a production Kafka cluster within two weeks. Learning, provisioning, tuning, and monitoring Kafka reliably takes 4–8 weeks even with experienced engineers. Every broker restart, partition rebalance, or ISR issue becomes a fire drill with no domain expert on staff.
- **Infrastructure cost is non-trivial at any scale.** A 3-broker Kafka cluster on AWS (m6g.large or equivalent) costs ~$400–700/month before EBS storage, data transfer, and monitoring. MSK (Amazon's managed Kafka) starts at ~$300/month for a minimal 2-broker cluster but requires provisioned throughput that scales cost with traffic. Managed Confluent Cloud is explicitly out of budget. By contrast, upgrading our existing Redis instance to a size adequate for stream buffers costs $50–150/month.
- **Setup timeline violates the two-week constraint.** Provisioning a Kafka cluster: 2–4 days. Tuning broker configs, producer/consumer clients, monitoring, alerting: 1–2 weeks. Validating exactly-once configuration: additional days. Training the team: ongoing. Redis Streams: one afternoon to test, one day to deploy to staging, two days of production validation.
- **Overkill for the throughput.** Kafka excels at millions of messages/second with multiple replay consumers and long-term retention. Our peak of ~15,000 msg/s does not demand Kafka's horizontal scaling properties. Adopting Kafka for this workload today is paying a complexity premium for capacity we may never use.
- **WebSocket integration requires a bridge.** Kafka does not natively support Pub/Sub push semantics. We would need to build or deploy a bridge service (e.g., Kafka to WebSocket over Server-Sent Events) — additional infrastructure and latency.

**When to revisit Kafka.** If notifications grow to include:
- A data-intensive event-sourcing log with months of retention and multiple replay consumers
- 200,000+ msg/s sustained throughput
- A dedicated platform/operations engineer on the team

...then a migration to Kafka (or another disk-backed log) is warranted. The stream abstraction is similar enough that the migration path is well-understood: a Kafka source connector or a dual-write adapter during a transition window.

### PostgreSQL LISTEN/NOTIFY (Not seriously considered)

PostgreSQL's `LISTEN/NOTIFY` was rejected immediately because it lacks consumer groups, persistent queue semantics, and any retention — a disconnected consumer loses all notifications. It is suitable for cache invalidation, not a retry-capable notification pipeline.

### Amazon SQS / SNS (Not seriously considered)

Managed queue services offload operational burden, which is attractive for a small team. However, SQS lacks ordered delivery guarantees for FIFO queues at scale (3,000 TPS cap for FIFO; no ordering for standard queues), and SNS/WebSocket integration requires additional bridging. The team is already on AWS, so this is a reasonable future alternative — but given the existing Redis investment and the ordering requirements, Redis Streams offers better control at lower cost.

---

## Decision Timeline

| Milestone | Target |
|---|---|
| Staging deployment of Redis Streams producer + 1 consumer | Week 1 |
| Production deployment for non-critical notifications | Week 2 |
| Billing consumer with idempotency deduplication | Week 3 |
| Dead-letter queue + backoff implementation | Week 4 |
| WebSocket push layer (Redis Pub/Sub bridge) | Q2 |
| Load test at 5,000 msg/s; evaluate single-stream ceiling | Q2 |

---

## References

- Redis Streams documentation: https://redis.io/docs/data-types/streams/
- Kafka exactly-once semantics: https://www.confluent.io/blog/exactly-once-semantics-are-possible-heres-how-apache-kafka-does-it/
- Existing Redis configuration: `infra/redis/redis.conf` (session + rate limiting)
- Current notification code: `src/notifier/` (to be refactored into producer + consumer)
