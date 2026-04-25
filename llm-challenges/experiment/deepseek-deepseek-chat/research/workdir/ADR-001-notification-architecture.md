# ADR-001: Notification Subsystem — Async Processing Architecture

**Status:** Proposed

---

## Context

The Notifier module in our SaaS project management platform (85k MAU, ~2M tasks/month, 500 req/s peak) sends emails and webhooks for task updates, assignments, and completions. Currently, notifications are sent synchronously inside the HTTP request cycle, causing:

- **Request timeouts** — average latency 800ms, spikes to 8s during peak hours.
- **Silent failures** — failed email or webhook deliveries are dropped with no retry or dead-letter queue.
- **Cascading failures** — two incidents where slow webhook endpoints exhausted the connection pool, taking down unrelated features.
- **No delivery guarantees** — billing-critical notifications (trial expiry, payment failures) must be delivered exactly-once but lack any guarantee today.

We need to decouple notification delivery from the request cycle, supporting:

| Requirement | Priority |
|---|---|
| Async processing (non-blocking requests) | Critical |
| Retry with exponential backoff | Critical |
| At-least-once delivery for billing events | Critical |
| Exactly-once delivery for billing events | High |
| Real-time WebSocket push (within 2 quarters) | Medium |
| 10x traffic growth without re-architecting | Medium |

**Team constraints:**
- 6 engineers (3 senior, 3 mid-level), no dedicated infrastructure engineer
- Redis already in production (session storage, rate limiting)
- Zero Kafka experience on the team
- ≤ 2 weeks to deliver value
- No budget for managed Confluent Cloud at full scale
- AWS-hosted, Python/Flask monolith, PostgreSQL

---

## Decision

**Adopt Redis Streams** as the notification message bus.

Redis Streams provide a consumer-group-based message queue that maps cleanly to our workload. Since Redis is already deployed and operated by the team, we can deliver async notification processing within days, not weeks. This decision carries the expectation that we will re-evaluate when and if the workload scales beyond Redis's ability to keep up — but given our team size, budget, and 10x growth target, Redis Streams comfortably cover our requirements.

### Why Redis Streams fits

**Message retention & ordering.** Redis Streams uses a consumer-group model where each message is assigned to one consumer in a group, with delivery tracking via a PEL (Pending Entry List). Messages persist until explicitly acknowledged or trimmed by maxlen (capped at 100k–1M per stream), giving us hours-to-days of backlog tolerance without a separate storage system. Within a consumer group, messages are delivered in insertion order — sufficient for our notification use case where per-resource ordering (e.g., events for the same task arrive in order) matters, but global total order does not. If per-resource ordering is needed, we partition by task/project ID.

**Consumer groups & retries.** Each notification type (email, webhook, WebSocket) becomes a consumer group consuming the same stream. Unacknowledged messages remain in the PEL and are automatically redelivered to the same or another consumer after a configurable idle timeout — this provides built-in at-least-once delivery and the foundation for exponential backoff (implemented by checking delivery count and requeueing with delay via a sorted set).

**Exactly-once semantics for billing.** Redis Streams supports *idempotent consumers*: by externalizing a consumer-side deduplication key (e.g., notification UUID) in Redis itself (`SET NX` with TTL), we achieve exactly-once processing. Combined with client acknowledgment (`XACK`), this gives us the same guarantee level Kafka provides with idempotent producers, at lower operational cost.

**Operational simplicity.** The team already runs Redis. Adding streams is a configuration change — no new cluster, no new data pipeline, no new monitoring surface. For on-call engineers who know `redis-cli`, debugging a stalled consumer is a three-command operation (`XINFO GROUPS`, `XPENDING`, `XCLAIM`). This is the decisive advantage given our team size.

**Real-time WebSocket push** fits naturally: a worker uses `XREADGROUP` with `BLOCK` to tail the stream and push events to connected WebSocket clients via a pub/sub channel. Redis Streams + Redis Pub/Sub gives us push notifications without introducing a separate broker.

**Scaling to 10x.** At 10x, our peak throughput is ~5,000 req/s and ~10,000 notification events/s. A single Redis instance handles 100k–200k ops/s on modest hardware. With pipelining in the producer and a small consumer pool (10–20 workers), Redis Streams absorbs this comfortably. If we outgrow one instance, we can shard by stream (billing vs. email vs. webhook) — the same pattern we'd eventually use with Kafka.

---

## Consequences

### ✅ Advantages

| Area | Benefit |
|---|---|
| **Time to value** | Days, not weeks. Existing Redis infrastructure, minimal new code. |
| **Operational burden** | No new system to learn, deploy, or monitor. The team maintains Redis — which they already do. |
| **Cost** | No new infrastructure cost. Redis runs on existing instances. |
| **Retry & DLQ** | PEL provides built-in unacknowledged message tracking. Integration with a Redis Sorted Set gives us scheduled retry with exponential backoff. Dead letters go to a separate stream or a Redis List for manual inspection. |
| **WebSocket push** | Workers tailing the stream with `BLOCK` push live updates via Pub/Sub — a single coherent subsystem. |
| **Consumer flexibility** | Multiple consumer groups independently track their own cursor, so we can add new notifier types without reprovisioning. |
| **Message persistence** | Configurable stream retention (maxlen), tunable to our needs. |
| **Exactly-once semantics** | Achievable via idempotent consumers with external deduplication. |

### ⚠️ Disadvantages

| Area | Risk / Trade-off |
|---|---|
| **Throughput ceiling** | A single Redis instance is far below Kafka's horizontal scalability ceiling. If we 100x+ grow, we'll hit it. Redis Cluster sharding is operational work. |
| **Message replay granularity** | No Kafka-style offset-based replay to arbitrary points in time. Reprocessing past messages requires a consumer to iterate from a stream ID — functional but less ergonomic. |
| **Message size** | Redis streams are memory-bound. Large notification payloads (>1 MB) waste RAM and degrade performance. Mitigation: store payload in S3/PG, push only a pointer through the stream. |
| **No built-in partitioning** | Redis Streams doesn't have Kafka's partition-per-consumer scaling model. We can manually shard by stream, but it's less elegant. |
| **Consumer rebalancing** | When a consumer dies, the group leader auto-assigns pending messages to another consumer — but this rebalancing is less sophisticated than Kafka's cooperative rebalancing protocol. |

---

## Alternatives Considered

### Apache Kafka (Rejected)

Kafka is the gold standard for high-throughput, partitioned, replayable event streaming. It excels at exactly-once semantics (idempotent producers + transactional API), and its log-based architecture with configurable retention is ideal for event sourcing and replay.

**Why rejected:**

- **Operational overhead is fatal for a 6-person team.** Kafka requires Zookeeper/KRaft, careful partition sizing, broker tuning, and ongoing monitoring. Without a dedicated infrastructure engineer, a misconfigured Kafka cluster (too few partitions, under-replicated partitions, unclean leader election) will cause worse outages than the current synchronous system. The team has zero Kafka experience — there is a steep learning curve before anything delivers value.
- **Time to value exceeds the 2-week constraint.** Provisioning, tuning, wiring, and testing Kafka — with no prior team experience — realistically takes 4–6 weeks. We cannot leave the notification problem unresolved for that long.
- **Cost at scale.** Managed Kafka (Confluent Cloud) is expensive. Self-hosted Kafka on AWS (EC2 + EBS + networking) is cheaper but adds operational overhead that conflicts with the team constraint.
- **Over-engineered for the workload.** At 500 req/s and ~2M notifications/month, we are well below Kafka's sweet spot (100k+ events/s). Redis Streams handles our throughput with far less complexity.

**When to revisit:** If sustained throughput exceeds 50,000 events/s, or if we need global total order across all events, or if event sourcing/replay becomes a first-class product requirement. At that point, Kafka becomes worth the operational cost — but today is not that day.

### RabbitMQ (Rejected)

RabbitMQ is a mature, AMQP-compliant message broker with excellent routing flexibility (exchanges, bindings, topics).

**Why rejected:**
- **No message retention.** RabbitMQ deletes messages once consumed. Our retry and replay requirements need persistent storage.
- **No stream-like replay.** RabbitMQ Streams (added in 3.9) is experimental and less battle-tested than Redis Streams.
- **Operational overhead.** Requires a new Erlang-based cluster. Our team has no Erlang/RabbitMQ operational experience. Adds a new surface for monitoring, patching, and on-call.

### Amazon SQS + SNS (Rejected)

Fully managed, dead-letter queue support, exactly-once via FIFO queues, no operational overhead.

**Why rejected:**
- **Vendor lock-in.** Decision pushes us deeper into AWS; future migration to multi-cloud or on-prem becomes expensive.
- **No ordered delivery for standard queues.** FIFO queues guarantee order but cap throughput at 300 TPS (3,000 with batching) — too low for peak traffic at 10x growth.
- **No native consumer group model.** Each SQS message is processed by one consumer per queue — we'd need separate queues for email, webhook, and WebSocket, each with its own retry and DLQ configuration.
- **No real-time push.** SQS requires polling (long-polling reduces cost but adds latency). Kafka and Redis Streams both support push-based consumption.
- **Cost at scale.** SQS costs per-million requests add up at 10x. Redis Streams cost is zero (already running).

---

## Implementation Summary

| Component | Approach |
|---|---|
| Producer | Flask handler pushes notification payload + UUID + delivery count to Redis Stream via `XADD` |
| Email consumer | `XREADGROUP` worker with `BRPOPLPUSH`-style retry via Sorted Set for exponential backoff |
| Webhook consumer | Same pattern as email, with circuit breaker (threshold-based skip before `XACK`) |
| Billing consumer | Idempotent consumer: `SET dedup:<uuid> NX EX 86400` before processing, `XACK` only after success |
| Dead-letter queue | After N retries, `XADD` to a `dlq:<type>` stream with original payload + error context |
| WebSocket push | Worker `XREADGROUP BLOCK 0` + `PUBLISH` to Redis Pub/Sub, forwarded via an async WebSocket server |

**Migration plan:** Implement as a sidecar within the monolith first (same process, separate thread pool), then extract into a standalone worker process when traffic grows. This keeps the 2-week timeline realistic.
