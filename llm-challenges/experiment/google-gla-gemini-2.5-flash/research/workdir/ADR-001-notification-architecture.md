# ADR-001: Notification Subsystem Architecture

## Status
Proposed

## Context
The existing notification module, part of a Python/Flask monolith, handles emails and webhooks synchronously within the HTTP request cycle. This approach has led to significant problems: request timeouts (average 800ms, spikes to 8s), silent failures for undeliverable notifications, cascading failures due to connection pool exhaustion from slow webhook endpoints, and a lack of delivery guarantees for critical billing notifications.

The goal is to decouple notification processing from the main request cycle, enabling asynchronous processing, retry mechanisms with exponential backoff, and robust delivery guarantees (at-least-once for general events, exactly-once for billing-critical events). The system must scale to 10x current traffic (~5000 req/s peak) and support future real-time WebSocket push notifications within two quarters.

Key constraints include a small engineering team (6 people, no dedicated infrastructure engineer), existing Redis infrastructure, no prior Kafka experience, a strict two-week setup/migration timeline for initial value delivery, and a modest budget that precludes managed Kafka at full scale.

## Decision
We choose **Redis Streams** for the new notification subsystem.

This decision prioritizes leveraging existing team knowledge and infrastructure, minimizing operational complexity, and adhering to the tight timeline and budget constraints. Redis is already in production for session management and rate limiting, reducing the learning curve and deployment overhead significantly.

Redis Streams natively support:
*   **Asynchronous processing**: Messages are published to a stream and consumed by a separate worker process.
*   **At-least-once delivery**: With consumer groups, messages are acknowledged, and unacknowledged messages can be reprocessed.
*   **Consumer groups**: Allow multiple consumers to process messages from a stream in parallel, distributing the load and providing scalability.
*   **Message retention**: Configurable to support retry and replay scenarios.

While achieving exactly-once semantics for billing notifications will require careful application-level design (e.g., idempotent consumers, transaction logs in PostgreSQL), the overall operational simplicity and faster time-to-value offered by Redis Streams are critical for our team given the current constraints. The anticipated 10x traffic growth (to ~5000 req/s) is well within the capabilities of a properly configured Redis Streams setup for this use case.

## Consequences

**Pros:**
*   **Low Operational Overhead**: Leverages existing Redis infrastructure and team familiarity, significantly reducing the learning curve and deployment complexity compared to Kafka.
*   **Rapid Development & Deployment**: The two-week setup/migration timeline is highly achievable, allowing the team to deliver value quickly.
*   **Cost-Effective**: Avoids the immediate need for a separate, potentially expensive, managed Kafka cluster or the significant operational cost of self-hosting Kafka.
*   **Good Performance & Scalability**: Redis Streams can handle the projected 10x traffic growth for notifications and is well-suited for real-time WebSocket integration.
*   **Fits Team Skillset**: The team already operates Redis, making troubleshooting and maintenance more straightforward.
*   **At-Least-Once Delivery**: Built-in support for reliable message processing with consumer groups.

**Cons:**
*   **Exactly-Once Semantics**: While achievable, it requires more explicit application-level logic (e.g., using a transaction log/deduplication key in the consumer) compared to Kafka's native transactional producers/consumers.
*   **Scalability Ceiling**: While sufficient for the projected 10x growth, Redis Streams may not offer the same extreme scalability or fault tolerance as a highly distributed Kafka cluster in highly specialized, ultra-high-throughput scenarios or for very long-term, large-scale data retention/replay.
*   **Ecosystem Maturity**: The event streaming ecosystem around Redis Streams is less mature and extensive than Kafka's, potentially requiring more custom tooling for advanced use cases (e.g., complex stream processing, deep analytics).
*   **Monitoring**: Generic Redis monitoring tools will be used; specific stream monitoring might require custom dashboards.

## Alternatives Considered

### Apache Kafka
Kafka was considered due to its industry-leading capabilities for high-throughput, fault-tolerant, and scalable event streaming.

**Reasons for Rejection:**
*   **High Operational Complexity**: Kafka introduces a significant operational burden, requiring dedicated expertise for setup, configuration, monitoring, and maintenance. Our small engineering team with no dedicated infrastructure engineer and no prior Kafka experience would struggle to manage a self-hosted Kafka cluster effectively.
*   **Steep Learning Curve**: The team would need substantial time to learn Kafka's concepts (brokers, topics, partitions, Zookeeper/Kraft, consumer groups, offsets, compaction) and best practices, directly conflicting with the < 2 weeks setup/migration constraint.
*   **Budget Constraints**: While managed Kafka services like Confluent Cloud offer operational relief, they can be costly at full scale, violating our modest budget. Self-hosting, while cheaper in licenses, is more expensive in engineering time and potential outages.
*   **Time-to-Value**: The initial setup and learning curve would likely push delivery of value well past the two-week target, delaying critical decoupling efforts.
*   **Overkill for Initial Needs**: While powerful, Kafka's full capabilities (e.g., massive long-term data retention, complex stream processing at petabyte scale) are beyond the immediate requirements for a notification subsystem. Redis Streams can meet the core requirements with less overhead.