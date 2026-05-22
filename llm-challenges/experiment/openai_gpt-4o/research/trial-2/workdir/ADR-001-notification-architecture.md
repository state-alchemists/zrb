# ADR-001: Notification Subsystem — Asynchronous Processing Architecture

**Status:** Proposed

---

## Context

The notification subsystem (email + webhook delivery on task create/update/assign/complete) currently runs synchronously inside the Flask HTTP request cycle. This causes four concrete problems:

1. **Request timeouts** — average 800ms latency, spiking to 8s at peak, because notification delivery blocks the response.
2. **Silent failures** — a failed email provider or webhook endpoint drops the notification with no retry or dead-letter path.
3. **Cascading failures** — two incidents this year where a slow webhook caused connection pool exhaustion, taking down unrelated HTTP endpoints.
4. **No delivery guarantees** — billing-critical notifications ("trial expired", "payment failed") need at-least-once delivery with exactly-once semantics, but the current fire-and-forget design provides neither.

The required solution must: decouple delivery from the request cycle, support retry with exponential backoff, guarantee at-least-once delivery (exactly-once for billing), lay groundwork for WebSocket push within two quarters, and scale to 10x current traffic.

**Constraints:**
- Engineering team of six (3 senior, 3 mid-level), no dedicated infrastructure engineer
- Redis already in production for session storage and rate limiting
- Zero Kafka experience on the team
- Must deliver value within 2 weeks of starting implementation
- Budget does not support managed Confluent Cloud at full scale
- Must handle exactly-once semantics for billing notifications

---

## Decision

**Adopt Redis Streams** as the notification message broker and processing backbone.

Redis Streams provides the necessary primitives — consumer groups, pending entry lists (PEL), message acknowledgements, and blocking reads — to build a reliable async notification pipeline on infrastructure we already operate.

### Architecture Overview

```
HTTP Request → Flask Handler → XADD to Stream
                                    │
                         ┌──────────┴──────────┐
                         │  Consumer Group      │
                         │  (notif-workers)     │
                         └──────────┬──────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
            Email Worker                      Webhook Worker
            (XREADGROUP)                      (XREADGROUP)
                    │                               │
                    ▼                               ▼
            SendGrid/SES                   Target Webhook
                    │                               │
            ┌───────┴───────┐               ┌───────┴───────┐
            │  Success →    │               │  Success →    │
            │  XACK         │               │  XACK         │
            │  Failure →    │               │  Failure →    │
            │  XPENDING +   │               │  XPENDING +   │
            │  CLAIM (retry)│               │  CLAIM (retry)│
            └───────────────┘               └───────────────┘
                    │                               │
                    ▼                               ▼
            Dead-letter stream              Dead-letter stream
            (after N retries)               (after N retries)
```

### Exactly-Once Strategy for Billing

Redis Streams alone provides at-least-once delivery via PEL tracking. For exactly-once on billing events, we combine:

1. **Idempotency key** stored in the stream message (e.g., `billing_event:user_id:tier_change:timestamp`).
2. **Dedup table** in PostgreSQL (`notification_dedup` with unique constraint on idempotency_key).
3. **Transactional insert**: the consumer does `INSERT ... ON CONFLICT DO NOTHING` before dispatching. If the key exists, the notification was already processed — skip.
4. **XACK only after the DB insert succeeds**, so a crash between processing and acknowledgement re-delivers the message. The dedup table catches the replay.

This pattern gives end-to-end exactly-once without requiring the broker itself to provide it — a pragmatic approach that matches the team's existing PostgreSQL expertise.

---

## Consequences

### Benefits

- **No new infrastructure.** Redis is already in production. Adding streams uses an existing operational surface area — no new ZooKeeper, no new broker VMs, no new monitoring.
- **Fast time-to-value.** A working prototype (Flask handler that XADDs to a stream + a Python worker that XREADGROUPs and delivers) can ship in days. Within 2 weeks we can have retry, dead-letter, and monitoring in place.
- **Leverages existing team knowledge.** The team already manages Redis (config, persistence, monitoring). Learning the Streams API is a days-long investment, not a weeks-long one.
- **Consumer groups map cleanly to our problem.** Each notification type (email, webhook) gets its own consumer group with multiple workers for parallelism. Pending entry list provides automatic re-delivery on consumer failure.
- **Sufficient at current and 10x scale.** At 500 req/s peak (~50–150 notification events/s after dedup), Redis on a single instance handles this trivially. Even at 10x (5,000 req/s, ~1,500 events/s), a single `m6g.large` Redis instance with AOF persistence is comfortable. At 100x we'd reconsider, but the 10x target is well within range.
- **Enables WebSocket push naturally.** The same stream can feed a WebSocket broadcast worker using `XREAD` with `BLOCK`. No separate pub/sub infrastructure needed — though for fan-out we'd likely add a dedicated stream or use Redis Pub/Sub alongside.
- **Memory cost is predictable.** With `MAXLEN ~ 100,000` and trimming, the stream stays bounded. At ~500 bytes/message, that's ~50MB of RAM — negligible against our existing Redis footprint.

### Trade-offs

- **Not a Kafka-scale system.** If the business grows to millions of events per second, Redis Streams will require sharding across a Redis Cluster, which is operationally complex. Kafka handles that scale natively. For our stated 10x target, this is not a concern.
- **Exactly-once is application-layer, not broker-native.** Redis Streams does not offer Kafka-style transactional exactly-once. Our dedup-table approach works but requires discipline: every billing consumer must check the dedup table before acting, and the XACK must follow the DB commit. Miss this ordering and duplicates appear.
- **Message retention is bounded.** Unlike Kafka's disk-based log with configurable retention, Redis keeps streams in memory (optionally persisted to AOF). If we need to replay months of events for auditing, we'd need a separate archival strategy (e.g., dump stream to S3 periodically). At our scale this is a documentation item, not a blocker.
- **Consumer rebalancing is manual.** When adding or removing workers from a consumer group, Redis doesn't auto-rebalance partitions. We'd need to monitor pending counts and manually CLAIM orphaned messages. For 2–4 workers per consumer group this is manageable; for 20+ it becomes a pain point.
- **Single-point-of-failure risk on one Redis instance.** Adding a replica + Redis Sentinel (or using ElastiCache) mitigates this. We already run Redis in production, so this is an incremental improvement, not a new burden.

---

## Alternatives Considered

### Apache Kafka

**Why it was considered:** Kafka is the industry standard for event streaming. It provides:
- Disk-based persistence with configurable retention (unlimited by memory)
- Native exactly-once semantics via idempotent producers + transactions
- Auto-rebalancing consumer groups
- Throughput in the hundreds of thousands of messages per second
- Built-in log compaction for keyed event replay

**Why it was rejected:**

1. **Operational complexity exceeds team capacity.** A production Kafka deployment requires at minimum 3 brokers (for replication factor 3), ZooKeeper or KRaft, a schema registry, and a monitoring stack (JMX exporters, Burrow, Cruise Control). The team of 6 with no dedicated infrastructure engineer and zero Kafka experience would take 4–8 weeks just to stand up a production-grade cluster and learn the operational patterns. This violates the 2-week value constraint.

2. **Budget prohibits the easy path.** Managed Kafka (Confluent Cloud, MSK) is the sensible choice for teams without Kafka expertise. MSK pricing starts at ~$0.50/hr per broker (~$1,100/mo for 3 brokers) and Confluent Cloud is higher at scale. The project's modest budget precludes this. Self-hosting Kafka means owning the operational toil.

3. **Overkill for the current scale.** Kafka's design assumes high-throughput, multi-subscriber event buses. At 500 req/s producing ~50–150 notification events/s, we would use a fraction of what Kafka offers while paying the full complexity tax. This is a mismatch.

4. **Delays WebSocket push integration.** Adding real-time push requires either mirroring events to Redis Pub/Sub anyway (since Kafka clients are heavier for browser delivery) or investing in Kafka-to-WebSocket gateways. Redis Streams allows a single infrastructure layer for both persistent queuing and real-time broadcast.

**Verdict:** Kafka is the right choice for a larger team, higher scale, or an event-sourced architecture — none of which describe our current situation. A future migration to Kafka is possible if the event volume outgrows Redis Streams (e.g., 50x+ growth or an event-sourcing mandate), but there is no benefit to adopting it now.

### Amazon SQS + SNS

**Why it was considered:** Managed, serverless, near-zero operational overhead for the team.

**Why it was rejected:** Vendor lock-in to a single provider. SQS does not natively support consumer replay (messages are deleted on acknowledgement), making exactly-once for billing harder without the dedup-table pattern anyway. More critically, it provides no foundation for the WebSocket push requirement — we'd still need a separate real-time layer. SNS can push to HTTP/S but adds cost per notification and has no built-in retry with exponential backoff beyond its own delivery policy. The combined SQS + SNS approach is functional but adds AWS spend and does not reduce architectural complexity compared to Redis Streams.

### Postgres Queue (SKIP LOCKED / pgq)

**Why it was considered:** Uses the database we already run. No new infrastructure. PostgreSQL `SELECT ... FOR UPDATE SKIP LOCKED` can implement a polling queue.

**Why it was rejected:** Polling a database table for notifications adds load on the primary PostgreSQL instance, which already handles all transactional workload. At 10x growth, this becomes a contention point. PostgreSQL lacked native pub/sub (outside of `NOTIFY`/`LISTEN`, which has no delivery guarantees and drops messages on connection loss) and provides no consumer group semantics, no PEL-style re-delivery, and no built-in retry mechanism. The application code to build these primitives on Postgres would take longer to write and debug than the 2-week window allows. Redis Streams provides all of these as first-class features.

---

## Implementation Plan (Summary)

| Phase | Time | Deliverable |
|-------|------|-------------|
| 0 | Week 1 | Flask handler writes notification events to a stream via XADD. Single `notif-worker` process reads via XREADGROUP, delivers emails. HTTP response no longer blocks. |
| 1 | Week 2 | Add dead-letter stream, retry loop (XPENDING + CLAIM with exponential backoff), monitoring dashboard (stream length, pending count). |
| 2 | Weeks 3–4 | Split into email and webhook consumer groups. Add dedup table for billing exactly-once. |
| 3 | Q2 | WebSocket push worker reading from a dedicated stream, broadcasting to connected clients. |

All phases build on the same Redis instance already in production.

---

## References

- Redis documentation on [Streams](https://redis.io/docs/latest/develop/data-types/streams/), [Consumer Groups](https://redis.io/docs/latest/develop/data-types/streams/#consumer-groups), [XPENDING](https://redis.io/docs/latest/commands/xpending/), [XCLAIM](https://redis.io/docs/latest/commands/xclaim/)
- Redis [PEL and message delivery guarantees](https://redis.io/docs/latest/develop/data-types/streams/#a-note-about-pending-entries)
