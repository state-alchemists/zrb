# Title: Notification Subsystem Architecture Decision

## Status: Proposed

## Context

The current notification system in our SaaS project management platform is leading to performance and reliability problems. Notifications are sent synchronously within the HTTP request cycle, causing significant latency spikes and occasional silent failures. The system lacks a retry mechanism and delivery guarantees, creating cascading failures and missing critical notifications. Our goal is to decouple notifications, support retry mechanisms, guarantee at-least-once delivery, and handle a projected 10x growth. Constraints include a lack of Kafka experience, modest budget, minimal setup time, and existing Redis production use.

## Decision

We will implement the notification subsystem using **Redis Streams**.

Redis Streams aligns well with our existing infrastructure, supporting near real-time data streams without requiring significant additional operational overhead. It offers at-least-once delivery semantics, crucial for our billing notifications. Although it doesn't provide exactly-once semantics natively, we can implement idempotency at the application level for these critical paths. Redis Streams also integrates seamlessly with our current Redis deployment, minimizing setup time and cost.

## Consequences

### Pros
- **Quick to Deploy**: Leverages existing Redis infrastructure, reducing setup and operational complexity.
- **Cost-Effective**: Avoids new infrastructure costs, fitting within our budget.
- **Simplified Operations**: Relies on familiar stack components, reducing training overhead.

### Cons
- **Limited Exactly-Once Support**: Requires additional logic for idempotency to achieve exactly-once delivery.
- **Scalability Constraints**: While sufficient now, may require sharding or additional nodes if load increases significantly beyond current projections.

## Alternatives Considered

### Apache Kafka

We rejected Apache Kafka primarily due to its operational complexity and lack of team experience. Kafka's exactly-once semantics, while attractive, come with significant infrastructure overhead. The setup time exceeds our two-week limit, and without in-house expertise, ongoing management would be challenging. Additionally, the cost of deploying Kafka at scale doesn't align with our current budgetary constraints. For a team of this size and focus, Redis Streams offers a more practical solution that delivers essential features with less risk.