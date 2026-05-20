# ADR-001: Notification Subsystem Architecture

**Status:** Proposed

---

## Context

The Notifier subsystem of our SaaS project management platform sends email and webhook notifications when tasks are updated, assigned, or completed. Today, notifications are sent synchronously inside the HTTP request cycle, which causes four systemic problems:

1. **Request timeouts** — average 800ms latency, spiking to 8s during peak hours (500 req/s), degrading user-facing response times.
2. **Silent failures** — a downed email provider or webhook endpoint causes the notification to be dropped with no retry or dead-letter queue.
3. **Cascading failures** — two incidents this year where slow webhook endpoints exhausted the PostgreSQL connection pool, taking down unrelated features.
4. **No delivery guarantees** — billing-critical notifications (trial expiry, payment failure) require exactly-once delivery; the current system offers no guarantees whatsoever.

The platform serves 85,000 monthly active users, creates ~2M tasks/month, and must handle 10x traffic growth without a re-architecture. An async notification subsystem is non-negotiable.

**Key constraints:**
- Engineering team of 6 (3 senior, 3 mid-level), no dedicated infrastructure engineer
- Redis already in production (session storage, rate limiting)
- Zero Kafka experience on the team today
- Maximum 2 weeks of setup/migration before delivering value
- Modest budget — cannot afford managed Confluent Cloud at full scale
- Must maintain exactly-once semantics for billing notifications

---

## Decision

**Adopt Redis Streams** as the notification message broker.

The HTTP request cycle will produce notification messages to Redis Streams. A pool of background workers (Python processes) will consume these streams via consumer groups, handle retries with exponential backoff, and route dead-letter notifications to a dedicated stream for manual inspection. Billing notifications will carry idempotency keys stored in Redis itself for exactly-once processing.

We will run the stream on the existing Redis instance, using a separate logical database and configuring `maxmemory-policy: noeviction` to prevent data loss.

---

## Consequences

### Pros

- **Leverages existing infrastructure.** Redis is already deployed, monitored, and understood by the team. Adding streams requires no new servers, no new daemons, and no new vendor relationships. Operational risk is near-zero.

- **Rapid time-to-value.** A working async notification pipeline with consumer groups, retries, and dead-letter routing can be built and deployed within one week. This satisfies the 2-week constraint by a comfortable margin.

- **Appropriate throughput ceiling.** Redis Streams comfortably handles 100,000+ operations per second on modest hardware. At 500 req/s peak today and a 10x target of 5,000 req/s, we will use roughly 5% of Redis Streams' practical capacity. There is no throughput risk at our scale.

- **Natural path to WebSocket push.** Adding real-time push (required within 2 quarters) pairs naturally with Redis — WebSocket servers consume from a shared stream and broadcast to connected clients via Redis Pub/Sub. No additional broker is needed.

- **Strong ordering within streams.** Streams preserve insertion order. Within a single notification stream, messages are processed in FIFO order, which is sufficient for our use case (per-task notification ordering).

- **Exactly-once via idempotency keys.** Billing notifications carry a unique idempotency key (e.g., `billing:trial-expired:user-123:2026-05-20`). The consumer checks a Redis key before processing and skips duplicates. Because we already run Redis, this pattern costs zero additional infrastructure.

- **Consumer groups manage distribution.** Redis consumer groups (`XREADGROUP`) distribute messages across worker instances with automatic tracking of pending entries. Workers that crash mid-process do not lose messages — pending entries are claimed by other workers after a timeout.

- **Operational simplicity.** A team of 6 with no dedicated SRE can manage this. Troubleshooting Redis Streams requires no specialized knowledge beyond existing Redis expertise.

### Cons

- **No native exactly-once.** Unlike Kafka (which provides exactly-once semantics via transactions and idempotent producers), Redis Streams requires application-level idempotency keys. This is a solved pattern but adds implementation responsibility to the team.

- **In-memory with disk persistence.** Redis Streams live primarily in memory. While RDB/AOF snapshots provide durability, a catastrophic failure before the latest snapshot could lose recently-produced messages. At our volume (~2M messages/month ≈ 0.77 msg/s average), the risk window is small but nonzero. Mitigation: configure `appendfsync everysec` and monitor Redis memory headroom.

- **Consumer rebalancing is manual.** Unlike Kafka's automatic partition rebalancing, Redis consumer group rebalancing requires explicit management when worker instances join or leave. For a 6-person team running a handful of workers, this is a manageable operational detail, not a blocker.

- **No built-in stream compaction.** Kafka's log compaction purges obsolete records while keeping the latest value per key. Redis Streams do not compact — you must manage stream trimming manually via `XTRIM` or set `MAXLEN`. For our notification workload (messages are consumed and then discarded), compaction is unnecessary.

- **Maturity gap.** Kafka has a richer ecosystem for stream processing (Kafka Streams, ksqlDB, connectors). Redis Streams are younger and the tooling is thinner. For a pure notification pipeline (produce → consume → deliver), Redis Streams covers every requirement. If we later need complex event processing (joining streams, windowed aggregations), we may outgrow Redis Streams. At our scale and team size, that future requirement is hypothetical.

---

## Alternatives Considered

### Apache Kafka

**Why it was seriously considered.** Kafka is the industry standard for async event pipelines. It offers:

- **Native exactly-once semantics.** Kafka's transaction API (KIP-98) and idempotent producer provide exactly-once delivery without application-level idempotency keys. For billing notifications, this removes implementation burden.
- **Durable disk-based storage.** Kafka persists all messages to disk with configurable retention, surviving Redis-level failures without data loss.
- **Automatic consumer rebalancing.** Kafka handles partition assignment changes transparently when consumers join or leave a group.
- **Higher throughput ceiling.** Kafka routinely handles millions of messages per second. At 10x growth (5,000 msg/s peak), we would use less than 1% of Kafka's practical capacity.

**Why it was rejected.** Despite Kafka's technical strengths, four constraints make it the wrong choice for this team, at this time:

1. **Operational complexity is incompatible with a 6-person team with no dedicated infrastructure engineer.** Running Kafka requires managing ZooKeeper or KRaft controllers, tuning JVM heap and GC, configuring replication factors and ISR settings, and monitoring broker disk usage and lag. Each of these is a known discipline in the Kafka ecosystem but an unknown one for this team. A misconfigured Kafka cluster (e.g., insufficient replication factor, unclean leader election) can lose data silently — exactly the outcome we are trying to prevent. One of our incidents was caused by connection pool exhaustion; Kafka doubles the surface area with its own connection pool and thread model.

2. **Time-to-value exceeds the 2-week constraint.** Even with managed Amazon MSK (which starts at ~$100/month for the smallest cluster), the team would need to learn Kafka's consumer API, understand partitioning strategies, set up monitoring for broker health and consumer lag, and adapt their current synchronous Python code to an async producer/consumer pattern using a library (confluent-kafka or aiokafka) none of them have used. Realistically, this is a 3-6 week ramp-up for the first production notification. We do not have that runway.

3. **Budget eliminates managed Kafka options.** The modest budget rules out Confluent Cloud at full scale. Self-hosted Kafka on EC2 is cheaper but imposes the operational burden described above. Amazon MSK (serverless or provisioned) is viable but still adds $100-300/month plus the hidden cost of team time spent learning and operating it. Redis Streams costs zero additional dollars — we already pay for the Redis instance.

4. **Kafka is over-engineered for the workload.** At 500-5,000 messages per second with simple produce → consume → deliver semantics, Kafka brings a distributed commit log, partition rebalancing protocols, and a storage layer designed for multi-terabyte retention. We need a queue with retries, not an event store. Redis Streams matches the problem's complexity without adding architectural entropy.

---

## Recommendation

Use **Redis Streams**. Build an async notification pipeline that produces messages to a Redis stream, consumes them via `XREADGROUP` in a pool of Python workers, implements exponential-backoff retry with a configurable max retry count, routes exhausted messages to a dead-letter stream, and enforces exactly-once delivery for billing notifications via idempotency keys stored in Redis itself.

This decision buys down risk immediately, leverages existing team knowledge and infrastructure, and defers the complexity of a distributed log system until our traffic, team, and requirements clearly demand it. If we grow past Redis Streams' capabilities (unlikely below ~50,000 msg/s), the producer/consumer abstraction is easily swapped — both Kafka and Redis Streams share the same conceptual model of producers, consumers, consumer groups, and offsets. Migration at that point is a tactical swap, not an architectural reinvention.

**Target delivery: a dead-letter retry pipeline in production within 7 calendar days.**
