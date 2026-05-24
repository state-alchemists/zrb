# ADR-001: Selecting Redis Streams over Apache Kafka for the Async Notification Subsystem

- **Status**: Proposed
- **Date**: 2026-05-24
- **Deciders**: Go Frendi (Principal Software Engineer), Engineering Team
- **Context tags**: architecture, async-processing, message-broker, notifications, scalability

## Context

The current synchronous notification module within our Python/Flask monolith dispatches email and webhook alerts during the HTTP request lifecycle. This synchronous pattern blocks response threads and introduces severe architectural issues:
1. **Request Timeouts**: Sending notifications over external networks blocks client responses. This adds an average of 800ms of latency per request, which spikes to over 8s during peak traffic hours.
2. **Silent Failures**: If third-party email providers or webhook endpoints are offline, notifications are lost. The monolith has no built-in retry mechanisms, persistence, or Dead-Letter Queues (DLQs).
3. **Cascading Failures**: Unresponsive or slow third-party webhook endpoints have exhausted the monolith's connection pool twice this year, taking down unrelated user-facing features.
4. **No Delivery Guarantees**: Billing-critical notifications (e.g., "trial expired", "payment failed") must have deterministic delivery, which the current setup cannot provide.

To mitigate these issues, we must transition to an asynchronous notification subsystem. We need to evaluate a message broker to decouple notification generation from HTTP request threads. 

### Scale Requirements
- **Current Load**: 85,000 Monthly Active Users (MAU), ~2M tasks created/updated per month, and peak throughput of ~500 requests/second.
- **Scaling Target**: Handle a 10x traffic increase (~5,000 peak requests/second, ~20M tasks/month) without needing a re-architecture.
- **Timeline**: Deliver value within a strict 2-week setup and migration deadline.
- **Future Growth**: Introduce real-time WebSocket push notifications within 2 quarters.

### Operational Constraints
- **Team Size**: 6 engineers (3 senior, 3 mid-level) with zero dedicated DevOps or infrastructure engineers.
- **Technology Stack**: No in-house Apache Kafka experience. The team currently runs Redis in production for session storage and rate limiting.
- **Financial Budget**: Modest budget. We cannot afford the high baseline costs of managed Kafka solutions (e.g., Confluent Cloud, AWS MSK) at our target scale today.
- **Delivery Guarantee**: At-least-once delivery for general notifications, and exactly-once processing (EOS) for billing-critical events.

---

## Decision

We will use **Redis Streams** as the message broker for the asynchronous notification subsystem, rejecting Apache Kafka.

We will write notification events directly to Redis Streams from our Flask monolith and consume them asynchronously using dedicated Python background worker processes. This decision leverages our existing production infrastructure, aligns with our team's skills, fits within our 2-week delivery timeframe, and easily satisfies our current and 10x peak throughput demands.

---

## Rationale

Redis Streams is the optimal choice for our specific scale, team size, and operational constraints based on the following technical properties:

### 1. Throughput & Performance
Our current peak is 500 req/s. At our 10x scaling target, peak load will reach 5,000 req/s. Assuming each request generates up to two notification events, our broker must support a peak ingest rate of 10,000 events/s.
- **Redis Streams**: Operates in-memory and can achieve over 100,000 write/read operations per second on modest, single-node hardware. It will easily handle our 10x peak load of 10,000 events/s using only a fraction of its capacity.
- **Apache Kafka**: Capable of millions of writes/sec, which is far beyond our current or 10x peak requirements. Choosing Kafka for our 10k events/s peak would be a severe case of over-engineering.

### 2. Operational Complexity & Team Constraints
- **Redis Streams**: We already run Redis in production for sessions and rate-limiting. Reusing this instance or spinning up a dedicated Redis node requires zero new infrastructure primitives, zero new monitoring dashboards, and zero JVM tuning. Our 6-person team is already familiar with Redis, enabling us to deliver the complete migration well within the 2-week deadline.
- **Apache Kafka**: Running Kafka requires configuring a cluster of JVM-based brokers and a consensus mechanism (ZooKeeper or KRaft). With no dedicated infrastructure engineer, managing high availability, partition counts, log segments, and JVM garbage collection is an unacceptable operational risk.

### 3. Consumer Groups & Scale-Out
Redis Streams provides native, robust consumer group support via the `XGROUP`, `XREADGROUP`, `XACK`, and `XCLAIM` APIs. 
- We can scale our background notification consumers horizontally by running multiple instances of lightweight Python worker processes in a single consumer group.
- Redis handles load distribution automatically, ensuring each notification event is dispatched to only one active consumer worker in the group.

### 4. Ordering Guarantees
- **Redis Streams**: Provides strict chronological ordering. Every stream entry is assigned a unique, monotonically increasing ID (`<timestamp>-<sequence>`). Messages are read by consumers in the exact order they were appended, preventing race conditions (e.g., ensuring a "task created" event is processed before a "task updated" event).
- **Apache Kafka**: Guarantees ordering only within a single partition. To maintain task-level ordering across a partitioned Kafka topic, we would have to define partition keys (e.g., hash of `task_id`). Redis Streams gives us stream-wide ordering naturally without partition routing management.

### 5. Message Retention & Memory Management
Because Redis is an in-memory datastore, we must manage RAM usage proactively to avoid Out-Of-Memory (OOM) failures:
- We will enforce capped streams using the `MAXLEN` option during event insertion (e.g., `XADD notification_stream MAXLEN ~ 50000 * ...`). This maintains a sliding window of the most recent 50,000 messages, purging older, acknowledged notifications from memory.
- Since notifications are transient, long-term persistence in the broker is not required. Postgres remains our durable system of record for audit logs and historical task data.

### 6. Exactly-Once Semantics (EOS)
Neither Redis Streams nor Apache Kafka can provide true end-to-end exactly-once delivery for notifications because external actions (sending emails via SMTP, calling webhook HTTP endpoints) are not transactional and cannot be rolled back.
- **At-Least-Once Delivery**: Achieved via Redis Streams consumer group acknowledgment. Workers pull messages using `XREADGROUP`. If a worker crashes before calling `XACK`, the message remains in the Pending Entries List (PEL). A supervisor process queries the PEL using `XPENDING` and claims stalled messages using `XCLAIM` to retry.
- **Consumer Idempotency**: To achieve exactly-once processing (EOS) for billing notifications, we will implement deduplication in the consumer. Every notification is generated with a unique transaction ID. Before a worker dispatches a billing notification, it will attempt to write an idempotency key to Postgres or Redis using a transactional unique constraint. If the write succeeds, the notification is sent; if it fails (duplicate key), the message is safely discarded as a duplicate.

### 7. WebSocket Push Integration
Our 2-quarter target for real-time WebSockets aligns naturally with Redis. We can easily bridge Redis Streams to real-time client pushes using Redis Pub/Sub or by having our WebSocket servers (e.g., gevent or FastAPI ASGI servers) poll the streams directly.

---

## Consequences

### Positive (Pros)
- **Zero Infrastructure overhead**: Reuses our existing Redis production setup, preventing infrastructure sprawl.
- **Rapid Delivery**: The 6-person engineering team can implement, test, and deploy the entire async architecture in under 2 weeks.
- **Immediate Latency Recovery**: Offloading SMTP and webhooks to background workers will instantly lower monolith request latency from up to 8s down to sub-50ms.
- **No Financial Cost**: Eliminates the high baseline licensing/hosting fees associated with managed Kafka offerings.
- **Resilient Webhook Isolation**: Background workers run in isolation, preventing slow webhooks from exhausting Flask's HTTP connection pools.

### Negative (Cons)
- **RAM Limits**: Redis is strictly bounded by available memory. An unmanaged backlog of unacknowledged notifications could lead to OOM conditions. We must proactively enforce capped streams (`MAXLEN`) and configure Prometheus alerts on the queue depth.
- **Manual DLQ Management**: Redis Streams do not have a built-in Dead-Letter Queue (DLQ). We must write custom Python code to query the `XPENDING` list and route poisoned messages (messages that have failed delivery more than 5 times) to a dedicated `notification_dlq` stream or Postgres table.
- **Durable Persistence Risk**: Unlike Kafka's disk-backed log, Redis is transient by default. If the Redis server crashes, data in RAM could be lost. We must enable Append-Only File (AOF) persistence with `appendfsync everysec` to ensure disk durability with minimal performance impact.

### Follow-Ups
1. **Deduplication DB Schema**: Design and index the idempotency table in Postgres for billing notifications.
2. **Persistence Audit**: Verify that production Redis instances have `appendfsync everysec` enabled and that backup RDB snapshots are configured.
3. **DLQ Implementation**: Write the custom PEL/XCLAIM supervisor task to monitor unacknowledged messages and forward exhausted notifications to the DLQ.
4. **Alerting**: Configure Datadog/Prometheus alerts to trigger if Redis memory utilization exceeds 80% or if queue depth exceeds 20,000 items.

---

## Alternatives Considered

### Apache Kafka
- **Why Rejected**: Apache Kafka is an excellent log-structured event streaming platform, but it is vastly over-engineered for our scale and constraints. 
- **Operational Drag**: Setting up and running Kafka (or KRaft/ZooKeeper) has an extremely high operational complexity ceiling. Since our team of 6 has zero Kafka experience and no dedicated infrastructure engineer, self-hosting is an unacceptable operational risk.
- **Budget Mismatch**: Managed Kafka services like AWS MSK or Confluent Cloud are too expensive for our modest budget.
- **Missed Deadline**: Learning Kafka, writing clients, configuring serialization, and deploying the cluster would take at least 4-6 weeks, failing our 2-week time-to-value constraint.
- **Overkill**: While Kafka provides stronger out-of-the-box durability (disk-backed log) and built-in EOS for internal transactions, these properties do not justify the immense operational and financial costs given our current and 10x scale (500 to 5,000 req/s), which Redis Streams can easily handle. We would have chosen Kafka if our peak throughput exceeded 100,000 req/s, or if we had a dedicated DevOps team and a large budget.
