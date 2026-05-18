# ADR-001 — Use Redis Streams for Asynchronous Notifications

- **Status**: Proposed

## Context

Our monolithic Python/Flask application currently processes notifications (emails, webhooks) synchronously within the HTTP request cycle. With 85,000 MAU and peak traffic of 500 req/s, this architecture is causing 800ms–8s latencies, silent data drops on third-party API failures, and cascading connection pool exhaustion. 

We need to decouple notifications into an asynchronous queue that supports retries, exponential backoff, and at-least-once delivery (with exactly-once semantics for critical billing events). The solution must handle a 10x traffic increase (5,000 req/s) and future WebSocket real-time push capabilities. 

Crucial constraints:
- **Team**: 6 engineers, 0 dedicated infrastructure engineers, no prior Kafka experience.
- **Timeline**: Implementation must deliver value within 2 weeks.
- **Infrastructure**: We already operate Redis in production. Budget is tight, ruling out premium managed messaging services like Confluent Cloud.

## Decision

We will use **Redis Streams** as the message broker for the notification subsystem.

**Justification:**
Given the strict 2-week implementation constraint and lack of infrastructure engineers, introducing a new, operationally complex technology like Kafka is too risky. Redis is already part of our production stack. 

Our target throughput (10x growth = 5,000 req/s) is trivial for Redis Streams to handle. Redis Streams provides native support for **consumer groups**, allowing us to reliably distribute work among worker processes, track acknowledged messages, and implement a dead-letter queue (via `XPENDING` and `XCLAIM`) for retry and backoff logic. 

To satisfy the **exactly-once semantics** required for billing notifications, we will leverage Redis Streams' at-least-once delivery guarantee combined with consumer-side idempotency. Workers will use unique event IDs and database transaction locks in PostgreSQL to ensure duplicate messages do not result in double-billing.

## Consequences

**Pros:**
- **Zero operational overhead:** We leverage our existing Redis infrastructure, eliminating the need to provision, monitor, and maintain a new distributed system.
- **Speed of execution:** The team can implement this well within the 2-week deadline using standard Python Redis libraries.
- **Built-in consumer groups:** Provides the necessary primitives for message acknowledgment, horizontal scaling of workers, and handling failures/retries.

**Cons:**
- **Message retention limits:** Unlike disk-based brokers, Redis stores messages in RAM. We cannot afford long-term **message retention**. We must actively trim the stream (`XADD ... MAXLEN`) once messages are processed or moved to a permanent Postgres DLQ.
- **Application-level exactly-once:** Redis does not support transactional exactly-once messaging across the broker. The burden of idempotency falls entirely on the application code and database layer.
- **Persistence risks:** If Redis goes down, unacknowledged messages might be lost depending on our AOF (Append Only File) sync configuration. We must ensure Redis persistence is tuned for durability, not just caching.

## Alternatives Considered

- **Apache Kafka:** Kafka is the industry standard for high-throughput event streaming. It offers cheap disk-based message retention, strict **ordering guarantees** per partition, and native **exactly-once semantics** (via Kafka Transactions). 
  *Why rejected:* **Operational complexity**. Self-hosting Kafka requires managing KRaft/ZooKeeper quorums, partition rebalancing, and JVM tuning, which our 6-person team cannot support. Our budget prohibits managed Confluent Cloud. Furthermore, learning and deploying Kafka securely would easily violate our 2-week setup constraint, and our peak 10x target (5,000 req/s) does not justify Kafka's massive scale capabilities.