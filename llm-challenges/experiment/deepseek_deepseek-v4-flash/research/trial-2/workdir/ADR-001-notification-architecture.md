# ADR-001: Notification Subsystem — Async Architecture

**Status:** Proposed

---

## Context

The notification subsystem (email + webhook delivery) runs synchronously inside the HTTP request cycle of a Python/Flask monolith. As the platform has grown to 85,000 MAU and ~500 req/s peak, this coupling has caused request timeouts (800 ms avg, 8 s spikes), silent failures on downstream outages, connection-pool exhaustion cascading into unrelated features, and zero delivery guarantees for billing-critical events.

We need to decouple notification dispatch from request handling with an async message broker. The broker must support:

- **Async dispatch** — push notifications to a queue, return the HTTP response immediately.
- **Retry with exponential backoff** — transient failures should be retried, not dropped.
- **At-least-once delivery** for all events; **exactly-once processing** for billing notifications (trial expiry, payment failure).
- **Consumer grouping** for horizontal scaling across our 4 web servers.
- **WebSocket push** planned within two quarters (event stream → real-time frontend updates).
- **10× traffic growth** without re-architecting the queue layer.

**Constraints that drive this decision:**

- Engineering team: 6 people (3 senior, 3 mid-level). No dedicated infrastructure engineer. No prior Kafka experience.
- Redis is already in production for session storage and rate limiting.
- Budget is modest — managed Confluent Cloud is out of scope at full scale.
- The solution must deliver value within 2 weeks of starting implementation.
- Exactly-once semantics for billing notifications is a hard requirement.

---

## Decision

**Use Redis Streams as the notification message broker.**

Adopt the following architecture:

1. **Producers** (inside Flask request handlers) push notification events to Redis streams via `XADD`. Each event carries a unique, deterministic `event_id` (ULID scoped to notification type + payload hash).
2. **Consumer groups** (`XREADGROUP`) run as background workers on the existing web servers — one per consumer group per stream. Workers acknowledge messages after successful dispatch (`XACK`) and claim abandoned pendings (`XAUTOCLAIM`) on startup or timer.
3. **Retry with backoff** — on failure, workers leave the message pending (or add it to a retry stream with a timestamp-based scoring). A dead-letter stream receives events exceeding the retry limit.
4. **Exactly-once processing for billing** — consumers check a Redis Set or stream-scoped deduplication key (`SISMEMBER processed_<event_id>`) before processing. This gives idempotent consumers with exactly-once *outcome* semantics without depending on the broker for transactional guarantees.
5. **WebSocket push** — a separate reader on the same streams publishes to Redis Pub/Sub for real-time fanout to WebSocket server processes.

---

## Consequences

### ✅ Benefits

| Concern | How Redis Streams addresses it |
|---------|--------------------------------|
| **Async dispatch** | `XADD` is O(1), sub-millisecond, non-blocking. HTTP handlers return immediately. |
| **Retry & backoff** | Pending entries (no `XACK`) are re-delivered to consumers. Dead-letter streams cap retries. |
| **At-least-once delivery** | Consumer groups guarantee each message is delivered to at least one consumer. |
| **Exactly-once billing** | Consumer-side idempotency (dedup via `event_id`) provides exactly-once *processing* without broker-level transactions. This is the pragmatic industry standard — true distributed exactly-once end-to-end is unachievable without idempotent consumers anyway. |
| **Consumer groups** | `XREADGROUP` with `XAUTOCLAIM` provides partition-free concurrency — simpler than Kafka partition management. |
| **WebSocket push** | Redis Pub/Sub (already available) reads from the same streams for real-time fanout. |
| **Existing infrastructure** | Zero new stateful services. Redis already runs in production — the team knows its operational profile. |
| **Time to value** | A working prototype can ship in 2–3 days. Production-ready within the 2-week constraint. |
| **10× growth (5 k req/s)** | Redis Streams handles 100 k+ msg/s on modest hardware. Memory capacity planning (below) is the real constraint, not throughput. |
| **Team size** | No new skill to learn. The 6-person team can own the entire stack. |

### ⚠️ Trade-offs & Mitigations

| Risk | Mitigation |
|------|------------|
| **Memory-bound storage** — streams live in RAM; backlog grows unbounded if consumers fall behind. | Enforce `MAXLEN ~ 100k` per stream to bound memory. Monitor consumer lag with `XINFO GROUPS`. Alert if lag exceeds 10k entries. |
| **No native replay for cold consumers** — evicted entries are gone. | Dead-letter and billing events are forwarded to long-term storage (PostgreSQL `notification_audit` table) within the same worker pipeline. |
| **No partition rebalancing** — unlike Kafka, Redis Streams don't auto-rebalance consumers across shards. | Not needed at our scale. A single stream with multiple consumers in a group distributes entries round-robin. If partitioning becomes necessary later, shard by `user_id % N` across N streams — a data-plane change, not a control-plane one. |
| **Consumer lag under high load** — `XREADGROUP` is polling-based, unlike Kafka's push. | Use `BLOCK` with a short timeout (1–2 s) and `COUNT` to batch. Polling overhead is negligible below 10 k msg/s. |
| **Redis failover** — unacknowledged pending messages survive failover only if AOF + fsync is configured. | Enable appendfsync everysec on the Redis instance. Streams persist to AOF; `XAUTOCLAIM` rebalances pendings after a failover. |
| **No exactly-once from the broker** — Redis Streams offer at-least-once delivery. | This is acceptable. As noted above, idempotent consumers are required for exactly-once outcome regardless of broker choice. |

---

## Alternatives Considered

### Apache Kafka

**Why we evaluated it:** Kafka is the de facto standard for event streaming at scale. It offers durable log-based storage, strong partition ordering, native rebalancing, configurable retention, and Kafka Transactions for exactly-once semantics. For an organization with the operational maturity and scale to justify it, Kafka is the superior long-term platform.

**Why we rejected it (for now):**

| Constraint | Why Kafka fails |
|------------|-----------------|
| **No Kafka experience on the team** | Learning curve for Kafka is steep — producers, consumer groups, partitioning, offsets, rebalancing, topic configuration, ZooKeeper/KRaft, monitoring. Realistic timeline to production-ready: 4–6 weeks for a team of 6 without prior experience. This violates the 2-week constraint. |
| **No dedicated infrastructure engineer** | Kafka requires dedicated cluster management — broker tuning, partition rebalancing, ISR monitoring, log compaction, JMX metrics, disk sizing. A 6-person team building product features cannot absorb this operational burden. |
| **Budget constraints** | Self-hosted Kafka on 3+ EC2 instances with EBS volumes costs $500–1,500/mo. Managed Confluent Cloud starts at ~$200/mo but scales quickly. This competes directly with limited infrastructure budget. |
| **Overkill for the scale** | At 500 req/s (5 k at 10×), Kafka's advantages (100 k+ msg/s, multi-year retention, stream processing) are not exercised. The operational cost buys capacity we won't use. |
| **Existing Redis investment** | We already run Redis. Adding Kafka means operating two stateful systems instead of deepening one. More blast radius, more runbooks, more on-call burden. |

**When to revisit:** If our event throughput exceeds 50 k msg/s, or if we need multi-source event sourcing with replay across months of history, Kafka should be re-evaluated. At that point the team size and operational maturity will likely have grown accordingly.

### RabbitMQ

**Why we evaluated it:** RabbitMQ is a mature AMQP broker with dead-letter exchanges, retry queues, and a familiar routing model. It excels at point-to-point work queues.

**Why we rejected it:** RabbitMQ adds another stateful service to operate and provides a weaker consumer-group model than either Redis Streams or Kafka. For exactly-once delivery it requires publisher confirms + consumer acknowledgements — same as Redis Streams, but with a new Erlang runtime to manage. It offers no natural path to the planned WebSocket push requirement (no Pub/Sub substrate), which would require a separate solution. Redis Streams achieves all the same outcomes with zero additional infrastructure.

### PostgreSQL LISTEN/NOTIFY + Job Table

**Why we evaluated it:** Zero new infrastructure — the existing PostgreSQL instance handles everything.

**Why we rejected it:** `LISTEN/NOTIFY` has no persistence, no consumer groups, and a hard payload size limit (8,000 bytes). A job table with a worker poll loop (`SELECT ... FOR UPDATE SKIP LOCKED`) would work but adds table-bloat pressure on the database, requires periodic vacuum maintenance, and couples queue performance to PostgreSQL query throughput. At 500 req/s the query volume alone creates contention with the primary workload. This pattern works for background job queues at smaller scale but is inappropriate for a high-throughput event pipeline with delivery guarantees.

---

*Decision date: 2026-05-22*
