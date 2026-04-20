# ADR-001: Notification Subsystem Architecture

**Status:** Proposed

## Context

Our SaaS project management platform currently processes notifications (emails, webhooks) synchronously within the HTTP request cycle. At our current peak load of ~500 req/s, this architecture is causing request timeouts (up to 8s latency spikes), silent failures, and cascading system failures due to connection pool exhaustion. 

We need to decouple notifications into an asynchronous, queue-based architecture to achieve:
- Reliable delivery with retries and exponential backoff
- At-least-once delivery guarantees (and exactly-once semantics for billing notifications)
- Future support for real-time WebSocket push notifications
- Headroom for 10x traffic growth (peak ~5,000 req/s)

However, we operate under strict constraints:
- Engineering team of 6 (no dedicated infrastructure/DevOps engineer)
- Modest budget (cannot afford premium managed services like Confluent Cloud)
- Strict 2-week timeline to deliver business value
- No existing team experience with Apache Kafka
- We currently operate Redis in production for session management and rate limiting

We evaluated **Apache Kafka** and **Redis Streams** as the message broker for this subsystem.

## Decision

We will use **Redis Streams** for the asynchronous notification subsystem.

Given our small team size, lack of dedicated infrastructure engineering, and strict 2-week delivery timeline, introducing a highly complex distributed system like Apache Kafka is an unacceptable operational risk. Redis is already part of our production stack, meaning we incur zero new infrastructure provisioning, monitoring, or maintenance overhead. 

Redis Streams natively supports the technical requirements we need:
- **Throughput:** Redis can trivially handle our 10x growth target of ~5,000 req/s (it can handle 100k+ ops/sec).
- **Consumer Groups:** Using `XREADGROUP`, we can distribute message processing across a fleet of worker dynamos/containers.
- **Reliability & Retries:** Unacknowledged messages remain in a Pending Entries List (PEL). A background worker can use `XPENDING` to claim and retry stalled messages, effectively giving us at-least-once delivery.
- **Exactly-once Semantics:** No message broker can guarantee exactly-once *delivery* to an external system (like an email API). We will achieve exactly-once *processing* for billing events by using Redis Streams for at-least-once delivery, combined with an idempotency key stored in our existing PostgreSQL database.

## Consequences

### Pros
- **Speed to Market:** Developers can implement this within the 2-week constraint using well-documented Redis client libraries.
- **Zero Infra Overhead:** No new services to deploy, monitor, patch, or secure.
- **Cost Effective:** We leverage our existing Redis infrastructure, avoiding the high costs of managed Kafka clusters.
- **Built-in Fan-out:** When we implement WebSocket notifications later this year, Redis Streams allows multiple independent consumer groups to read the same message stream without consuming each other's messages.

### Cons
- **Memory Bound Retention:** Unlike Kafka, which writes to disk and can retain messages for months, Redis Streams live in memory. We must carefully configure stream trimming (e.g., `MAXLEN`) to prevent out-of-memory (OOM) crashes.
- **Durability Risks:** Redis persistence (AOF/RDB) is generally reliable, but a hard node crash could result in the loss of sub-second unflushed data depending on `fsync` settings. Kafka offers stronger multi-node disk-level durability.
- **Manual Idempotency:** The application layer must handle exactly-once processing logic for external billing calls.

## Alternatives Considered

**Apache Kafka:** 
Rejected. While Kafka is the industry standard for high-throughput, highly-durable event streaming, it is heavily over-engineered for our needs. 
- *Operational Complexity:* Running a self-hosted Kafka cluster (with ZooKeeper/KRaft) requires dedicated DevOps resources we do not have.
- *Timeline constraints:* Learning Kafka's complex client configurations (partition rebalancing, offset commits, retention policies) would easily violate our 2-week deadline.
- *Overkill capacity:* Kafka is designed for millions of messages per second; our 10x target is 5,000 req/s, which Redis handles easily.
- *Budget constraints:* Managed Kafka (e.g., Confluent Cloud, MSK) provides the operational relief we'd need, but violates our modest budget constraint.