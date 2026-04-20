# ADR-001: Notification Subsystem Architecture

## Status
Proposed

## Context
Our current notification system is synchronous, causing request timeouts, silent failures, and cascading failures. We need to transition to an asynchronous, message-driven architecture that supports:
- High throughput (current peak 500 req/s, target 5,000 req/s).
- Reliable delivery (at-least-once for general tasks, exactly-once for billing).
- Consumer groups for horizontal scaling.
- Low operational overhead for a 6-person team with no dedicated DevOps/Infra engineer.
- Implementation within a 2-week window.

We currently utilize Redis for sessions and rate-limiting. The team has no experience with Apache Kafka.

## Decision
We will use **Redis Streams** as the backbone for the notification subsystem.

**Justification:**
1. **Operational Simplicity:** We already run Redis in production. Adding Streams leverages existing infrastructure, monitoring, and team knowledge. Kafka would require a new stack (Zookeeper/KRaft, JVM tuning, complex partition management) which the team cannot absorb in 2 weeks.
2. **Performance:** Redis Streams easily handles 5,000 req/s on a single node. Given our 10x scaling target, Redis provides more than enough headroom without the complexity of a distributed log like Kafka.
3. **Feature Parity:** Redis Streams supports Consumer Groups, strict **ordering guarantees**, and message acknowledgment (ACKs), providing the necessary primitives for at-least-once delivery and retries via the Pending Entry List (PEL).
4. **Exactly-Once Semantics (EOS):** While Kafka has native transactional producers, we can achieve EOS in Redis for billing-critical events by using deterministic Message IDs (e.g., `event_uuid`) combined with consumer-side idempotency in our Python workers.
5. **Message Retention:** We can manage memory usage through stream capping (`XADD` with `MAXLEN`), ensuring high performance without the disk-management overhead of Kafka.
6. **Cost:** Redis is significantly cheaper to run at our scale compared to a managed Kafka cluster (e.g., Confluent Cloud or AWS MSK).

## Consequences
### Pros
- **Immediate Productivity:** The team can start development immediately using familiar libraries (`redis-py`).
- **Low Latency:** Redis’s in-memory nature ensures extremely low sub-millisecond tail latency for message ingestion.
- **Unified Stack:** Simplifies the architectural footprint and reduces the "moving parts" in our small-scale environment.

### Cons
- **Memory Constraints:** Unlike Kafka, which stores messages on disk, Redis is memory-bound. We must implement strict stream capping (`MAXLEN`) and archive older events to PostgreSQL if long-term replayability is needed.
- **Durability Trade-off:** While Redis supports AOF (Append Only File), it is generally considered less durable than Kafka’s multi-node replication/disk-flush guarantees in catastrophic failure scenarios. We will mitigate this via synchronous AOF and standard RDS-backed state for critical billing events.

## Alternatives Considered
### Apache Kafka
**Rejected** due to high operational complexity and the steep learning curve for a 6-person team. While Kafka provides superior durability and native EOS, the "infrastructure tax" would prevent us from meeting the 2-week delivery goal. At our current and projected scale (5k req/s), Kafka’s massive scalability is not yet a requirement that justifies its overhead.

### PostgreSQL (Transactional Outbox)
**Rejected** as a primary queue. While great for consistency, using Postgres as a high-throughput queue at 5,000 req/s would create significant vacuuming overhead and potential lock contention on the primary database, which we are already trying to protect.
