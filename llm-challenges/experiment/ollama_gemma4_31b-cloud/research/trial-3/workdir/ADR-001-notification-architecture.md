# ADR 001: Notification Subsystem Architecture

## Status
Proposed

## Context
The current synchronous notification system is causing request timeouts (up to 8s), silent failures, and cascading failures due to slow external webhooks. We need to decouple notifications from the HTTP request cycle to support async processing, retries with exponential backoff, and delivery guarantees.

### Constraints
- **Traffic**: Peak 500 req/s, scaling target 10x (5,000 req/s).
- **Team**: 6 engineers (3 senior, 3 mid); no dedicated infra engineer.
- **Existing Stack**: Python/Flask, PostgreSQL, Redis (already in production).
- **Knowledge Gap**: Zero Kafka experience on the team.
- **Timeline**: Maximum 2 weeks for setup/migration to deliver initial value.
- **Budget**: Modest; cannot afford high-cost managed Kafka (e.g., Confluent Cloud).
- **Critical Requirement**: Exactly-once semantics for billing-critical notifications.

## Decision
We will use **Redis Streams** for the notification subsystem.

### Justification
Redis Streams provides the necessary primitives (consumer groups, message persistence, and acknowledgment) to solve our current failures while fitting our operational constraints.

1. **Operational Simplicity**: We already run Redis. Adding Streams requires no new infrastructure, no new binaries, and no new monitoring stacks. Kafka would require managing a Zookeeper/KRaft ensemble and a JVM-based runtime, which is a significant burden for a 6-person team without an infra engineer.
2. **Performance**: At 5,000 req/s (10x target), Redis Streams easily handles the throughput. Kafka is designed for millions of messages per second, which is overkill for our scale and introduces unnecessary complexity.
3. **Delivery Guarantees**: 
   - **At-least-once**: Achieved via Consumer Groups and explicit `XACK`. Messages not acknowledged are reclaimed via `XPENDING` and `XCLAIM`.
   - **Exactly-once (Billing)**: Since Redis and Kafka both primarily provide at-least-once delivery, exactly-once is achieved at the application level via **Idempotency**. We will use a `notification_id` (UUID) stored in PostgreSQL to ensure that billing events are not processed multiple times.
4. **Time-to-Value**: Integration with the existing Redis instance takes hours, not weeks. Kafka's learning curve and setup would likely exceed the 2-week constraint.

## Consequences
### Pros
- **Zero Infra Overhead**: Leverages existing production Redis.
- **Low Latency**: Sub-millisecond produce/consume latency.
- **Rapid Deployment**: Team can implement the pattern immediately using existing Python clients (`redis-py`).
- **Future-Proof**: Supports the planned WebSocket push notifications via the same Pub/Sub or Stream mechanism.

### Cons
- **Memory Bound**: Unlike Kafka's disk-centric storage, Redis is primarily in-memory. We must implement a strict retention policy (using `XADD` with `MAXLEN ~`) to prevent OOM.
- **Persistence Trade-off**: While Redis AOF provides durability, it is not as robust as Kafka's distributed commit log. However, for notifications, this is an acceptable risk given we can replay from the DB if critical.

## Alternatives Considered
### Apache Kafka
**Rejected**. While Kafka is the industry standard for high-throughput event streaming and offers superior long-term retention and exactly-once semantics (via transactional producers), it is unfit for this context:
- **Complexity**: The operational overhead of managing Kafka is too high for a small team without a dedicated SRE.
- **Cost**: Self-hosting is resource-intensive; managed options are beyond the current budget.
- **Overkill**: Our 10x growth target (5k req/s) is still well within the capabilities of a single Redis instance.
- **Learning Curve**: The team's lack of Kafka experience would jeopardize the 2-week delivery window.
