# ADR-001: Notification Subsystem Architecture

## Title
Use Redis Streams for Notification Subsystem Asynchronous Processing

## Status
Proposed

## Context
Our SaaS project management platform currently processes notifications (emails, webhooks) synchronously during the HTTP request cycle. With 85,000 monthly active users and peak traffic of ~500 req/s, this synchronous approach is causing critical issues:
- **Request timeouts** (up to 8s latency during peak hours).
- **Silent failures** (dropped notifications on downstream downtime, no retries/DLQs).
- **Cascading failures** (slow webhooks exhausting DB connection pools).
- **Lack of delivery guarantees** for billing-critical events.

We need to decouple notifications into an asynchronous system that supports exponential backoff retries, at-least-once delivery, exactly-once semantics for billing, and future real-time WebSocket push notifications within two quarters. The system must also scale to handle 10x traffic (~5,000 req/s) without re-architecture.

Constraints:
- **Team**: 6 engineers (3 senior, 3 mid), no dedicated infrastructure engineer.
- **Current stack**: Python/Flask, PostgreSQL, Redis (used for session/rate limiting).
- **Experience/Budget**: No Kafka experience on the team, modest budget (cannot afford managed Kafka like Confluent Cloud).
- **Timeline**: Maximum 2 weeks of setup/migration work.

## Decision
We will use **Redis Streams** as the message broker to decouple the notification subsystem.

**Justification:**
- **Operational Complexity & Constraints**: The engineering team of 6 has no dedicated infrastructure engineer and zero Kafka experience, but already operates Redis in production. Standing up a self-hosted Kafka cluster or paying for a managed service violates our 2-week timeline and budget constraints. Redis Streams can be leveraged on our existing infrastructure immediately.
- **Throughput & Scalability**: Redis Streams can comfortably handle our target 10x peak load (~5,000 req/s), as Redis is an in-memory data store capable of hundreds of thousands of operations per second.
- **Consumer Groups & Retries**: Redis Streams natively supports Consumer Groups (via `XREADGROUP`), allowing us to distribute processing across multiple worker instances. Unacknowledged messages remain in the Pending Entries List (PEL), enabling robust retry logic with exponential backoff and dead-letter queue (DLQ) implementations via `XPENDING` and `XCLAIM`.
- **Ordering & Message Retention**: Messages are ordered chronologically by ID. Retention can be easily managed by configuring stream limits (e.g., `MAXLEN` or time-based trimming) to prevent memory exhaustion.
- **Exactly-Once Semantics**: While Redis Streams natively provides at-least-once delivery, we will satisfy the "exactly-once" requirement for billing notifications by pairing Redis Streams with the Transactional Outbox pattern on PostgreSQL and implementing idempotent consumers. Redis Streams' guaranteed delivery ensures we don't lose the message, and idempotency guarantees the exact-once processing semantics.

## Consequences

**Pros:**
- **Speed to Delivery**: Can be implemented within the 2-week constraint since no new infrastructure needs to be provisioned or learned.
- **Low Operational Overhead**: Reuses existing Redis infrastructure, avoiding the steep operational burden of managing a Kafka cluster.
- **Robust Consumer Features**: Natively supports consumer groups, pending entries (PEL), and acknowledgment mechanisms critical for reliable retries.
- **Future-Proofing**: Excellent fit for the upcoming WebSocket push notification requirement, as Redis Pub/Sub or Streams can efficiently fan out messages to WebSocket servers.

**Cons:**
- **Memory Bound**: Redis is in-memory. Message retention is constrained by available RAM, unlike Kafka which flushes to disk. We must enforce strict retention policies (e.g., trimming streams) to prevent out-of-memory incidents.
- **Lack of Native Dead-Letter Queues (DLQ)**: Redis does not have an automatic DLQ. We will need to write custom worker logic to move repeatedly failed messages from the PEL to a separate Redis Stream or Postgres table.
- **Idempotency Overhead**: Redis does not support atomic distributed transactions between the broker and the database like Kafka's exactly-once semantics. We must strictly enforce idempotent consumer design.

## Alternatives Considered

**Apache Kafka**
Kafka is the industry standard for high-throughput, durable event streaming and supports advanced features like native exactly-once processing (via Kafka Transactions) and disk-based, long-term message retention.

**Why it was rejected:**
- **Operational Complexity**: Self-hosting Kafka (with ZooKeeper or KRaft) requires significant infrastructure expertise that our team of 6 lacks. Managing partition rebalancing, JVM tuning, and disk scaling would become a massive distraction.
- **Budget**: Managed Kafka solutions (like Confluent Cloud or MSK) at production scale exceed our modest budget constraints.
- **Timeline Risk**: The learning curve and infrastructure setup would certainly breach the strict 2-week maximum timeline to deliver value.
- **Overkill**: Kafka's disk-backed retention and massive throughput capabilities (millions of msgs/s) are vastly disproportionate to our 10x target of ~5,000 req/s, which Redis Streams handles effortlessly in memory.