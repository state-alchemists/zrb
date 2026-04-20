# ADR-001: Notification Subsystem Architecture

## Status

Proposed

## Context

The current notification system operates synchronously within the main application's HTTP request cycle. This architecture has led to significant performance and reliability issues, including request timeouts, silent failures with no retries, and cascading failures that impact the entire platform. Critical billing-related notifications lack the "exactly-once" delivery guarantee required for financial operations.

The new system must decouple notification processing from user requests, support at-least-once delivery for general notifications and exactly-once for billing events, and be capable of handling 10x traffic growth.

This decision is constrained by a small engineering team (6 people) with no dedicated infrastructure engineer, no prior experience with Apache Kafka, and an existing production Redis instance. The solution must deliver value within two weeks.

## Decision

We will use **Redis Streams** as the backbone of the new asynchronous notification subsystem.

The monolith will publish notification-request events to a Redis Stream. A separate pool of worker processes will consume events from this stream, process them, and handle interactions with third-party services like email providers and webhooks.

This choice is justified by:
1.  **Operational Simplicity**: Redis is already part of our production infrastructure. Using Streams introduces no new systems to manage, monitor, or learn. This is the most critical factor for our small team, which lacks a dedicated operations engineer.
2.  **Existing Expertise**: Our team is already familiar with Redis, which allows us to meet the aggressive two-week timeline. Introducing Kafka would require significant time for training and implementation, creating unacceptable project risk.
3.  **Sufficient Performance**: Redis Streams can easily handle the throughput required for our 10x scaling target (~5,000 req/s). While Kafka offers higher theoretical throughput, it is overkill for our current and projected needs.
4.  **Meeting Core Requirements**: Redis Streams provides consumer groups for load balancing, message ordering guarantees within a stream, and at-least-once delivery semantics out of the box. Exactly-once semantics for billing events will be achieved at the application level through idempotent consumer logic, which is a manageable engineering task.

## Consequences

### Pros:
-   **Low Operational Overhead**: We leverage our existing Redis deployment, avoiding the significant complexity of setting up, managing, and monitoring a Kafka cluster (and its Zookeeper/KRaft dependency).
-   **Fast Time to Value**: The team can be productive immediately, making the two-week migration goal realistic.
-   **Cost-Effective**: We avoid the costs associated with a managed Kafka service or the engineering hours required for a self-hosted cluster.

### Cons:
-   **Weaker Data Durability**: Redis is primarily an in-memory store. While persistence (AOF) provides good durability, it is less robust than Kafka's disk-first architecture. A catastrophic Redis failure could lead to the loss of a few seconds of data. This risk is acceptable for most notifications, and mitigation strategies can be applied for critical ones.
-   **Application-Level Exactly-Once**: Achieving exactly-once semantics requires building idempotent logic into our consumers (e.g., tracking processed message IDs). This places a moderate burden on application code, whereas Kafka provides stronger transactional primitives to build upon.
-   **Potential Future Migration**: If the system grows 50-100x, we may eventually need to migrate to a more purpose-built system like Kafka. However, Redis Streams is the correct-sized solution for now and for the foreseeable future.

## Alternatives Considered

### Apache Kafka

We rejected Apache Kafka primarily due to **prohibitive operational complexity**.

-   **High Operational Burden**: Self-hosting Kafka is a complex undertaking that would require a dedicated infrastructure engineer, which we do not have. Managed solutions (like Confluent Cloud) are beyond our current budget.
-   **Steep Learning Curve**: With no Kafka experience on the team, the ramp-up time would violate our two-week delivery constraint.
-   **Over-provisioning**: Kafka is a powerful system designed for massive, multi-terabyte log streaming. Its feature set (e.g., infinite log retention, complex topic management) is far more than what our notification system requires. The benefits do not justify the immense operational cost and risk for a team of our size and experience.
