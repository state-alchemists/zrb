# ADR-001: Notification Subsystem — Message Broker Selection

**Status:** Proposed

---

## Context

The Notifier subsystem sends email and webhook notifications when tasks are created, updated, assigned, or completed on our SaaS project management platform (85k MAU, ~2M tasks/month, peak 500 req/s). These notifications are currently sent synchronously inside the Flask HTTP request cycle, causing:

- **Request timeouts**: average 800ms latency, spiking to 8s at peak.
- **Silent failures**: downstream email/webhook unavailability drops the notification permanently.
- **Cascading failures**: two incidents where a slow webhook endpoint exhausted the PostgreSQL connection pool.
- **No delivery guarantees**: billing-critical notifications (trial expiry, payment failure) need at-least-once delivery; exactly-once where feasible.

We must decouple notification dispatch from the request cycle into an async subsystem that supports retry with exponential backoff, consumer group semantics, and a path to real-time WebSocket push within two quarters. The solution must handle 10x current load without re-architecting.

### Non-negotiable constraints

| Constraint | Detail |
|---|---|
| Team size | 6 engineers (3 senior, 3 mid), no dedicated infra engineer |
| Existing infra | Redis already in production for session storage and rate limiting |
| Kafka experience | None on the team |
| Setup window | Must deliver value within 2 weeks |
| Budget | Modest — managed Confluent Cloud is out of reach |
| Exactly-once | Required for billing notifications |

---

## Decision

**Use Redis Streams** as the notification message broker. Consumer groups in a dedicated Redis instance (or a logical database on the existing Redis) will manage fan-out, acknowledgment, and retry. A companion dead-letter stream will capture messages that exhaust their retry budget.

### Architecture overview

```
HTTP Request
    │
    ▼
Flask App ──XADD──▶ Redis Stream (notification:events)
                        │
              ┌─────────┼─────────┐
              ▼         ▼         ▼
        Consumer  Consumer  Consumer
        (email)   (webhook) (ws:future)
              │         │
              ▼         ▼
         SendGrid    HTTP POST
           / \       (retry 3×)
          DLQ  DLQ
```

Each consumer operates within a **consumer group** (`notification:events:email`, `notification:events:webhook`) so each event is dispatched to exactly one consumer per group. The pending entries list (PEL) tracks unacknowledged messages; a periodic reaper (`XCLAIM`) reclaims messages from stalled consumers for retry.

---

## Consequences

### ✅ Pros

1. **Zero new infrastructure.** We already run Redis. No new cluster, no new vendor, no new credentials to rotate. The ops burden is unchanged.

2. **Fast time-to-value.** A working consumer group with retry and a DLQ can be implemented in 3–5 days. The 2-week constraint is met comfortably.

3. **Team familiarity.** Every engineer on the team has already worked with Redis. The Streams API (`XADD`, `XREADGROUP`, `XACK`, `XCLAIM`) has a small surface area — the entire protocol fits in a day of study.

4. **Adequate throughput.** A single Redis node handles ~100k msg/s for small payloads. Our current peak is 500 req/s; even at 10x (5000 req/s), we're at 5% of capacity. No partitioning or sharding is needed.

5. **Natural WebSocket bridge.** Redis Pub/Sub + Streams is a well-known pattern for real-time push. The same Redis cluster that holds notification streams can serve ephemeral Pub/Sub channels for live WebSocket delivery. This avoids a separate message broker for the Q2 WebSocket initiative.

6. **Consumer group semantics.** `XREADGROUP` provides at-least-once delivery within a group. The PEL tracks unacknowledged messages across consumer crashes — automatic redelivery with `XCLAIM` requires no additional infrastructure.

### ❌ Cons

1. **At-least-once, not exactly-once.** Redis Streams natively guarantees at-least-once. Exactly-once requires application-level idempotency (dedup key + PostgreSQL `UNIQUE` constraint or idempotency table in the consumer). This is achievable but must be explicitly built — it's not automatic.

2. **Message retention is bounded by memory.** Unlike Kafka, which stores messages on disk by time/size policy, Redis Streams use bounded-length streams (`MAXLEN`). Long-term event history must be persisted elsewhere. For our use case this is acceptable: the canonical event log is already in PostgreSQL (task updates are INSERTed/UPDATE'd there). The stream is a transient processing pipeline, not an audit store.

3. **No built-in rebalancing protocol.** When a consumer joins or leaves a group, Redis does not auto-rebalance partitions. New consumers must negotiate via `XREADGROUP`'s `>` ID, which works well when all consumers read from the same stream (no partitioning). If we ever need to shard across multiple streams, we must implement partition assignment ourselves.

4. **Scaling beyond a single node is manual.** Kafka scales horizontally by adding brokers and partitions — mostly transparent to consumers. Redis Streams on a single node handles 100k msg/s, but if we need to scale beyond that, we must manually shard across Redis nodes. At 10x (5000 req/s) this is unlikely to be necessary for 2–3 years.

---

## Alternatives Considered

### Apache Kafka (Rejected)

Kafka was seriously evaluated and has genuine strengths, but it is the wrong choice given our constraints.

**Strengths we weighed:**
- Native exactly-once semantics (EOS) via transactional producers/consumers.
- Durable, disk-based retention with configurable time/size policies — events can be replayed months later without any auxiliary storage.
- Proven 100k+ msg/s throughput per cluster with horizontal scaling.
- Strong partitioning and consumer rebalancing via the group coordinator protocol.

**Why we rejected it:**
- **Operational complexity is prohibitive for a 6-person team with no dedicated infra engineer.** Kafka requires managing a KRaft or Zookeeper ensemble, tuning `replica.fetch.max.bytes`, `log.retention.bytes`, `num.io.threads`, `queued.max.requests` — dozens of knobs. A misconfigured Kafka cluster is fragile and loses data silently. Our team has no Kafka experience; the learning curve alone would consume the 2-week setup window.
- **Infrastructure cost.** Self-hosted Kafka on EC2 requires at least 3 brokers (for ack=all durability), plus a KRaft/ZK quorum. That's 5+ instances for a production-grade deployment. Managed Confluent Cloud for our throughput tier starts at ~$800/month and rises quickly. Redis Streams uses our existing Redis node — marginal cost near zero.
- **Overkill for our throughput.** Kafka is designed for 100k–1M msg/s. We need 500 req/s today, 5000 req/s in 2 years. Redis Streams comfortably handles 10× our target. Kafka's power is wasted on this workload, and the operational tax is paid regardless.
- **Exactly-once is still not truly end-to-end.** Kafka's EOS guarantees exactly-once delivery *within the Kafka cluster* and from a Kafka source to a Kafka sink. For our use case, exactly-once means "send the email exactly once" — Kafka cannot guarantee that the SendGrid API call happens exactly once. Both Kafka and Redis Streams require application-level idempotency in the consumer to achieve end-to-end exactly-once. The advantage Kafka claims here is marginal in practice.
- **Setup time is 3–4 weeks minimum.** A production Kafka cluster requires instance provisioning, security group configuration, TLS certificate management, client library integration, and load testing. This exceeds our 2-week constraint.

### Amazon SQS / SNS (Considered, rejected)

SQS + SNS would decouple notifications with zero infrastructure management. We rejected this for three reasons:
- **No ordering guarantees in standard queues.** FIFO queues cap throughput at 300 txn/s — insufficient at 10× growth.
- **Vendor lock-in.** Moving to SQS ties our async architecture to AWS. If we later need on-prem or multi-cloud deployment, we'd need a full rewrite.
- **WebSocket gap.** SQS has no Pub/Sub or streaming mechanism suitable for real-time push. We'd need a separate WebSocket solution anyway, adding infrastructure complexity.

### PostgreSQL LISTEN/NOTIFY (Considered, rejected)
- No persistent queues — notifications are lost if no listener is connected.
- No consumer group semantics.
- No retry or ack mechanism.
- Single-channel bottleneck at high throughput.

---

## Summary Recommendation

**Adopt Redis Streams.** It is the only option that satisfies all constraints simultaneously: zero new infrastructure, immediate team productivity, adequate throughput headroom, and a natural path to WebSocket push. The cost of Kafka's stronger ordering and retention guarantees is operational complexity we cannot afford with a 6-person team — and those guarantees can be replicated at the application layer (idempotent consumers, PostgreSQL dedup table) at a fraction of the operational cost.

### Immediate next steps

1. Provision a dedicated Redis instance (or logical database on the existing node) for notification streams — 1–2 days.
2. Implement a Python consumer pattern using `redis-py` `XReadGroup` with configurable concurrency — 3 days.
3. Add a retry supervisor that inspects PEL length and `XCLAIM`s stale entries — 2 days.
4. Wire the Flask app to `XADD` on notification triggers, removing blocking SendGrid/HTTP calls from the request cycle — 1 day.
5. Deploy with dead-letter stream and `MAXLEN ~100k` per stream. Monitor PEL depth and DLQ ingress via Redis `INFO` metrics — ongoing.
