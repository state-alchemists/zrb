# ADR-001: Use Redis Streams for Notification Subsystem

## Status
Proposed

## Context
Our SaaS project management platform currently handles task notifications (emails, webhooks) synchronously within the Flask HTTP request cycle. This architecture causes severe issues at our peak load of 500 req/s: request timeouts (latency spikes up to 8s), cascading failures from slow webhooks exhausting connection pools, and silent dropped messages. Furthermore, billing-critical notifications lack the required exactly-once delivery guarantees.

We must decouple notifications to an asynchronous queue to support 10x traffic growth (~5k req/s), add real-time WebSocket push notifications within two quarters, and implement retry logic with exponential backoff. 

Our constraints are rigid:
- A 6-person engineering team with no dedicated infrastructure engineer.
- No existing team experience with Apache Kafka.
- A strict 2-week setup and migration deadline.
- A modest budget that rules out premium managed infrastructure like Confluent Cloud.
- Redis is already running in production for session management and rate limiting.

## Decision
We will use **Redis Streams** as the message broker for the asynchronous notification subsystem.

**Justification:**
Given the strict 2-week timeline and lack of dedicated infrastructure personnel, leveraging our existing Redis deployment is the only viable path to immediate value. Redis Streams provides Consumer Groups, which will allow us to independently scale email, webhook, and future WebSocket consumers. Redis can trivially handle our target throughput of 5,000 req/s.

To meet the mandatory **exactly-once semantics** for billing notifications, we will rely on Redis Streams' native *at-least-once* delivery guarantee combined with **idempotent consumers**. We will achieve exactly-once processing by generating unique idempotency keys for billing events and storing them in our existing PostgreSQL database within the same transaction that updates the user's billing state.

## Consequences

**Pros:**
- **Zero New Infrastructure:** No new services to provision, monitor, or pay for, keeping us within budget.
- **Speed of Execution:** Fits safely inside the 2-week migration constraint.
- **Consumer Groups:** Natively supports our roadmap requirement to add decoupled WebSocket consumers in the coming quarters.

**Cons:**
- **Memory-Bound Retention:** Unlike Kafka's disk storage, Redis stores data in RAM. We must proactively configure stream length limits (`XADD MAXLEN`) to prevent out-of-memory crashes.
- **Manual Retry/DLQ Logic:** Redis Streams does not have built-in exponential backoff or dead-letter queues. We will need to write custom application logic (e.g., using Redis Sorted Sets) to handle failed message retries and DLQ routing.

## Alternatives Considered

**Apache Kafka:**
Rejected. While Kafka provides superior disk-based message retention, native exactly-once transactional semantics, and massive horizontal scalability, it fails our team and budget constraints. Operating a highly available Kafka cluster requires specialized knowledge that our 6-person team currently lacks, and we do not have a dedicated infrastructure engineer. Our budget precludes using a fully managed service like Confluent Cloud, and self-hosting would make it impossible to meet the 2-week deadline for delivering business value. We would choose Kafka if we had an order of magnitude more traffic, a larger infrastructure budget, and more engineering capacity.