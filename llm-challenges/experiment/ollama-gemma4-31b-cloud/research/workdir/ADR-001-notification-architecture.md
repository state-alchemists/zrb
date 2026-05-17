# ADR-001: Notification Subsystem Architecture

## Title
Selection of Messaging Backend for Notification Subsystem

## Status
Proposed

## Context
The current synchronous notification system is causing request timeouts, silent failures, and cascading system instability. We need to decouple notification delivery from the HTTP request cycle to support retries and delivery guarantees.

**Key Constraints:**
- **Team:** 6 engineers (no dedicated infra/DevOps).
- **Existing Stack:** Python/Flask, PostgreSQL, Redis.
- **Requirements:** 
    - At-least-once delivery for billing events.
    - Exactly-once semantics for critical billing notifications.
    - Support for future WebSocket integration.
    - Ability to handle 10x growth (up to 5,000 req/s peak).
    - Maximum 2-week setup/migration window.
    - Modest budget (cannot afford high-end managed Kafka).

## Decision
We will use **Redis Streams** as the messaging backbone for the notification subsystem.

**Justification:**
Given the team size and existing infrastructure, Redis Streams provides the optimal balance of performance and operational simplicity. 

1. **Operational Overhead**: The team already manages Redis for session and rate limiting. Adding Streams requires zero new infrastructure components, whereas Kafka would introduce a significant operational burden (Zookeeper/KRaft, JVM tuning, partition management) for a team with no prior Kafka experience.
2. **Performance**: Redis Streams easily handles the target 5,000 req/s peak throughput with sub-millisecond latency, fitting our 10x growth target.
3. **Consumer Groups**: Redis Streams supports consumer groups, allowing us to scale the number of notification workers and ensure that each message is processed by only one worker in a group.
4. **Time-to-Value**: Integration can be completed within days using existing Redis clients, meeting the <2-week constraint.
5. **Delivery Guarantees**: By utilizing the `XACK` (acknowledgment) mechanism and maintaining a pending entries list (PEL), we can ensure at-least-once delivery. For exactly-once requirements (billing), we will implement an idempotent consumer pattern using the existing PostgreSQL database to track processed notification IDs.

## Consequences
### Pros
- **Near-Zero Lead Time**: No new software to install or configure.
- **Low Cognitive Load**: The team avoids the steep learning curve of Kafka's complex ecosystem.
- **Resource Efficiency**: Avoids the memory and CPU overhead of a dedicated Kafka cluster for a relatively low-volume workload (~2M tasks/month).
- **Built-in Integration**: Seamlessly aligns with our future WebSocket push needs, as Redis is already an industry standard for pub/sub and real-time state.

### Cons
- **Persistence Limits**: Unlike Kafka, Redis is primarily in-memory. While RDB/AOF provides persistence, it is less robust than Kafka's disk-first commit log. We must monitor memory usage closely as volume grows.
- **Lack of Native Exactly-Once**: Redis does not provide the transactional producer/consumer API that Kafka does. We must handle idempotency at the application layer.
- **Retention Management**: We must manually implement a strategy (e.g., `XTRIM`) to prune old streams and prevent memory exhaustion.

## Alternatives Considered
**Apache Kafka**
Rejected for the following reasons:
- **Operational Complexity**: Managing a Kafka cluster is a full-time job; our team of 6 generalists cannot afford the overhead.
- **Cost**: Managed Kafka (Confluent) exceeds the current budget.
- **Overkill**: The scale (500-5,000 req/s) is well within Redis's capabilities. Kafka's superior throughput and long-term retention are not required for this specific use case.
- **Implementation Lag**: The learning curve and setup would likely push the delivery beyond the 2-week constraint.
