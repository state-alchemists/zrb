**Title**: ADR-001: Asynchronous Notification Subsystem Architecture

**Status**: Proposed

**Context**
Our existing synchronous notification module, responsible for sending emails and webhooks, is causing significant operational issues: request timeouts, silent failures, and cascading system failures due to blocking I/O. We currently lack robust delivery guarantees, particularly for critical billing notifications which require at-least-once, and ideally exactly-once, delivery.

The goal is to decouple notification processing from the HTTP request cycle, implement retry mechanisms with exponential backoff, guarantee at-least-once delivery for all notifications and exactly-once for billing events, support future real-time WebSocket push notifications, and scale to 10x our current traffic (5000 req/s peak) without significant re-architecture.

Key constraints include:
*   A small engineering team (6 people) with no dedicated infrastructure expertise.
*   Existing in-production Redis instance.
*   No prior team experience with Apache Kafka.
*   Strict timeline: initial value delivery within 2 weeks.
*   Modest budget, precluding expensive managed Kafka solutions at full scale.
*   Mandatory exactly-once semantics for billing notifications.

**Decision**
We will implement the asynchronous notification subsystem using **Redis Streams**.

This decision is primarily driven by the immediate operational and team constraints. Given our small engineering team, lack of Kafka experience, existing Redis infrastructure, and tight 2-week delivery timeline, Redis Streams offers a significantly lower barrier to entry and operational overhead compared to a new, self-managed Kafka deployment. Leveraging an existing, familiar technology reduces the learning curve, simplifies deployment, and minimizes the risk of unforeseen infrastructure challenges.

While Kafka offers more robust native exactly-once semantics and higher theoretical throughput at extreme scales, Redis Streams can pragmatically meet our scaling targets (10x traffic, up to 5000 req/s peak) and delivery guarantees (at-least-once, with effectively-once for billing via idempotent consumer processing and persistent tracking of message IDs within consumer groups). The ability to quickly integrate with our existing Flask backend and Redis cache is critical for achieving value within the specified timeframe.

**Consequences**

*   **Pros**:
    *   **Faster Time-to-Value**: Immediate leverage of existing Redis infrastructure and team familiarity will enable rapid development and deployment, meeting the 2-week deadline for initial value delivery.
    *   **Lower Operational Complexity**: We avoid introducing a new, complex distributed system (Kafka) which would require significant learning, setup, and ongoing maintenance from a small team with no dedicated infrastructure engineer.
    *   **Cost-Effective**: No additional infrastructure costs beyond potentially scaling up our existing Redis instance. Avoids the high cost of managed Kafka services.
    *   **Strong Support for Core Requirements**: Redis Streams natively supports message ordering, consumer groups, and persistent message logs necessary for async processing, retry mechanisms, and at-least-once delivery.
    *   **Future-Proofing for WebSockets**: Redis Pub/Sub capabilities, often used in conjunction with Streams, provide a straightforward path for integrating real-time WebSocket push notifications within 2 quarters.

*   **Cons**:
    *   **Exactly-Once Semantics require careful implementation**: Achieving truly exactly-once semantics for billing notifications in Redis Streams requires diligent client-side implementation of idempotent processing and persistent tracking of last-processed message IDs per consumer group in our PostgreSQL database. This is not as natively integrated as Kafka's transactional APIs.
    *   **Throughput Scalability Ceiling**: While sufficient for 10x current traffic, Redis Streams may have a lower ultimate throughput ceiling compared to a highly optimized Kafka cluster for massive, multi-million message/second workloads. This is a long-term concern, but not an immediate blocker for our stated scaling target.
    *   **Monitoring & Tooling Maturity**: While Redis has excellent monitoring, the ecosystem around Redis Streams for deep message tracing and debugging might be less mature or feature-rich compared to Kafka's extensive tooling.

**Alternatives Considered**

**Apache Kafka**
Kafka was rejected primarily due to the significant operational burden and learning curve it would impose on our small engineering team and modest budget.
*   **Operational Complexity**: Deploying and managing a production-grade Kafka cluster, especially without prior experience or a dedicated infrastructure engineer, is a complex, time-consuming, and error-prone endeavor. This directly conflicts with our 2-week setup/migration constraint.
*   **Cost**: While open-source Kafka is free, running it reliably at scale requires significant operational effort or costly managed services (e.g., Confluent Cloud). The latter is explicitly outside our current budget constraints.
*   **Time-to-Value**: The steep learning curve for development, deployment, and operational best practices would prevent us from delivering value within the critical 2-week timeframe.
*   **Overkill for Initial Scale**: While Kafka offers superior raw throughput for extreme scale, our immediate 10x scaling target (up to 5000 req/s) is well within Redis Streams' capabilities, making Kafka an over-engineered solution for our current stage given the team and budget constraints.
*   **Lack of Existing Expertise**: The team has no Kafka experience, which would necessitate significant training and ramp-up time, impacting project timelines and increasing risk.

While Kafka's native support for exactly-once semantics is compelling, the practical challenges of adoption for our team outweighed this benefit, especially since "effectively once" can be achieved with Redis Streams for critical billing events through careful consumer design.