# ADR-001: Notification Subsystem Architecture

## Status
Proposed

## Context
Our SaaS project management platform currently processes notifications (emails and webhooks) synchronously within the HTTP request cycle. At our current scale (85,000 MAU, ~2M tasks/month, 500 req/s peak), this synchronous architecture is causing frequent request timeouts, silent failures when external providers are down, and dangerous cascading system failures due to connection pool exhaustion. Furthermore, we lack delivery guarantees, particularly the exactly-once delivery required for billing events. 

We need to decouple notifications into an asynchronous, message-driven architecture capable of supporting a 10x traffic increase (~5,000 req/s), exponential backoff retries, and a planned transition to real-time WebSocket push notifications within two quarters. 

Critically, we operate under strict constraints: a 6-person engineering team with no dedicated infrastructure engineer, a modest budget that rules out expensive managed services, an existing Redis/Postgres footprint, and a strict maximum of 2 weeks of setup/migration time before delivering value. The two leading candidates evaluated for the message broker are **Apache Kafka** and **Redis Streams**.

## Decision
We will use **Redis Streams** as the message broker for the notification subsystem.

Given our operational constraints, Redis Streams provides the optimal balance of performance, required messaging primitives, and zero-infrastructure-overhead adoption. We will utilize Redis Consumer Groups (`XREADGROUP`) to distribute notification workloads across background Python workers, enabling horizontal scalability and automatic tracking of pending messages for retry logic.

To satisfy the "exactly-once" delivery requirement for billing events without Kafka's native transactional APIs, we will implement the **Idempotent Consumer pattern**. Consumers will process billing events and write a unique idempotency key (derived from the Redis message ID or domain event) into our existing PostgreSQL database within the same transaction as the business state update.

### Justification against Technical Properties:
*   **Operational Complexity:** Redis is already running in production for session management and rate limiting. Deploying Redis Streams requires zero additional infrastructure provisioning, perfectly fitting our 2-week timeline constraint and accommodating our lack of a dedicated infrastructure engineer.
*   **Throughput:** Redis easily handles hundreds of thousands of operations per second in memory. Our 10x target of 5,000 req/s is well within a single Redis node's capability.
*   **Consumer Groups:** Redis Streams natively supports consumer groups, allowing us to safely distribute webhook and email processing across multiple background worker instances and handle scaling dynamically.
*   **Ordering Guarantees:** Redis Streams appends messages sequentially and maintains strict time-based ordering within a stream, which is sufficient for sequential task update notifications.

## Consequences

### Pros
*   **Immediate Velocity:** Development can start immediately without learning a new ecosystem or provisioning new infrastructure. Fits easily inside the 2-week limit.
*   **Low Operational Burden:** No ZooKeeper/KRaft clusters to manage, no JVM tuning, and no need to hire an infrastructure engineer. 
*   **Built-in Reliability Tools:** Commands like `XPENDING` and `XCLAIM` allow us to seamlessly build exponential backoff retries and dead-letter queue (DLQ) mechanisms for failed webhooks.
*   **Budget-Friendly:** Leverages our existing AWS infrastructure footprint without requiring premium managed services like Confluent Cloud.

### Cons
*   **Message Retention is RAM-bound:** Unlike disk-backed Kafka logs, Redis stores streams in memory. We must rigorously configure maximum stream lengths (using `MAXLEN ~`) to prevent OOM (Out of Memory) crashes, limiting our ability to replay historical data over long periods.
*   **Application-level Exactly-Once Semantics:** Redis does not have native exactly-once transactional guarantees across multiple systems. The engineering team must strictly enforce idempotency in consumer logic (via Postgres unique constraints) rather than relying on the broker.
*   **Durability Risks:** Depending on our Redis persistence configuration (AOF/RDB), a sudden node crash could result in sub-second data loss of un-synced events, unlike Kafka's synchronous disk-replication models.

## Alternatives Considered

**Apache Kafka**
Kafka is the industry standard for high-throughput, highly durable event streaming. It natively provides disk-based **message retention** for virtually unlimited periods, robust **consumer groups**, and native **exactly-once semantics** via its transactional API. 

*Why it was rejected:* 
Despite its superior durability and native delivery guarantees, Kafka was rejected due to its massive **operational complexity**. Self-hosting Kafka requires managing ZooKeeper/KRaft, partitioning, and JVM memory—tasks our 6-person team cannot absorb without a dedicated infrastructure engineer. A fully managed solution (like Confluent Cloud) exceeds our "modest budget" constraint. Furthermore, the steep learning curve for a team with zero Kafka experience guarantees we would fail the "2 weeks to deliver value" constraint. For our target of 5,000 req/s, Kafka's raw scale is unnecessary, and the operational tax heavily outweighs the architectural benefits.