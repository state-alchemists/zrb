# ADR-001: Notification Subsystem Architecture

## Title
ADR-001: Adopt Redis Streams for Async Notification Subsystem

## Status
Proposed

## Context
Our SaaS project management platform (85,000 MAU, ~500 req/s peak) currently processes notifications (emails and webhooks) synchronously within the HTTP request cycle. This architecture is causing severe reliability and performance issues:
- Request timeouts (spikes up to 8s latency) and cascading failures (connection pool exhaustion).
- Silent notification drops when downstream providers fail, due to a lack of retries or dead-letter queues.
- No delivery guarantees, which is unacceptable for billing-critical events that require exactly-once processing semantics.

We need to decouple notification processing into an asynchronous model that supports retries, handles 10x traffic growth (~5,000 req/s peak), and enables real-time WebSocket push notifications within two quarters. 

Key constraints include a small engineering team (6 engineers, no dedicated infrastructure engineer), a tight deadline (2 weeks to deliver value), no prior Apache Kafka experience, and a modest budget that rules out expensive managed services like Confluent Cloud. We currently operate Redis in production for caching and rate limiting.

## Decision
We will use **Redis Streams** as our message broker for the decoupled notification subsystem. 

**Justification:**
1. **Operational Simplicity & Team Velocity**: We already run Redis in production. Leveraging Redis Streams introduces zero new infrastructural dependencies, allowing our small team to meet the 2-week delivery constraint without needing a dedicated infrastructure engineer.
2. **Throughput Requirements**: Redis can trivially handle our target of 10x growth (~5,000 req/s), as it operates entirely in-memory and can process tens of thousands of operations per second on modest hardware.
3. **Consumer Groups & Retries**: Redis Streams natively supports Consumer Groups, which will allow us to scale out notification processors, ensure messages are acknowledged (`XACK`), and track pending/failed messages (`XPENDING`) to implement robust retry logic and dead-letter queues.
4. **Delivery Guarantees**: While Redis Streams natively provides at-least-once delivery, we will achieve the required **exactly-once semantics for billing notifications** by combining at-least-once delivery with idempotent consumers. We will use our existing PostgreSQL database to track processed message IDs within the same transaction that processes the billing event.
5. **Future WebSockets**: Redis Pub/Sub or Streams can easily act as the backplane for distributing events to stateful WebSocket servers in the future.

## Consequences

**Pros:**
- **Zero new infrastructure overhead:** Eliminates the steep learning curve and maintenance burden of a new clustered datastore.
- **Fast time-to-market:** Fits well within the 2-week limit since the team is already familiar with Redis and the hosting environment is configured.
- **Cost-effective:** Avoids the high licensing or managed-service costs of enterprise event-streaming platforms.
- **Solves current pain points:** Immediately decouples the Flask monolith, eliminating HTTP request blocking and cascading failures.

**Cons:**
- **In-memory constraints:** Message retention is bound by available RAM (using `XTRIM` to cap stream length). We cannot store an infinite historical replay of events like a disk-based log.
- **Manual idempotency required:** We must carefully implement idempotent consumers using PostgreSQL to guarantee exactly-once processing for billing, as Redis does not support distributed cross-system transactions.
- **Durability risks:** Depending on our Redis persistence configuration (AOF/RDB), there is a minor risk of message loss during a catastrophic Redis node failure if fsync hasn't completed.

## Alternatives Considered

**Apache Kafka**
Kafka is the industry standard for distributed event streaming, offering disk-based retention, massive throughput, and robust exactly-once semantics via its transactional API. 

*Why it was rejected:* 
Given our team size (6 engineers), lack of a dedicated infrastructure engineer, and zero prior Kafka experience, self-hosting Kafka (which requires managing ZooKeeper/KRaft quorums, JVM tuning, and disk management) would introduce immense operational risk and easily blow past the 2-week deadline. Furthermore, our budget constraints rule out a fully managed solution like Confluent Cloud. While Kafka is technically superior for massive-scale event sourcing, our target of 5,000 req/s peak is relatively small and can be comfortably handled by our existing Redis infrastructure with drastically lower operational complexity.