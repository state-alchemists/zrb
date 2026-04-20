# ADR-001: Notification Subsystem Architecture

## Status
Proposed

## Context
Our SaaS project management platform is currently processing notifications (emails and webhooks) synchronously within the HTTP request cycle. At our current scale (~500 req/s peak), this architecture is causing request timeouts, silent failures due to dropped notifications, and cascading failures resulting from connection pool exhaustion. 

We need to decouple the notification subsystem to process events asynchronously. The new architecture must:
- Support retries with exponential backoff and dead-letter queues.
- Guarantee at-least-once delivery, with exactly-once semantics for critical billing events.
- Lay the groundwork for real-time WebSocket push notifications.
- Handle a 10x traffic growth (up to ~5,000 req/s).

Our constraints dictate a pragmatic approach: we have a 6-person engineering team with no dedicated infrastructure engineer, no prior Apache Kafka experience, a modest budget, and a strict 2-week maximum setup/migration window. We already operate Redis in production for caching and rate limiting.

## Decision
We will use **Redis Streams** as the message broker for our asynchronous notification subsystem.

**Justification:**
Given our strict constraints around team size, lack of infrastructure expertise, and the 2-week timeline, introducing a heavy distributed system like Kafka is too risky and operationally expensive. Redis is already part of our production infrastructure, meaning there is zero new operational overhead or provisioning required to get started. 

Redis Streams natively supports the features we need to build a robust notification queue:
- **Consumer Groups:** Allows us to distribute notification processing across multiple background worker instances and scale horizontally.
- **Pending Entries List (PEL):** Tracks messages that have been delivered to a consumer but not yet acknowledged. This provides at-least-once delivery guarantees and makes it straightforward to implement retries and dead-letter queues for failed webhooks or emails.
- **Throughput:** Redis can comfortably handle our target of 5,000 req/s, as it processes operations in memory.

To satisfy the **exactly-once semantics** requirement for billing events, we will rely on Redis Streams' at-least-once delivery combined with **idempotent consumers**. We will store processed message IDs in our primary PostgreSQL database. By wrapping the notification dispatch and the message ID insertion in a database transaction (using unique constraints), we guarantee that a billing notification is never processed twice, even if Redis delivers it multiple times due to a worker crash.

## Consequences

**Pros:**
- **Speed to Market:** We can easily implement this within the 2-week deadline using our existing infrastructure and Python libraries (e.g., `redis-py`).
- **Low Operational Overhead:** No new infrastructure to deploy, monitor, or manage. We bypass the need for a dedicated infrastructure engineer.
- **Cost Effective:** Avoids the high licensing or managed-service costs of Kafka (e.g., Confluent Cloud).
- **Built-in Reliability:** Consumer groups and PEL provide the necessary primitives for message acknowledgment and robust error handling.

**Cons:**
- **In-Memory Retention Limits:** Unlike Kafka, which persists to disk and can store weeks of data, Redis Streams stores data in RAM. We must actively prune acknowledged messages (`XDEL` or `XTRIM`) to prevent out-of-memory crashes.
- **No Native Exactly-Once:** Redis Streams does not have transactional outbox/exactly-once processing built-in end-to-end; we bear the burden of implementing idempotency at the application layer.
- **Smaller Ecosystem:** Lacks Kafka's massive ecosystem of sink/source connectors, though we don't need them for our current use case.

## Alternatives Considered

**Apache Kafka**
- **Why it was rejected:** While Kafka is the industry standard for event streaming and natively handles exactly-once semantics, disk-based retention, and massive scale, it violates almost all of our constraints. Operating a highly available Kafka cluster requires specialized knowledge that our team lacks, and managed solutions exceed our modest budget. Furthermore, setting up Kafka, configuring Zookeeper/KRaft, and training the team on Kafka concepts (partitions, offsets, rebalancing) would drastically exceed our 2-week timeline. For our target of 5,000 req/s, Kafka's complexity is unnecessary overhead.