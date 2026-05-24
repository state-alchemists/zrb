# ADR-001: Notification Subsystem Architecture Decision

## Status
Proposed

## Context
The existing notification module, part of a Python/Flask monolith, handles emails and webhooks synchronously within the HTTP request cycle. This design has led to:
- **Request timeouts**: Latency spikes to 8s, causing poor user experience.
- **Silent failures**: No retry mechanism or dead-letter queue for failed notifications.
- **Cascading failures**: Slow webhook endpoints have exhausted connection pools, impacting other features.
- **No delivery guarantees**: Critical billing notifications lack at-least-once or exactly-once delivery guarantees.

The scaling targets require decoupling notifications for async processing, supporting retry with exponential backoff, guaranteeing at-least-once delivery (exactly-once for billing events where feasible), and enabling real-time WebSocket push notifications within two quarters. The system must also handle 10x traffic growth (up to ~5000 req/s peak) without re-architecting.

Key constraints:
- Engineering team: 6 people (no dedicated infrastructure engineer), with no prior Kafka experience.
- Existing infrastructure: Redis is already in production for caching and session management.
- Timeline: Must deliver value within 2 weeks of setup/migration.
- Budget: Modest, precluding expensive managed Kafka services like Confluent Cloud at full scale.
- Criticality: Exactly-once semantics for billing notifications.

## Decision
**We will adopt Redis Streams for the asynchronous notification subsystem.**

This decision is primarily driven by the team's existing familiarity with Redis, the modest budget, and the tight 2-week timeline for initial value delivery. Redis Streams provides a robust, battle-tested solution that directly addresses the core problems of decoupling, reliability, and delivery guarantees, while minimizing operational overhead and learning curve for our team.

Redis Streams offers persistent, append-only logs suitable for event streaming. Its consumer groups feature allows multiple consumers to process messages in parallel, ensuring at-least-once delivery. For billing-critical events, exactly-once processing can be achieved by implementing idempotent consumers, a pattern often required regardless of the message broker. Leveraging our existing Redis infrastructure means a faster setup and a reduced total cost of ownership compared to introducing a new, complex system like Kafka. The current and projected 10x traffic growth (up to 5000 req/s) is well within Redis Streams' capabilities, especially with a properly scaled Redis instance.

## Consequences

### Pros
-   **Lower Operational Complexity**: Our team already operates Redis. Integrating Redis Streams leverages existing knowledge and monitoring, significantly reducing the operational burden compared to introducing and self-managing Kafka. This directly aligns with having no dedicated infrastructure engineer.
-   **Faster Time-to-Value**: The 2-week setup/migration constraint is highly achievable with Redis Streams, as it builds on an existing component. Kafka would require a much steeper learning curve and setup time.
-   **Cost-Effective**: No additional infrastructure costs for a new message broker. We can scale our existing Redis instance or add dedicated Redis instances for Streams as needed, which is more budget-friendly than managed Kafka services.
-   **Decoupling and Reliability**: Provides asynchronous processing, consumer groups, and message persistence, addressing request timeouts, silent failures, and cascading failures. At-least-once delivery for general notifications is inherent.
-   **Real-time Capabilities**: Redis is already a strong candidate for real-time applications (e.g., WebSocket push notifications), making it a natural fit for future extensions of the notification system.

### Cons
-   **Long-Term Retention**: While Redis Streams supports persistence, it is generally not optimized for petabyte-scale, multi-year data retention typically associated with Kafka for event sourcing or data lakes. This is not a primary requirement for notifications but is a general difference.
-   **Application-Level Idempotency for Exactly-Once**: While at-least-once is built-in, true exactly-once semantics for billing-critical events will require careful implementation of idempotent consumers within our application logic, as Redis Streams does not provide transactional guarantees across multiple external services. This is a common pattern but adds application complexity.
-   **Scalability Ceiling**: While sufficient for 10x growth, Redis Streams might hit a scalability ceiling earlier than a highly distributed Kafka cluster in extremely high-throughput, global-scale scenarios. However, for the described 5000 req/s peak, it is more than adequate.

## Alternatives Considered

### Apache Kafka
Kafka was considered due to its industry-leading capabilities as a distributed streaming platform, offering high throughput, robust durability, and strong delivery guarantees, including built-in exactly-once semantics with appropriate configurations.

However, Kafka was rejected primarily due to the following constraints:
-   **Operational Complexity**: The engineering team has no Kafka experience and lacks a dedicated infrastructure engineer. Self-hosting Kafka requires significant expertise in cluster management, monitoring, and troubleshooting, making it a high-risk option for a team with limited resources and experience in this domain.
-   **Setup Time & Budget**: The requirement to deliver value within 2 weeks is incompatible with the steep learning curve and complex setup involved in deploying and configuring a production-ready Kafka cluster. Furthermore, the modest budget precludes the use of fully managed Kafka services (like Confluent Cloud) that would mitigate some of the operational burden.
-   **Resource Intensive**: Kafka clusters typically require more dedicated resources and compute power compared to adding Streams functionality to an existing Redis instance.

While Kafka offers superior capabilities for long-term event sourcing and massive data pipelines, its overhead and complexity are disproportionate to our immediate needs and team capabilities. The trade-off between its advanced features and the operational burden makes it an unsuitable choice under the current constraints, especially when Redis Streams can adequately meet all critical requirements.
