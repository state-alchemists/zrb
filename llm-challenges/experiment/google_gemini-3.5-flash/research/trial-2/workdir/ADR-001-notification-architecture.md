# ADR-001: Redis Streams over Apache Kafka for the Notification Subsystem

## Status
Accepted

## Context
Our SaaS project management platform has grown to 85,000 monthly active users, processing ~2M tasks per month with business-hour peaks of ~500 requests/second. Currently, the notification module (responsible for sending emails and webhooks when tasks are updated, assigned, or completed) operates synchronously within the Python/Flask HTTP request cycle. This synchronous coupling has introduced major system-wide issues:
1. **Request timeouts**: Blocks response cycles, driving average latencies to 800ms and peak latency spikes to 8s.
2. **Silent failures**: Lack of retry mechanisms or Dead-Letter Queues (DLQs) results in permanently dropped notifications when external webhook or email providers fail.
3. **Cascading failures**: Double incidents of connection pool exhaustion caused by slow downstream webhook endpoints, taking down unrelated parts of the platform.
4. **No delivery guarantees**: Critical billing-related notifications (e.g., "trial expired", "payment failed") have no delivery guarantees, but must be delivered exactly once where feasible or at least once with strict application-level deduplication.

### Scaling Target
- Decouple notification dispatch from the HTTP request cycle (fully asynchronous execution).
- Support exponential backoff retry policies and Dead-Letter Queue (DLQ) routing.
- Guarantee at-least-once delivery for billing notifications, and exactly-once semantics (EOS) at the application boundary.
- Integrate real-time WebSocket push notifications within 2 quarters.
- Scale to handle 10x traffic growth (~5,000 requests/second peak) without requiring a future architectural overhaul.

### Constraints
- **Team Size**: 6 engineers (3 senior, 3 mid-level) with no dedicated infrastructure/DevOps engineer.
- **Expertise**: Zero internal experience with Apache Kafka.
- **Existing Stack**: Redis is already running in production for session storage and rate limiting.
- **Timeline**: Maximum of 2 weeks of setup/migration work before delivering measurable value.
- **Budget**: Modest. Enterprise managed services (e.g., Confluent Cloud) are cost-prohibitive at our scaling target.

---

## Decision
We choose **Redis Streams** as our primary message broker for the notification subsystem.

### Justification
Redis Streams provides the ideal balance of throughput, low operational complexity, and rich streaming features. It fully solves our scaling, reliability, and delivery requirements while remaining within our team's operational and time constraints.

1. **Zero New Operational Footprint**: Since Redis is already deployed and maintained in our production stack, adopting Redis Streams introduces no new systems to configure, monitor, scale, or secure.
2. **Guaranteed Delivery at 10x Scale**: 
   - **Throughput**: A single-node Redis instance on modest AWS EC2 hardware easily handles over 50,000 message writes/second. At our 10x peak scaling target (5,000 req/s), Redis Streams will operate under 10% utilization.
   - **Ordering & Partitioning**: Per-task and per-user ordering are naturally achieved within streams.
3. **Timeline Feasibility**: Deploying a client-side Redis Streams consumer group takes days, fitting comfortably within our 2-week deadline. Re-architecting for Kafka, configuring partition distribution, and training the team on offset commit patterns would require weeks of setup, missing the delivery window.
4. **Application-Level Exactly-Once Semantics (EOS)**: Neither Redis Streams nor Apache Kafka can guarantee exactly-once delivery across external network boundaries (e.g., triggering a third-party email API or webhook). Both brokers require application-level deduplication. We will enforce exactly-once semantics by attaching a unique event ID (e.g., `event_uuid`) to every notification message and performing a deduplication check on the consumer side via a PostgreSQL `INSERT INTO processed_notifications (event_uuid) VALUES (...) ON CONFLICT DO NOTHING` statement.
5. **Native WebSocket Push Alignment**: Redis is exceptionally suited for real-time pub/sub and stream-reading patterns, aligning perfectly with our two-quarter roadmap for WebSocket push notifications.

---

## Consequences

### Pros (Benefits)
- **Extremely Fast Time-to-Value**: No infrastructure provisioning is needed; the team can immediately begin writing Python consumer-group code.
- **Rich Consumer Group Semantics**: Redis Streams supports consumer groups natively via `XGROUP`, tracking unacknowledged messages via Pending Entries Lists (PEL) using `XPENDING`.
- **Reliable Retries & DLQ**: Consumers can safely inspect the PEL, reclaim stale or crashed deliveries via `XCLAIM`, and automatically route failing "poison pill" messages to a secondary dead-letter stream after a threshold of retries is exceeded.
- **Minimal Budget Impact**: Leverages existing investments. A dedicated Redis node for streams costs around $50–$100/month, compared to much higher managed streaming overheads.
- **Low Latency**: Sub-millisecond in-memory operations prevent any downstream bottlenecking.

### Cons (Risks and Mitigations)
- **Memory-Bound Retention**: Unlike disk-backed brokers, Redis Streams keep messages in RAM, posing an out-of-memory (OOM) risk if consumers fall behind.
  - *Mitigation*: We will write to streams using the `MAXLEN ~ <threshold>` flag (e.g., keeping only the last 100,000 events per stream) and archive all processed notifications to PostgreSQL for historical audits.
- **Durability Risks on Crash**: Standard Redis asynchronous replication or snapshotting (RDB) can lose a sub-second window of data in a severe cluster failover.
  - *Mitigation*: We will configure Append-Only File (AOF) persistence with `appendfsync everysec` on our Redis instance, which limits potential data loss to under 1 second of non-billing transient events, while billing transactions are protected by transactional PostgreSQL state.
- **No Native Message Replay (Long-Term)**: Redis is not a long-term data lake and cannot store weeks of stream history.
  - *Mitigation*: This is acceptable. Notifications are transient tasks that are processed and completed. PostgreSQL serves as the permanent system of record.

---

## Alternatives Considered

### Apache Kafka
We rejected Apache Kafka for the following reasons:

1. **High Operational Complexity**: Running a production-ready, self-hosted Kafka cluster requires managing multiple brokers, KRaft or ZooKeeper quorums, JVM memory tuning, consumer rebalances, and partition assignments. For a 6-person team with no infrastructure engineer, this introduces a high-risk point of failure.
2. **Prohibitive Infrastructure Costs**:
   - Self-hosted 3-broker cluster requires persistent disk storage and multi-instance overheads (~$500/month minimum).
   - AWS Managed Streaming for Kafka (MSK) starts at ~$1,100/month.
   - Confluent Cloud would quickly exceed our modest budget at our 10x scaling target.
3. **Severe Timeline Violations**: Provisioning, benchmarking, configuring security (SASL/TLS), and designing reliable Kafka consumer loops cannot be achieved within our strict 2-week window.
4. **Redundant Broker-Level Exactly-Once Semantics (EOS)**: Kafka's transactional EOS applies strictly inside the Kafka ecosystem (broker-to-broker). Because our notification system must call external APIs (SendGrid, Twilio, third-party webhooks), we still require application-level consumer idempotency. This makes Kafka's primary delivery-guarantee advantage redundant for our specific use case.
