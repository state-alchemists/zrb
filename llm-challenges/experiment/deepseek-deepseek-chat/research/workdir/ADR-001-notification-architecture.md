# ADR-001: Notification Subsystem — Asynchronous Processing Architecture

**Status:** Proposed

---

## Context

The Notifier subsystem in our SaaS project management platform is synchronous, embedded in the HTTP request cycle. Every task update, assignment, or completion triggers email and webhook delivery before the response is returned. This design has caused three classes of production incidents:

- **Request timeouts**: Notification latency averages 800ms with spikes to 8s at peak (~500 req/s). Users wait for the email provider before seeing their response.
- **Silent failures**: Downstream email/webhook failures drop notifications without retry, dead-letter queue, or observability.
- **Cascading failures**: Slow webhook endpoints exhausted the PostgreSQL connection pool twice this year, taking down unrelated features.

We need to decouple notification delivery from the request cycle with an asynchronous message broker. Requirements:

| Requirement | Detail |
|---|---|
| Decoupling | Notifications must not block HTTP responses |
| Retry | Exponential backoff with a dead-letter mechanism |
| Delivery guarantees | At-least-once for all; exactly-once for billing events |
| Real-time push | WebSocket delivery target within 2 quarters |
| Headroom | 10x traffic growth without re-architecture |
| Team capacity | 6 engineers, no dedicated ops, zero Kafka experience |
| Timeline | Working value delivered within 2 weeks of decision |
| Budget | Cannot run managed Confluent Cloud at full scale |

We evaluated two candidates: **Apache Kafka** and **Redis Streams**.

---

## Decision

**Adopt Redis Streams as the notification message broker.**

Redis Streams is the right choice for this team, at this stage, with these constraints. It meets every functional requirement while cutting operational complexity to near-zero for a team already running Redis. The team can ship an async notification pipeline in days, not months, and the system has a clear migration path to Kafka if traffic or feature requirements outgrow Redis in the future.

---

## Consequences

### ✅ Pros

**Already in the stack, zero new infrastructure.** Redis is running in production today for sessions and rate limiting. Adding streams requires no new servers, no new clustering topology, no new credentials, no new backup/restore procedures. The team can configure consumer groups, retries, and dead-letter queues with the existing Redis instance.

**Fastest path to value.** The team has Python/Flask familiarity with `redis-py`. A consumer daemon that reads from a stream, dispatches email/webhook, marks the message as delivered, and retries on failure can be written in < 200 lines. The 2-week delivery constraint is easily met — the hard part is the consumer retry/dead-letter logic, which is identical regardless of broker choice.

**Consumer groups with at-least-once delivery.** Redis Streams consumer groups track delivery state per consumer. Each message is delivered to one consumer in the group. If a consumer crashes before acknowledging, the message becomes pending and is re-delivered to another consumer — exactly the semantics needed for exactly-once billing notifications when paired with idempotent processing on the consumer side.

**Natural fit for WebSocket push.** Redis Pub/Sub (running on the same instance) provides the real-time push channel planned for Q2. A single WebSocket server subscribes to a Pub/Sub channel and fans out to connected clients. This avoids architecting WebSocket delivery through a log-based broker.

**Low operational overhead.** The team of 6 without a dedicated infra engineer can manage one Redis instance. No ZooKeeper, no controller quorum, no topic replication factor planning, no partition count decisions. A Redis instance failure means the notification queue is lost, but only unprocessed messages — once acknowledged, delivery is the consumer's responsibility.

**Sufficient throughput.** Redis Streams on modern hardware handles tens-of-thousands of messages per second. At 500 req/s peak with ~3 notifications per request on average, the required throughput is ~1,500 msg/s — well within Redis Streams' comfort zone. Even at 10x growth (500 msg/s sustained, 5,000 msg/s peak during bursts), Redis Streams on a modest instance handles the load.

**No vendor lock-in for the data model.** Messages in Redis Streams are field-value pairs — plain dictionaries. The consumer code deliberately uses Redis Streams as a simple FIFO queue. Switching to Kafka later requires changing the producer/consumer libraries but the message schema and consumer logic remain intact.

### ❌ Cons

**No native message retention for replay.** Kafka persists messages to disk for a configurable retention period. Redis Streams holds messages in memory. If a consumer falls far behind, or if the team needs to replay a week of notifications to rebuild state, Kafka handles this natively. Redis does not — either the stream must be sized to fit in RAM, or a separate archival pipeline is needed.

**Limited ordering guarantees under failure.** Redis Streams guarantees ordered delivery within a single shard. But if the team shards across multiple stream keys (e.g., by customer ID), cross-shard ordering is lost. For the notification use case — each notification is independent — this is acceptable. Kafka's per-partition ordering is stricter and simpler to reason about at scale.

**No built-in exactly-once semantics from the broker.** Redis Streams provides at-least-once. Exactly-once requires idempotent consumers (dedup by notification ID on the consumer side). Kafka's exactly-once semantics are also consumer-implemented for practical purposes, so this is not a meaningful differentiator — both require the same consumer-side idempotency logic.

**Memory-bound queue depth.** If a downstream provider goes down for hours, the stream grows in memory. The team must set a `maxlen` and monitor stream size. Kafka writes to disk — a 24-hour backlog of 50M notifications is a non-issue. For Redis, the team must decide: cap the stream and accept data loss during prolonged outages, or archive to S3 and read back on consumer restart.

**Ecosystem maturity.** Kafka has a rich ecosystem of connectors, stream processors (Kafka Streams, ksqlDB), and monitoring tools. Redis Streams has `redis-py` and `redis-cli`. For the notification use case this is fine — a single consumer daemon doesn't need stream processors. But if the team later wants to build analytics pipelines off the notification events, Kafka is a better foundation.

---

## Alternatives Considered

### Apache Kafka (Rejected)

Kafka is the industry standard for event streaming. It offers:

- **Durable, disk-based retention** — replay months of data
- **Per-partition ordering** — simpler reasoning about event order at scale
- **Consumer group rebalancing** — sophisticated, handles large consumer fleets
- **Ecosystem** — Kafka Connect, Kafka Streams, Confluent Schema Registry, and dozens of monitoring tools

But for this team, today, the costs outweigh the benefits:

**Operational complexity is the decisive factor.** A team of 6 with no Kafka experience and no dedicated infrastructure engineer would need to learn, deploy, and maintain a Kafka cluster (or pay for Confluent Cloud). Running Kafka on EC2 requires ZooKeeper/KRaft, partition count planning, replication factor decisions, disk sizing for retention, and ongoing rebalancing monitoring. Confluent Cloud solves the ops problem but costs $300–1,000+/month at moderate throughput — over budget.

**The 2-week delivery constraint is incompatible with Kafka adoption.** In 2 weeks the team can: (a) research Kafka deployment options, (b) stand up a cluster or provision Confluent Cloud, (c) learn the Kafka Python client, (d) write producers and consumers, and (e) test under production load — or they can write a Redis Streams consumer in 2 days and spend the remaining 12 days on retry logic, monitoring, and testing. The latter is a better use of scarce engineering time.

**Kafka's strengths are surplus to requirements at this stage.** Disk-based retention for replaying a week of notification events is convenient but not critical — if a consumer falls behind, the team can backfill from PostgreSQL event logs or application logs. Per-partition ordering is useful but notification events are independent and order-tolerant. Exactly-once semantics are consumer-side idempotency in both systems — Kafka's transactional API doesn't simplify this meaningfully for a single consumer writing to external APIs (email providers, webhooks).

**Recommendation:** Revisit Kafka only if throughput exceeds 20,000 msg/s sustained (unlikely at 10x growth), or if the team builds event-driven analytics, CQRS read models, or audit log streaming. These are year-2 problems.

### SQS / SQS + Lambda (Rejected)

Amazon SQS is a natural fit for decoupling work in AWS. It offers:

- **Fully managed** — zero ops
- **Dead-letter queues** — native
- **Visibility timeout** — built-in retry with backoff
- **Lambda triggers** — no consumer infrastructure to manage

Rejected because:

**Lambda cold starts and timeout limits** make it unsuitable for webhook delivery at scale. A webhook call can take 5–10 seconds (slow endpoint). Lambda's maximum execution time is 15 minutes, but long-running Lambdas get expensive and delay downstream messages. A dedicated consumer process handles slow webhooks more predictably.

**No real-time push path.** To deliver WebSocket notifications, the team would need a separate service subscribing to SQS or polling SQS and pushing to WebSocket connections. Redis Streams + Pub/Sub on the same instance handles both queues and real-time push with a single infrastructure dependency.

**Vendor lock-in.** SQS ties the notification pipeline to AWS. If the team later migrates to multi-cloud or bare metal, the SQS integration must be rewritten. Redis Streams is portable — any environment with a Redis instance works identically.

### PostgreSQL LISTEN/NOTIFY (Rejected)

PostgreSQL's `LISTEN`/`NOTIFY` adds no new infrastructure and leverages the existing database. Rejected because:

**No delivery guarantees.** `NOTIFY` sends a message to connected listeners. If no listener is connected, the message is lost. No persistence, no replay, no acknowledgment. This is worse than the current system.

**Connection overhead.** Each listener holds a long-lived DB connection. For a modest consumer fleet, this means more connections to the primary — the same pool-exhaustion risk that caused the cascading failures.

**No consumer groups.** Every listener receives every notification. Distributing work across consumers requires application-level coordination (re-enqueue, dedup, skip). Redis Streams consumer groups handle this natively.
