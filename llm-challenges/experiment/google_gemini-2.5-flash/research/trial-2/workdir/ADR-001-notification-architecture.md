Title: ADR-001 Notification Subsystem Architecture
Status: Proposed
Context:
The existing notification module, embedded within the synchronous HTTP request cycle of our Python/Flask monolith, is causing significant issues: request timeouts, silent failures, cascading failures due to slow external endpoints, and a lack of delivery guarantees for critical billing notifications. We need to decouple notifications for asynchronous processing, implement retry mechanisms with exponential backoff, guarantee at-least-once delivery for all notifications, and where feasible, provide exactly-once delivery for billing-critical events. The new system must support future real-time WebSocket push notifications and scale to 10x current traffic.

Our engineering team consists of 6 people (3 senior, 3 mid-level) with no dedicated infrastructure engineer. We currently use Redis for session storage and rate limiting, but have no Kafka experience. The solution must be implemented within two weeks to deliver value and fit a modest budget, meaning managed Kafka solutions like Confluent Cloud are not immediately viable at full scale.

Decision:
We choose **Redis Streams** as the foundation for our asynchronous notification subsystem.

Consequences:
Pros:
*   **Leverages existing infrastructure and team knowledge**: We already operate Redis in production, reducing the operational overhead and learning curve for the team. This directly addresses the constraint of no dedicated infrastructure engineer and limited setup/migration time.
*   **Simple to get started**: Redis Streams offer a straightforward API for producers and consumers, allowing for rapid decoupling of the notification logic. The `XADD`, `XREADGROUP`, and `XACK` commands are intuitive.
*   **Stream processing primitives**: Redis Streams provide consumer groups, message acknowledgement, and automatic pending entry list (PEL) management, enabling robust at-least-once delivery semantics for all notifications.
*   **Exactly-once semantics (feasible)**: While not strictly "exactly-once" for every message by default in the Kafka sense, Redis Streams, when combined with idempotent consumer logic and transactional writes to our PostgreSQL database, can effectively achieve exactly-once processing for critical billing notifications. We can store the last processed ID in PostgreSQL to ensure idempotency and prevent reprocessing of acknowledged messages.
*   **Low operational cost**: A single Redis instance can handle initial scaling requirements, and horizontal scaling with multiple Redis instances and proxy layers is feasible for future growth, fitting our modest budget.
*   **Good for real-time WebSocket push**: Redis Pub/Sub (or even Redis Streams themselves with dedicated consumers) is a natural fit for real-time WebSocket push notifications, aligning with our future scaling target.
*   **Built-in message retention**: Redis Streams allow configuring a maximum length, providing a form of message retention without external storage.

Cons:
*   **Scalability limits (eventual)**: While sufficient for 10x growth, Redis Streams may eventually hit limitations compared to dedicated distributed systems like Kafka for extremely high throughput or very long-term message retention requirements across many terabytes. This would require sharding or a re-evaluation later.
*   **Lack of advanced features**: Redis Streams lack some of Kafka's more advanced features like complex stream processing (joins, aggregations) via tools like Kafka Streams or KSQL, schema registry, or robust multi-datacenter replication out-of-the-box. However, these are not immediate requirements.
*   **Durability and persistence**: While Redis persistence (RDB snapshots, AOF) can be configured, it requires careful tuning to balance performance and recovery time. Kafka's append-only log model provides stronger guarantees for durability by default.

Alternatives Considered:
**Apache Kafka**:
Rejected due to the following reasons:
*   **High operational complexity**: Kafka is a distributed system that requires significant expertise to set up, monitor, and scale correctly. Our team lacks Kafka experience and a dedicated infrastructure engineer, making the operational burden a high risk.
*   **High learning curve**: The entire team would need to learn Kafka concepts, tooling, and best practices, which would exceed our "2 weeks of setup/migration work" constraint.
*   **Budget constraints**: While self-hosting is an option, it negates some of the operational benefits. Managed Kafka solutions are currently beyond our modest budget for full-scale deployment.
*   **Overkill for initial needs**: For our immediate problem and scaling targets (10x current traffic), Kafka's full feature set and distributed complexity are an over-engineered solution given our team's constraints. While it offers superior long-term scalability and advanced features, the immediate cost in complexity and time is too high.
*   **Exactly-once semantics complexity**: While Kafka supports exactly-once processing, implementing it correctly also adds complexity (e.g., using producer transactions, consumer idempotence, and careful offset management) that would be challenging for a team without prior experience.
