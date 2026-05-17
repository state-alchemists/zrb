# ADR-001: Notification Subsystem Architecture

## Status
Proposed

## Context
Our project management platform (85,000 MAU, ~2M tasks/month) currently handles notifications (emails, webhooks) synchronously within the Flask HTTP request cycle. At peak traffic (~500 req/s), this causes severe latency spikes (up to 8s), request timeouts, and cascading system failures due to connection pool exhaustion when external APIs are slow. Furthermore, transient errors result in dropped notifications since there is no retry mechanism.

We need to decouple notifications into an asynchronous pipeline that guarantees at-least-once delivery (and exactly-once semantics for billing events), supports retries with exponential backoff, and can handle a 10x traffic growth (to ~5,000 req/s). Within two quarters, we must also support real-time WebSocket push notifications.

We are operating under strict constraints:
- 6-person engineering team with no dedicated infrastructure engineer.
- Modest budget (cannot afford premium managed event streaming like Confluent Cloud).
- Maximum of 2 weeks to set up and migrate.
- Redis is already deployed in production.
- Zero existing team experience with Apache Kafka.

## Decision
We will use **Redis Streams** as the message broker for the notification subsystem.

**Justification:**
Given the strict operational and timeline constraints, introducing a highly complex, infrastructure-heavy distributed log like Apache Kafka is not viable. Redis Streams provides the necessary features—append-only logs, consumer groups for horizontal scaling, and at-least-once delivery guarantees—while leveraging infrastructure we already operate and understand. 

A target throughput of 5,000 req/s (our 10x growth goal) is trivial for Redis Streams. Consumer groups allow us to seamlessly scale Python worker processes. To satisfy the "exactly-once semantics for billing" requirement, we will pair Redis Streams' at-least-once delivery with **idempotent consumers**. (Note: even with Kafka, exact-once delivery to external systems like email providers or third-party webhooks requires idempotent design, as broker-level exactly-once semantics only apply to internal read-process-write loops). We will achieve this by recording processed notification IDs in a dedicated PostgreSQL table within the same transaction that executes the business logic.

## Consequences

**Pros:**
*   **Speed of Delivery:** Meets the < 2 weeks constraint. Developers can start writing Python publisher/consumer code immediately without waiting for infrastructure provisioning.
*   **Zero New Infrastructure:** No new services to monitor, patch, or pay for. Eliminates the operational tax of managing clusters, partitions, and JVMs.
*   **Consumer Groups:** Built-in support for Redis Consumer Groups (`XREADGROUP`) allows multiple worker instances to safely process messages concurrently without duplicating work.
*   **WebSocket Readiness:** Redis Pub/Sub or Streams natively fits the upcoming requirement to push real-time events to stateful WebSocket servers.
*   **Built-in Dead Lettering:** Features like `XPENDING` and `XCLAIM` allow us to easily detect stalled/failed messages and implement retry queues with exponential backoff.

**Cons:**
*   **In-Memory Restraint:** Unlike Kafka, which writes to disk, Redis Streams resides in memory. We must carefully configure stream trimming (`XADD ... MAXLEN`) to prevent out-of-memory crashes if consumers go offline for extended periods.
*   **Implementation Burden for Exactly-Once:** Because Redis guarantees at-least-once delivery, the engineering team must strictly enforce idempotency in the application layer for critical billing events to prevent duplicate emails/webhooks on retry.
*   **Durability Risks:** Depending on our current Redis persistence configuration (AOF vs RDB), an abrupt Redis node failure might result in sub-second data loss of un-synced events, requiring a review of our `appendfsync` settings.

## Alternatives Considered

**Apache Kafka:**
Rejected. While Kafka is the industry standard for high-throughput event streaming and provides superior disk-based persistence and strict ordering, it violates multiple hard constraints. 
1. **Operational Complexity:** Operating ZooKeeper/KRaft, managing topic partitions, tuning JVM garbage collection, and handling broker failures require dedicated infrastructure expertise that our 6-person team lacks.
2. **Setup Time:** Learning Kafka concepts, deploying the cluster, and writing resilient Kafka clients in Python would heavily exceed the 2-week deadline.
3. **Cost:** Offloading the operational burden to a managed service like Confluent Cloud violates our modest budget constraints at our target scale. 
Kafka is an over-engineered solution for a peak target of 5,000 req/s.