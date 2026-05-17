# ADR-001: Notification Subsystem Architecture - Message Broker Selection

## Status
Proposed

## Context
Our SaaS project management platform is currently sending notifications (emails and webhooks) synchronously during the HTTP request cycle. With 85,000 MAU and peak traffic of 500 req/s, this architecture is failing. We are experiencing request timeouts (up to 8s latency spikes), silent data loss when external providers fail, and cascading failures due to connection pool exhaustion. 

We need to decouple notifications into an asynchronous subsystem that supports:
- Exponential backoff and retries.
- At-least-once delivery generally, and exactly-once semantics for billing-critical events.
- Future real-time WebSocket push notifications (within 2 quarters).
- 10x traffic growth (up to 5,000 req/s) without re-architecture.

We are operating under strict constraints: a 6-person engineering team with no dedicated infrastructure engineer, a modest budget, and a maximum 2-week implementation timeline before delivering value. The team has no Apache Kafka experience, but already operates PostgreSQL and Redis in production.

## Decision
We will use **Redis Streams** as the message broker for the asynchronous notification subsystem.

Given our tight constraints, introducing a new, operationally complex piece of infrastructure is too high a risk. Redis is already in our stack for session management and rate limiting, meaning the team understands its operational profile. Redis Streams natively supports Consumer Groups, which will allow us to safely distribute messages across worker nodes, track acknowledgments, and implement a Dead Letter Queue (DLQ) for failed webhooks. 

To satisfy the "exactly-once" delivery requirement for billing events, we will rely on **application-level idempotency** rather than broker-level guarantees. Workers will check and insert an idempotency key (derived from the event ID) into our existing primary PostgreSQL database within the same transaction that updates the system state, ensuring that even if Redis delivers a message twice, the business logic executes only once.

## Consequences

**Pros:**
- **Zero infrastructural overhead:** No new services to provision, monitor, or learn. Fits our modest budget.
- **Fast time-to-value:** Implementing Redis Streams using Python/Flask worker libraries will comfortably fit within the 2-week constraint.
- **Consumer Group support:** Native `XREADGROUP` and `XACK` commands provide the at-least-once delivery guarantees and tracking needed to prevent silent failures.
- **WebSocket readiness:** Redis makes it trivial to fan-out notifications to WebSocket servers in the future via Streams or Pub/Sub.
- **Sufficient throughput:** Redis Streams can easily handle our 10x growth target (5,000 req/s) with minimal tuning.

**Cons:**
- **In-memory cost:** Unlike disk-backed systems, retaining messages in Redis is expensive. We must strictly configure stream trimming (`MAXLEN`) to drop acknowledged messages to prevent memory exhaustion.
- **Durability limits:** Persistence is tied to our Redis AOF/RDB snapshot settings. While sufficient for our use case, it is fundamentally less durable than a distributed commit log.
- **Manual idempotency:** We must write and maintain the deduplication logic in our Python application for exactly-once billing events, rather than getting it out-of-the-box from the broker.

## Alternatives Considered
**Apache Kafka**
Kafka is the industry standard for high-throughput, fault-tolerant message streaming. It offers robust on-disk retention, excellent partitioning, and exactly-once semantics (via transactional APIs). 

*Reason for Rejection:* Kafka fails our organizational and operational constraints. Operating a Zookeeper/KRaft cluster requires specialized knowledge our 6-person team lacks, violating the rule against dedicated infrastructure overhead. Managed solutions (like Confluent Cloud) exceed our modest budget at our target scale. Finally, setting up Kafka, securing it, provisioning the infrastructure, and training the team would heavily exceed the 2-week time constraint. Our throughput target of 5,000 req/s does not justify Kafka's operational tax.