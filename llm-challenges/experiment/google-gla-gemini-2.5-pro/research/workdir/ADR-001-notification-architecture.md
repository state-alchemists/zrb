# ADR-001: Notification Subsystem Architecture

## Status

Proposed

## Context

The current notification system operates synchronously within the HTTP request cycle. This has led to increased response latency, request timeouts, and cascading failures under load. Critical billing notifications lack delivery guarantees (at-least-once or exactly-once), and failures are not retried. The system must be decoupled to run asynchronously, support retries, provide stronger delivery guarantees, and scale to handle 10x traffic growth, all while being manageable by a small engineering team with no dedicated infrastructure support.

## Decision

We will use **Redis Streams** as the backbone for the new asynchronous notification subsystem.

The web servers will produce notification jobs to a Redis stream. A separate pool of worker processes will consume from this stream, process the notifications (emails, webhooks), and handle retries with exponential backoff.

**Justification:**

1.  **Operational Simplicity:** Our team already manages a production Redis instance. Using Streams is a low-friction extension of our existing infrastructure, minimizing the learning curve and operational burden. This is critical for a small team with no dedicated infrastructure engineer.
2.  **Rapid Implementation:** Given our existing Redis expertise, we can build, test, and deploy a Streams-based solution within the required 2-week timeframe. This allows us to solve the immediate performance and reliability problems quickly.
3.  **Sufficient Performance:** Redis Streams can comfortably handle the projected 10x traffic increase (~5k messages/sec). It provides the necessary primitives like consumer groups for parallel processing and message acknowledgments for reliable delivery.
4.  **Cost-Effectiveness:** This approach leverages our existing Redis deployment, avoiding the significant cost associated with a managed Kafka service or the engineering hours required to self-host a Kafka cluster.

## Consequences

### Pros

-   **Low Operational Overhead:** No new infrastructure components to learn, manage, or monitor.
-   **Leverages Existing Skills:** The team can be immediately productive without extensive training.
-   **Fast Time-to-Market:** The core problem of decoupling notifications can be solved in days, not weeks.
-   **Meets Core Requirements:** Provides ordered, at-least-once delivery, consumer groups for scaling, and a persistent message log suitable for the notification workload.

### Cons

-   **Application-Level Exactly-Once:** Redis does not natively support exactly-once semantics. We must implement idempotency in our consumer logic (e.g., by tracking processed message IDs in PostgreSQL) to meet the requirement for billing notifications. This adds a small amount of application complexity.
-   **Less Robust Retention:** While Redis streams are persistent, they are not designed for the long-term, high-volume log retention that Kafka excels at. This is an acceptable trade-off for our notification use case.
-   **Ecosystem:** Kafka has a more mature and extensive ecosystem of tools for stream processing and data integration (e.g., Kafka Connect, ksqlDB), which we will not be able to leverage.

## Alternatives Considered

### Apache Kafka

Apache Kafka is the industry standard for high-throughput, durable streaming. It offers powerful features like tunable consistency, guaranteed ordering within partitions, and robust, long-term message retention.

We rejected Kafka for the following reasons:

1.  **High Operational Complexity:** Self-hosting Kafka (and its Zookeeper/KRaft dependency) is notoriously complex. It would introduce a significant operational and maintenance burden on our small team, diverting focus from product development.
2.  **Lack of Team Experience:** No one on the team has prior experience running Kafka in production. The learning curve is steep, and the risk of misconfiguration leading to downtime or data loss is high.
3.  **Violates Timeline & Budget Constraints:** Properly setting up a production-ready Kafka cluster would exceed our 2-week timeline. Furthermore, a managed service like Confluent Cloud, which would mitigate the operational complexity, is outside our current budget.
4.  **Over-Engineering:** For the immediate problem of decoupling notifications, Kafka is more powerful than necessary. The complexity it introduces outweighs its benefits for this specific use case at our current scale.
