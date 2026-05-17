# ADR-001: Notification Subsystem Architecture

**Status:** Proposed

---

## Context

Our Python/Flask project-management platform currently sends emails and webhooks synchronously inside the HTTP request cycle. At peak load (~500 req/s), this produces:

- Average response latency of 800ms, spiking to 8s
- Silent drops when downstream providers fail, with no retry mechanism
- Cascading failures (slow webhooks exhausting connection pools and taking down unrelated features)
- Zero delivery guarantees for billing-critical events such as "trial expired" and "payment failed"

We must decouple notification dispatch from the request cycle, introduce retries with exponential backoff, and provide at-least-once delivery for all events and exactly-once semantics for billing notifications. The solution must be deployable within two weeks by a six-person engineering team (three senior, three mid-level) with **no dedicated infrastructure engineer**. We already run Redis in production for sessions and rate limiting, but no one on the team has operated Kafka. The budget is modest: we cannot afford managed Confluent Cloud at full scale.

The platform is expected to grow 10× within the planning horizon, and we will add real-time WebSocket push notifications within two quarters.

---

## Decision

**Adopt Redis Streams as the notification bus.**

We will run a dedicated Redis instance (or Elasticache cluster) for streams, separate from our existing session/rate-limiting Redis, to avoid resource contention. Producers will use `XADD` to publish notification events. Consumers will use `XREADGROUP` in a named consumer group, process messages idempotently, and acknowledge with `XACK`. Billing-critical events will be handled with an application-level idempotency check (event UUID stored in PostgreSQL with a unique constraint) to deliver effective exactly-once semantics.

This choice is driven by the hard constraints of team size, time-to-value, budget, and the reality that both options ultimately require application-level idempotency for true exactly-once processing.

---

## Consequences

### Pros

- **Time to value:** Redis Streams is built into Redis 5.0+. Because the team already operates Redis, the subsystem can be wired into the Flask monolith and deployed within days, well under the two-week deadline.
- **Low operational complexity:** No new service topology (ZooKeeper/KRaft, broker tuning, partition rebalancing) to learn or operate. One mid-level engineer can own it without an SRE.
- **Cost:** Uses a technology already in our stack. A modest AWS Elasticache Redis node (or an EC2 instance with AOF+RDB persistence) is dramatically cheaper than a self-managed Kafka cluster (minimum three brokers for HA) or managed MSK/Confluent.
- **Throughput headroom:** Redis Streams can sustain well over 100,000 messages/sec on a single node. Our peak notification volume today is roughly 100–200 events/sec; at 10× growth we remain comfortably inside the capability of a single Redis instance.
- **Path to WebSocket push:** Redis Pub/Sub (or a lightweight bridge from Streams) slots neatly into our existing Redis architecture for the upcoming real-time requirement.
- **Exactly-once feasibility:** Both Kafka and Redis Streams provide at-least-once delivery natively. Achieving end-to-end exactly-once requires an idempotent consumer in either system. Using our existing PostgreSQL to store processed event UUIDs satisfies the billing exactly-once requirement without waiting for engineers to master Kafka transactions and idempotent producer configs.

### Cons

- **Memory-bound retention:** Redis Streams stores data in memory. If consumers lag significantly (e.g., during an extended downstream email-provider outage), memory usage rises and we risk OOM or forced trimming. We must enforce `MAXLEN` or explicit trimming, and monitor memory aggressively.
- **Consumer group maturity:** Redis consumer-group rebalancing is less battle-tested than Kafka’s. During consumer scaling events (deployment, pod restart) we may experience brief duplicate deliveries, reinforcing the need for idempotent handlers.
- **Horizontal scaling ceiling:** While single-node throughput covers our 10× target, growth beyond that (or retention of very large backlogs) will eventually require Redis Cluster or a migration to Kafka. We accept this trade-off because our near-term constraint is *surviving 10×*, not infinite scale.
- **Exactly-once is an application concern:** Unlike Kafka’s idempotent producer + transactions, which reduce the surface area of deduplication, Redis Streams offers no native producer-level deduplication. We must handle all deduplication in application code.
- **Single-point-of-failure risk:** A single Redis instance (or even a primary-replica Elasticache setup with manual failover) is less resilient than a properly configured multi-broker Kafka cluster. We mitigate this with persistence (AOF every-second + RDB snapshots) and monitoring.

---

## Alternatives Considered

### Apache Kafka

Kafka was evaluated and **rejected** for the current phase.

Technical strengths that made it attractive:
- **Disk-based log:** Retention is decoupled from RAM, making multi-day backlogs cheap and safe.
- **Exactly-once primitives:** Idempotent producers and transactions offer stronger native guarantees than Redis Streams.
- **Consumer groups and partitioning:** Mature, automatic rebalancing and horizontal partitioning are proven at massive scale.
- **Ecosystem:** Rich tooling (Kafka Connect, schema registry, monitoring dashboards).

Reasons for rejection:
- **Operational burden:** Operating a production Kafka cluster (3+ brokers, KRaft or ZooKeeper, partition planning, ISR tuning, and disk monitoring) is a specialty discipline. With six engineers and no infrastructure expert, we would spend the first month fighting configuration instead of shipping retries and dead-letter queues.
- **Schedule risk:** The team has zero Kafka experience. Estimates from the senior engineers place a minimal production deployment (including HA, monitoring, and runbook writing) at 4–6 weeks, violating the two-week value-delivery constraint.
- **Cost at modest scale:** A three-node self-managed cluster on EC2 is more expensive than a single Elasticache Redis node, and managed options (MSK, Confluent Cloud) are explicitly ruled out by budget constraints.
- **Overkill for current and 10× load:** Kafka excels when you need millions of messages per second and complex stream topologies. Our notification volume does not justify the infrastructure tax today.
- **Exactly-once is still not free:** Even with Kafka, end-to-end exactly-once requires idempotent consumers and transactional writes. The application-level work we would do for Redis Streams is nearly identical to what Kafka requires. Kafka improves producer semantics, but our risk is consumer-side duplicates, which both systems must solve in application code.

Kafka remains a viable *future* architecture when the team grows, an SRE is hired, or volume crosses the threshold where Redis memory economics become unfavorable. At that point, the idempotent consumer pattern we build now will port cleanly to Kafka.

---

## Recommendation

Proceed with **Redis Streams** for the notification subsystem. Implement a dedicated Redis instance with persistence (AOF + RDB), consumer groups per notification type (email, webhook, billing), application-level idempotency for billing events, and explicit memory monitoring with `MAXLEN` stream trimming policies.

Re-evaluate a migration to Kafka when the engineering team exceeds 12 people, a dedicated infrastructure role is staffed, or sustained throughput exceeds 50,000 messages/sec.
