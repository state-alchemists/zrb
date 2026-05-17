# ADR 001 — Notification Subsystem Message Broker

- **Status**: Proposed
- **Date**: 2026-05-17
- **Deciders**: Backend team (6 engineers)
- **Context tags**: notifications, messaging, scaling, reliability

## Context

Notifications (emails, webhooks) are processed synchronously inside the HTTP request cycle of a Python/Flask monolith serving 85,000 MAU. This has caused four documented problems: request timeouts averaging 800ms (spiking to 8s), silent notification drops with no retry or dead-letter queue, two incidents where slow webhook endpoints exhausted the connection pool and cascaded into unrelated features, and no delivery guarantees for billing-critical notifications ("trial expired", "payment failed") that require exactly-once semantics.

Two incidents in the past year traced back to synchronous notification processing causing connection pool exhaustion and platform-wide degradation. (`system_context.md:18-21`)

The system must decouple notification production from delivery, support retry with exponential backoff, guarantee at-least-once delivery for all notifications with exactly-once for billing events, and absorb 10x traffic growth without re-architecting. Real-time WebSocket push notifications are planned within two quarters.

Key constraints: 6-person team with no dedicated infrastructure engineer, no prior Kafka experience, existing Redis instance already in production for sessions and rate limiting, a hard two-week deadline before the solution must deliver observable value, and a budget that cannot sustain managed Confluent Cloud at scale.

## Decision

> We will use Redis Streams as the message broker for the notification subsystem.

Billing-notification exactly-once semantics will be enforced at the application layer using idempotency keys (notification ID + recipient) with a deduplication table in PostgreSQL, not through broker-level transaction semantics. This is necessary regardless of broker choice because the external side effects (email sends, webhook deliveries) are outside any broker's transaction boundary.

## Rationale

The decision turns on three constraints that are non-negotiable and that Kafka cannot satisfy simultaneously:

1. **Two-week time-to-value.** A team of six with zero Kafka experience cannot reliably stand up a production Kafka cluster (3+ brokers for fault tolerance, ZooKeeper or KRaft configuration, partition planning, monitoring, consumer offset management) and migrate the notification flow within two weeks. Redis Streams require adding `XADD`/`XREADGROUP` calls to an already-operational Redis instance — an incremental change measured in days.

2. **No dedicated infrastructure engineer.** Kafka demands ongoing operational effort: broker rollouts, partition rebalancing, consumer lag monitoring, disk capacity planning, ZooKeeper/KRaft quorum management. A six-person feature team without dedicated ops cannot sustain this alongside product work. Redis is already operated by this team for sessions and rate limiting; adding streams to the same instance adds near-zero operational burden.

3. **Exactly-once for billing notifications is an application-level property.** Kafka's transaction-based exactly-once semantics guarantee idempotent consume-process-produce cycles *within Kafka itself*. They do not prevent a consumer from sending the same email or webhook twice after a crash mid-delivery. External delivery requires application-level idempotency regardless of broker. A PostgreSQL deduplication table keyed on `(notification_id, recipient_id)` achieves the same guarantee with either broker — so Kafka's native EOS does not differentiate it for this use case.

Throughput is not a differentiator at our scale. Current peak is ~500 req/s; 10x growth yields 5,000 req/s. Redis Streams handle hundreds of thousands of messages per second on a single node — orders of magnitude above this ceiling. Kafka's capacity extends to millions per second, which is surplus capacity we do not need and cannot afford to operate.

On cost: self-hosted Kafka requires a minimum 3-broker cluster on dedicated instances. Our existing Redis instance absorbs the notification workload at marginal cost. Managed Confluent Cloud at 10x traffic volume exceeds the budget constraint (`system_context.md:39`).

## Alternatives Considered

- **Apache Kafka** — rejected because the operational overhead and learning curve are incompatible with a six-person team on a two-week deadline. Kafka's strengths — extreme throughput (millions of msgs/s), per-partition ordering with partition-level parallelism, configurable long-term message retention, native consumer groups with rebalancing, and transaction-based exactly-once semantics within the Kafka ecosystem — are genuine advantages, but none of them solve a problem we have *that Redis Streams cannot also solve*. We would have chosen Kafka if: (a) the team had prior Kafka experience or a dedicated platform engineer, (b) the two-week constraint were relaxed to 6-8 weeks, and (c) the budget supported managed Kafka or dedicated broker infrastructure. Any one of those three changes would reopen this decision.

- **PostgreSQL LISTEN/NOTIFY + queue table** — considered as a zero-infrastructure option but rejected because LISTEN/NOTIFY has no persistence (messages lost on crash), no consumer groups, no built-in retry, and polling a queue table adds write amplification on the primary. Would have won if Redis were not already in production.

- **RabbitMQ** — considered briefly. Richer routing than Redis Streams, but introduces a new operational component (Erlang runtime, cluster management) with no team experience. Same time-to-value problem as Kafka without Kafka's throughput ceiling. Would have won if we needed complex routing topologies (topic exchanges, fanout) that Redis Streams cannot model.

## Consequences

- **Positive**: Notification processing decoupled from the HTTP cycle within days, not weeks. Team operates no new infrastructure — Redis is already a managed dependency. Consumer groups (`XGROUP`) provide load-balanced, persistent consumption with automatic message pending-tracking for failure recovery. Retry with exponential backoff implemented at the consumer layer using `XPENDING` + `XCLAIM`. The same Redis instance can fan out WebSocket messages when that feature ships, avoiding a second broker introduction. Marginal cost to operate.

- **Negative**: Redis Streams lack per-partition parallelism — a single stream is consumed sequentially per consumer group, so throughput scaling requires sharding across multiple stream keys or multiple consumer groups. Message retention is time- or count-based with trimming (`XTRIM`), not the durable log Kafka provides; if all consumers lag beyond the retention window, messages are lost — we must size `MAXLEN` conservatively and monitor consumer lag. Redis Streams do not support exactly-once delivery natively; the application-layer deduplication table is additional code to write, test, and maintain. If notification volume grows beyond single-node Redis capacity (unlikely at 10x given current load, but possible at higher multiples), we face a migration to either Redis Cluster or a new broker — a non-trivial transition. Redis persistence (AOF/RDB) provides durability but not the same crash-recovery guarantees as Kafka's replicated commit log.

- **Follow-ups**:  
  1. Implement the PostgreSQL deduplication table for billing notifications with a unique constraint on `(notification_id, recipient_id)` and write idempotency-key checks into all billing notification consumers.  
  2. Set `MAXLEN` to ~500,000 per stream (roughly 2 hours of messages at 10x peak) and add a consumer-lag alert when `XPENDING` count exceeds 10% of `MAXLEN`.  
  3. Write a dead-letter consumer that moves messages exceeding max retry count to a `notifications:dead-letter` stream for manual inspection.  
  4. Document the Redis Cluster migration path as a condition for revisiting this ADR if single-stream throughput becomes a bottleneck.