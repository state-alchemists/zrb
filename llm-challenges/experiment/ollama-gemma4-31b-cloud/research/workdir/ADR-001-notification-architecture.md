# ADR-001: Notification Subsystem Architecture

## Title
Selection of Message Broker for Notification Subsystem: Redis Streams vs. Apache Kafka

## Status
Proposed

## Context
The current synchronous notification system is causing request timeouts (up to 8s), silent failures, and cascading system crashes due to connection pool exhaustion. We need to decouple notifications from the HTTP request cycle to ensure reliability and scalability.

### Constraints & Requirements:
- **Scale**: Current peak 500 req/s; must handle 10x growth (~5,000 req/s).
- **Team**: 6 developers; no dedicated infra/DevOps engineer.
- **Experience**: Zero team experience with Kafka; already running Redis in production.
- **Timeline**: Value must be delivered within 2 weeks.
- **Budget**: Modest; cannot afford high-tier managed services (e.g., Confluent Cloud).
- **Guarantees**: At-least-once delivery for general notifications; exactly-once required for billing-critical events.
- **Future**: Must support WebSocket push notifications within 6 months.

## Decision
We will use **Redis Streams** as the message backbone for the notification subsystem.

### Justification:
1. **Operational Simplicity**: Since we already operate Redis for session and rate limiting, adopting Redis Streams adds zero new infrastructure components to manage. Introducing Kafka would require managing a new cluster (Zookeeper/KRaft), which is unrealistic for a 6-person team without a dedicated infra engineer.
2. **Time-to-Value**: Integration with Redis Streams can be implemented using existing client libraries within the 2-week window. Kafka's learning curve and setup overhead would exceed this limit.
3. **Performance**: Redis Streams easily handles the 10x growth target (5,000 req/s), as it operates in-memory with sequential append-only logs.
4. **Consumer Groups**: Redis Streams provides consumer group support (via `XGROUP`), allowing us to distribute notification processing across multiple workers and track offsets, satisfying the requirement for asynchronous decoupling and retry logic.
5. **Exactly-Once Semantics**: While neither system provides "true" end-to-end exactly-once delivery without application-level cooperation, Redis allows for easier implementation of idempotent consumers using the existing Redis cache to store processed message IDs—giving us effectively exactly-once semantics for billing events.

## Consequences
### Pros:
- **Zero Infrastructure Overhead**: Leverages existing production Redis instances.
- **Low Latency**: In-memory processing ensures minimal overhead between the producer (Flask) and consumer.
- **Rapid Deployment**: Immediate implementation using existing skills.
- **Path to WebSockets**: Redis Pub/Sub or Streams integrate natively with WebSocket layers for the planned real-time push feature.

### Cons:
- **Memory Constraints**: Unlike Kafka, which persists to disk, Redis Streams consume RAM. We will need to implement strict `XTRIM` policies (e.g., capping stream length) to prevent OOM (Out of Memory) errors.
- **Retention**: Longer-term message retention is more expensive in Redis than in Kafka. We will move "completed" or "archived" notifications to PostgreSQL if long-term audit trails are needed.

## Alternatives Considered
### Apache Kafka
**Rejected.** 
While Kafka offers superior throughput, disk-based persistence, and robust exactly-once semantics via transactions, it was rejected due to:
- **Extreme Operational Complexity**: Managing a production-grade Kafka cluster is a full-time job; our team lacks both the headcount and the expertise.
- **Cost**: Managed services that alleviate the operational burden are outside the current budget.
- **Over-Engineering**: Kafka's capabilities are designed for millions of events per second. At our 10x target (5,000 req/s), Kafka provides no functional advantage that outweighs its operational cost.
