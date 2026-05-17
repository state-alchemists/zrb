# ADR-001: Notification Subsystem Architecture - Kafka vs. Redis Streams

## Status
Proposed

## Context
Our SaaS platform (85,000 MAU, ~2M tasks/month, peak 500 req/s) is experiencing stability issues due to synchronous notification processing (emails, webhooks) within the HTTP request cycle. This architecture causes average response latencies of 800ms (spiking to 8s), silent failures when third-party APIs are down, and occasional cascading failures due to connection pool exhaustion. Furthermore, we lack delivery guarantees for critical billing notifications.

We need to decouple notifications into an asynchronous system that supports:
- Retries with exponential backoff.
- At-least-once delivery (and exactly-once semantics for billing events).
- Future integration of real-time WebSocket push notifications within 2 quarters.
- 10x traffic growth.

We are a small engineering team (6 engineers, no dedicated infrastructure engineer) with a modest budget. We must deliver value within 2 weeks. We currently run Redis in production for caching and rate limiting, but we have zero in-house experience with Apache Kafka.

## Decision
We will use **Redis Streams** as our message broker for the asynchronous notification subsystem.

To satisfy the "exactly-once" delivery requirement for billing notifications, we will pair Redis Streams with a **Transactional Outbox** pattern (using our existing PostgreSQL database) and implement **Idempotent Consumers**. 

**Justification:**
1. **Time-to-Value & Operational Complexity:** Redis is already in our production stack. Leveraging Redis Streams introduces zero new infrastructure components. The team can implement this within the strict 2-week deadline without the steep learning curve and operational burden of managing a Kafka cluster.
2. **Consumer Groups:** Redis Streams natively supports Consumer Groups (similar to Kafka), which allows us to load-balance message processing across multiple workers and supports fan-out messaging. This is critical for our upcoming WebSocket push notification requirement.
3. **Delivery Guarantees:** Redis Streams provides reliable at-least-once delivery through explicit acknowledgments (`XACK`) and the Pending Entries List (PEL) for crashed consumers. By storing the initial event in Postgres alongside the domain transaction (Outbox pattern) and making our consumer workers idempotent, we achieve the required exactly-once processing semantics for billing.
4. **Scale:** Redis is highly performant. Even handling 10x our current traffic (peak 5,000 req/s), Redis Streams can easily process the ingestion volume in-memory without breaking a sweat, provided we actively consume and acknowledge the messages.

## Consequences

**Pros:**
- **Zero New Infrastructure Costs:** No need to pay for managed Kafka (e.g., Confluent Cloud) or maintain ZooKeeper/KRaft.
- **Fast Implementation:** Aligns with our constraint to deliver value within 2 weeks.
- **Fits Team Topology:** Does not require a dedicated infrastructure engineer or specialized distributed systems knowledge that the team currently lacks.
- **Built-in Fan-out:** Consumer groups seamlessly support adding future consumers (e.g., WebSocket service, analytics service) without impacting the email/webhook workers.

**Cons:**
- **Memory Bound:** Unlike Kafka, which writes sequentially to disk, Redis Streams stores messages in memory. If our consumers go down for an extended period, an unacknowledged queue could cause Redis to hit memory limits and evict data or crash. We will need strict monitoring on consumer lag and memory usage, and implement `MAXLEN` caps for the streams.
- **Application-Level Complexity for Exactly-Once:** Because Redis isn't a transactional database, achieving exactly-once semantics requires discipline in the application layer (Transactional Outbox + Idempotency keys), though this is largely true for Kafka as well when interacting with external APIs (like Stripe or SendGrid).

## Alternatives Considered

**Apache Kafka:**
- **Why it was considered:** Kafka is the industry standard for high-throughput, durable, replayable event streaming. It natively handles massive scale, offers disk-based retention, and provides strong ordering guarantees. 
- **Why it was rejected:** 
  - *Operational Overhead:* Kafka is notoriously complex to deploy, tune, and maintain. With a 6-person team and no infra engineers, self-hosting is too risky.
  - *Budget & Time Constraints:* Managed solutions are too expensive for our current budget, and getting up to speed with Kafka paradigms (partitions, rebalancing, offsets) would easily exceed the 2-week implementation deadline.
  - *Overkill:* At our target scale (10x growth = ~5,000 req/s peak), Kafka's massive throughput capabilities are largely unnecessary. Redis Streams is more than sufficient for this volume while fitting within our operational constraints.