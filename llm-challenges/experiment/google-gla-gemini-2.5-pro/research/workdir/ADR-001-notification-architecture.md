# ADR-001: Notification Subsystem Architecture

## Status

Proposed

## Context

The current notification system operates synchronously within the HTTP request cycle. This has led to high request latency (up to 8s), request timeouts, and cascading failures due to slow downstream services (email providers, webhooks). The system lacks delivery guarantees, offering no retries or dead-letter queues, which is unacceptable for critical billing notifications that require exactly-once delivery.

The new system must decouple notification processing from web requests, support retries with exponential backoff, and handle a projected 10x traffic increase. Key constraints include a small engineering team (6 people) with no dedicated infrastructure support, no prior Apache Kafka experience, and an existing production Redis instance. The solution must be implemented and deliver value within two weeks.

## Decision

We will use **Redis Streams** as the backbone for the new asynchronous notification subsystem.

The web servers will produce messages (events) onto a Redis stream immediately and return a response to the user. A separate pool of worker processes will consume these messages from the stream using consumer groups, process the notifications (sending emails, webhooks, etc.), and handle retries.

Exactly-once semantics for critical billing notifications will be enforced at the application layer by implementing idempotent consumers. This will be achieved by assigning a unique idempotency key to each critical message at production time and having consumers track processed keys in a separate Redis set or database table before executing the notification logic.

## Consequences

### Pros

- **Low Operational Complexity**: We leverage our existing Redis infrastructure and operational knowledge. This avoids the significant learning curve and management overhead associated with a new, complex distributed system like Kafka.
- **Rapid Implementation**: The team's familiarity with Redis and the simplicity of the client libraries will allow us to meet the two-week deadline for migration.
- **Meets Performance Requirements**: Redis Streams can comfortably handle far more than our current and projected 10x peak traffic, solving the immediate latency and timeout issues.
- **Enables Required Features**: Consumer groups provide a robust mechanism for distributing work and tracking message processing, which is the foundation for at-least-once delivery and building reliable retry logic.

### Cons

- **Application-Level Exactly-Once**: The responsibility for ensuring exactly-once semantics falls on the application code rather than being a core infrastructure guarantee. This requires disciplined implementation of idempotency checks in our consumer logic.
- **Limited Message Retention**: Redis is primarily an in-memory store. While streams can persist to disk (AOF/RDB), it is not a log-based system designed for long-term message replayability in the way Kafka is. This is an acceptable trade-off as our notifications are transient.
- **No Built-in Geo-Replication**: Advanced features like multi-datacenter replication are not part of Redis Streams, which could be a limitation in the very distant future but is not a current requirement.

## Alternatives Considered

### Apache Kafka

Apache Kafka was rejected primarily due to operational complexity and the team's lack of experience. While Kafka offers powerful guarantees, including built-in support for exactly-once semantics and extremely high throughput, the cost of adoption is too high given our constraints.

- **High Operational Burden**: Self-hosting Kafka (and its Zookeeper/KRaft dependency) reliably requires deep expertise that our team does not possess and cannot acquire within the project timeline. This would introduce significant risk to the stability of the entire platform.
- **Prohibitive Cost**: Managed Kafka services like Confluent Cloud would solve the operational problem but are outside our current budget.
- **Steep Learning Curve**: Implementing Kafka producers and consumers correctly, especially to achieve exactly-once semantics, is non-trivial. It would be difficult to meet the two-week deadline without cutting corners that would compromise the system's reliability.

While technically superior in its feature set for this use case, Kafka is the wrong choice for our team's size, budget, and timeline. Redis Streams provides 80% of the benefit for 20% of the cost and complexity.
