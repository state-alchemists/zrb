
# ADR-001: Notification Subsystem Architecture

- **Status**: Proposed

## Context

The current notification system operates synchronously within the HTTP request cycle. This architecture has led to request timeouts, silent data loss when downstream services fail, and cascading system failures due to connection pool exhaustion. Key business requirements, such as exactly-once delivery for billing notifications, are not met.

The new system must decouple notification processing from web requests, support retries, guarantee at-least-once delivery for most notifications, provide exactly-once semantics for critical billing events, and scale to 10x the current traffic. The decision is constrained by a small engineering team with no dedicated infrastructure support, no prior Kafka experience, and an existing Redis deployment. A solution must be viable within a two-week implementation timeframe.

## Decision

We will use **Redis Streams** as the backbone of the new asynchronous notification subsystem.

A producer (the Flask web application) will `XADD` notification events to a Redis stream. One or more independent consumer groups, running as separate processes, will read from the stream using `XREADGROUP`. This immediately decouples the web servers from the notification logic, resolving the latency and cascading failure issues.

This decision is justified because:
1.  **Low Operational Complexity**: The team already manages a production Redis instance. Using Streams is a feature extension of a known technology, not a net-new system to learn and maintain. This is critical for a team without dedicated infrastructure support.
2.  **Rapid Implementation**: Given the team's familiarity with Redis, a prototype and initial migration can be completed well within the two-week constraint.
3.  **Meets Core Requirements**: Redis Streams provides persistence, consumer groups for load balancing and failure recovery, and at-least-once delivery semantics via its acknowledgment mechanism (`XACK`). These features satisfy the primary requirements for decoupling, retries, and basic delivery guarantees.
4.  **Sufficient for Scale**: While not a distributed log on the scale of Kafka, a properly configured Redis instance can handle the projected 10x traffic growth (~5000 events/sec) without issue.
5.  **Achievable Exactly-Once Semantics**: Exactly-once processing for billing notifications can be implemented at the application layer. A consumer can use Redis transactions (MULTI/EXEC) or Lua scripting to atomically process a message and store the last processed ID in Redis, preventing duplicate processing. This is a tractable engineering problem that doesn't require the complex infrastructure of Kafka's EOS.

## Consequences

### Pros
- **Leverages Existing Expertise**: The team can move quickly without a steep learning curve.
- **Minimal Infrastructure Overhead**: We avoid the need to deploy, monitor, and manage a complex new distributed system like Kafka and its dependencies (e.g., Zookeeper/KRaft).
- **Fast Time to Value**: The solution directly addresses the core problems of latency and reliability within the required timeline.
- **Cost-Effective**: Avoids the high costs of managed Kafka services and the operational cost of a self-hosted cluster.

### Cons
- **Limited Long-Term Durability**: Redis is primarily an in-memory system, though it has persistence options (AOF, RDB). It is not a durable, replicated log in the same way as Kafka. An unrecoverable Redis failure could lead to data loss, making point-in-time recovery more complex.
- **Not a Specialized Tool**: Redis is a multi-purpose tool. As the system scales far beyond the 10x target, contention with other Redis use cases (caching, sessions) could become an issue.
- **Application-Layer Complexity**: Achieving exactly-once semantics places the implementation burden entirely on the consumer application logic.

## Alternatives Considered

### Apache Kafka

Apache Kafka is the industry standard for high-throughput, distributed event streaming. It offers superior durability, massive scalability, and built-in support for exactly-once semantics (EOS).

We rejected Kafka for the following reasons:
1.  **High Operational Complexity**: A self-hosted Kafka cluster requires significant expertise to configure, tune, and maintain, especially for a small team with no prior experience. This violates our primary constraint of having no dedicated infrastructure engineer.
2.  **Steep Learning Curve**: The concepts of topics, partitions, brokers, consumer lag, and the complexities of Kafka's EOS would require a significant time investment from the team, delaying the project beyond the two-week requirement.
3.  **High Cost**: While self-hosting is an option, the operational cost is high. Managed services like Confluent Cloud or Amazon MSK would exceed our modest budget.
4.  **Over-provisioning for Current Needs**: For the immediate problem and 10x scale target, Kafka's capabilities are in excess of our requirements. The operational trade-off is not justified at this stage of the product's lifecycle. Redis Streams provides a more pragmatic, right-sized solution for our current context.
