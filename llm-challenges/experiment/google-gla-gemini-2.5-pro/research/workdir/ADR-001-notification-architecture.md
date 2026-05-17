# ADR-001: Asynchronous Notification Processing with Redis Streams

- **Status**: Proposed

- **Context**:
  The current synchronous notification system, which handles emails and webhooks, is a major source of instability. It blocks the main request thread, leading to request timeouts (up to 8s), silent failures on endpoint downtime, and cascading failures that have caused two production incidents this year. The system offers no delivery guarantees, which is a critical risk for billing-related notifications. We require a decoupled, asynchronous system that supports retries, guarantees at-least-once delivery (exactly-once for billing), and can scale to 10x traffic without a major re-architecture. Key constraints include a small engineering team with no dedicated infrastructure support, no prior Kafka experience, and a requirement to deliver value within two weeks.

- **Decision**:
  We will use **Redis Streams** as the backbone of the new asynchronous notification subsystem. The Flask backend will produce messages onto a stream, immediately returning a response to the user. A separate group of worker processes will consume these messages, handle the logic of sending emails and webhooks, and manage retries with exponential backoff.

  This decision is justified because it directly addresses the core problems while respecting our operational constraints. It leverages our team's existing familiarity with Redis, minimizing the learning curve and operational overhead. Redis Streams provides the necessary technical features—persistent message logs, consumer groups for load balancing and failure recovery, and at-least-once delivery guarantees—that are sufficient to meet our immediate and 10x scaling requirements. The implementation complexity is low enough to meet the two-week delivery timeline.

- **Consequences**:
  - **Pros**:
    - **Low Operational Complexity**: We already manage Redis in production. Adding Streams is a minimal incremental cost compared to deploying and managing a new, complex distributed system like Kafka.
    - **Rapid Implementation**: The team's familiarity with Redis and the availability of mature Python libraries will allow us to build, test, and deploy the new system within the 2-week constraint.
    - **Sufficient Performance**: Redis Streams can handle tens of thousands of messages per second, far exceeding our projected peak of ~5,000 req/s at 10x scale.
    - **Enables Future Features**: It provides a foundation for real-time WebSocket notifications, a planned feature for the next two quarters.
    - **Cost-Effective**: We avoid the significant costs associated with a managed Kafka service or the engineering hours required to manage a self-hosted cluster.

  - **Cons**:
    - **Application-Layer Exactly-Once Semantics**: Redis guarantees at-least-once delivery. To achieve exactly-once semantics for billing notifications, we must design our consumers to be idempotent (e.g., by tracking processed message IDs). This moves complexity into our application code.
    - **Limited Log Retention**: Message retention is bound by server memory, unlike Kafka's disk-based log which can store data for much longer. This is an acceptable trade-off, as our primary use case is asynchronous processing, not long-term event sourcing.

- **Alternatives Considered**:
  - **Apache Kafka**:
    We rejected Kafka primarily due to operational complexity and team unfamiliarity. Standing up and maintaining a production-grade Kafka cluster (with ZooKeeper or KRaft) is a significant undertaking that our small team is not equipped for without a dedicated infrastructure engineer. The learning curve for both operations and development would violate our two-week delivery constraint. While Kafka offers superior throughput and stronger native support for exactly-once semantics, its capabilities are far beyond our current requirements, making it an unnecessarily complex and costly solution for this problem.
