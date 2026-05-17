# ADR-001: Notification Subsystem Architecture

## Status
Proposed

## Context
The current synchronous notification system is causing request timeouts, silent failures, and cascading system instability due to slow external webhooks. We need to decouple notifications from the request cycle to support retries, ensure at-least-once delivery for billing events, and scale to 10x current traffic (peak ~5k req/s).

Constraints:
- Team: 6 engineers, no dedicated DevOps/Infrastructure specialist.
- Current Stack: Python/Flask, PostgreSQL, Redis.
- Timeline: Setup/migration must be completed within 2 weeks.
- Experience: No prior Kafka experience on the team.
- Budget: Low; managed Kafka (Confluent) is cost-prohibitive.
- Requirement: Exactly-once semantics for billing notifications.

## Decision
We will use **Redis Streams** for the notification subsystem.

### Justification
Redis Streams provides the necessary primitives for a reliable asynchronous messaging system (consumer groups, message acknowledgement, and persistence) while leveraging our existing production infrastructure.

1. **Operational Simplicity**: We already run Redis. Adding Streams requires zero new infrastructure, whereas Kafka requires deploying and managing a new cluster (ZooKeeper/KRaft, JVM tuning, etc.), which is unrealistic for a 6-person team without a DevOps engineer.
2. **Performance & Throughput**: At a 10x growth target (5k req/s), Redis Streams easily handles the load with sub-millisecond latency. Kafka's throughput is superior but overkill for this scale.
3. **Delivery Guarantees**: Redis Streams supports Consumer Groups with `XACK`, allowing for at-least-once delivery. For "exactly-once" billing notifications, we will implement the **Idempotent Consumer pattern** at the application level (using a `processed_notifications` table in PostgreSQL), as neither Redis nor Kafka provides true end-to-end exactly-once semantics without significant complexity.
4. **Implementation Speed**: The team can integrate Redis Streams via existing Python libraries (`redis-py`) within the 2-week window. Kafka would require a steep learning curve and significant configuration time.
5. **Future Proofing**: Redis Streams supports the real-time requirements of the planned WebSocket push notifications more naturally than Kafka's polling model.

## Consequences
### Pros
- **Low Overhead**: No new servers to manage or monitor.
- **Rapid Deployment**: Immediate value delivery due to existing Redis expertise.
- **Sufficient Scale**: Capable of handling the anticipated 10x growth.
- **Reliability**: Moves notifications out of the request cycle, preventing cascading failures.

### Cons
- **Memory Bound**: Redis stores streams in RAM (though they can be trimmed). We must implement a strict `MAXLEN` policy to prevent OOM.
- **Persistence Trade-off**: While Redis offers AOF/RDB, it is not as durable as Kafka's disk-centric commit log. However, for notifications, this is an acceptable risk.

## Alternatives Considered
### Apache Kafka
Kafka was rejected for the following reasons:
- **Operational Complexity**: The "management tax" is too high for a small team. Setting up a production-grade, HA Kafka cluster is a multi-week project.
- **Resource Heavy**: Kafka requires significant RAM and disk I/O tuning, contrasting with our modest budget and infrastructure.
- **Over-engineering**: Kafka is designed for multi-gigabyte-per-second throughput and long-term event sourcing. Our requirement is a reliable task queue for notifications, which is a perfect fit for Redis Streams.
