# ADR 001 — Notification Subsystem Architecture: Redis Streams over Apache Kafka

- **Status**: Proposed
- **Date**: 2026-05-24
- **Deciders**: SaaS Project Management Platform Engineering Team
- **Context tags**: notifications, message-broker, scalability, reliability, redis, kafka

## Context

Our SaaS project management platform is experiencing significant performance and reliability challenges due to synchronous notification processing inside the HTTP request cycle. 

### Current System Metrics & Infrastructure
- **Metrics**: 85,000 monthly active users (MAU), ~2M tasks created per month, and peak traffic of ~500 requests/second.
- **Backend Stack**: Python/Flask monolith (~50k lines of code) with PostgreSQL (single primary, one read replica).
- **Existing Cache**: Redis is already deployed and managed in production for session storage and rate limiting.
- **Web Servers**: 4 web servers behind an AWS nginx load balancer.

### Identified Problems
1. **Request Timeouts**: Sending notifications blocks HTTP responses. Latency averages 800ms and spikes to 8s during peak hours, degrading user experience.
2. **Silent Failures**: Downstream failures (e.g., third-party email providers or slow webhook endpoints) lead to silently dropped notifications with no retry mechanism or dead-letter queue (DLQ).
3. **Cascading Failures**: Unresponsive webhook endpoints have caused database connection pool exhaustion twice this year, resulting in platform-wide outages.
4. **No Delivery Guarantees**: Critical billing-related notifications (e.g., "trial expired", "payment failed") are treated identically to non-critical notifications and lack delivery or processing guarantees.

### Scaling Target
- Decouple all notifications from the HTTP request cycle via asynchronous background worker processing.
- Build a robust retry mechanism with exponential backoff.
- Guarantee at-least-once delivery for billing events, achieving exactly-once processing semantics where feasible.
- Introduce real-time WebSocket push notifications within 2 quarters.
- Support a 10x traffic growth target (850k MAU, ~20M tasks/month, ~5,000 requests/second at peak) without requiring an architectural rewrite.

### Engineering & Budget Constraints
- **Team Size**: 6 engineers (3 senior, 3 mid-level) with no dedicated infrastructure or DevOps engineer.
- **Timeline**: No more than 2 weeks of setup and migration work before the new architecture must deliver production value.
- **Skill Set**: The team possesses strong Redis operational knowledge but has zero experience operating or developing with Apache Kafka.
- **Budget**: Modest. Fully managed options like Confluent Cloud are cost-prohibitive at our scale.

---

## Decision

We will use **Redis Streams** as the core message broker for the notification subsystem, implemented as an asynchronous task queue with at-least-once delivery guarantees and consumer-side idempotent deduplication.

### Justification

Redis Streams is the only option that satisfies all our technical requirements, guarantees, and timeline constraints without introducing existential operational risks.

1. **Leveraging Existing Infrastructure and Expertise**:
   Redis is already running, monitored, and managed in our production environment. Adopting Redis Streams introduces zero new infrastructure dependencies, allowing us to deliver production value well within the strict 2-week deadline.
2. **Operational Fit**:
   With a 6-person engineering team and no dedicated infrastructure engineer, self-hosting Apache Kafka would divert critical engineering capacity to cluster maintenance, ZooKeeper/KRaft administration, partition planning, JVM tuning, and OS-level storage optimization. Redis Streams requires near-zero additional operational overhead.
3. **Throughput Capability**:
   A modest, single-node Redis instance can process tens of thousands of write/read operations per second in memory. At our 10x peak scaling target of 5,000 requests/second, Redis Streams will easily handle the ingestion and dispatch of generated notification events (estimated at 10,000 to 15,000 messages/second) with sub-millisecond latency.
4. **Guaranteed Delivery and Exactly-Once Processing Semantics**:
   Redis Streams provides built-in Consumer Groups that track pending, unacknowledged messages via the Pending Entries List (PEL). We will achieve at-least-once delivery by requiring explicit consumer acknowledgements (`XACK`). Exactly-once processing for billing notifications will be enforced on the consumer side via transactional deduplication within our existing PostgreSQL database.

---

## Technical Comparison

The following matrix compares both options across the six required technical properties under our specific team and scale constraints:

| Technical Property | Redis Streams (Chosen) | Apache Kafka (Rejected) |
| :--- | :--- | :--- |
| **Throughput** | **Excellent (In-memory)**<br>Handles tens of thousands of operations/sec per node with sub-millisecond latencies. More than sufficient for our 5,000 req/s 10x target. | **Extreme (Disk sequential I/O)**<br>Can scale to millions of messages/sec. Highly over-engineered for our current and 10x target throughput. |
| **Ordering Guarantees** | **Strict FIFO within Stream**<br>Guaranteed sequential delivery. Message IDs are timestamp-based (e.g., `1518951480106-0`). | **Strict within Partition**<br>Requires design of partition keys to maintain ordering. Global order across partitions is not supported. |
| **Message Retention** | **In-memory (Capped)**<br>Messages are kept in memory. Bounded via stream capping (`MAXLEN` or `MINID`) to prevent Out-Of-Memory (OOM) conditions. | **Disk-based (Persistent)**<br>Configurable time-based or size-based retention (e.g., 7 days or 100GB). Safe for long-term historical storage. |
| **Consumer Groups** | **Native Support**<br>Native implementation (`XGROUP`, `XREADGROUP`, `XACK`). Supports message claiming and pending tracking. | **Native Support**<br>Extremely robust. Supports automatic partition rebalancing, dynamic scaling, and offset commits. |
| **Exactly-Once Semantics** | **Achieved via Idempotency**<br>At-least-once delivery coupled with application-level database deduplication (PostgreSQL transactions). | **Restricted to Internal Streams**<br>Kafka's transaction API supports exactly-once internally (Kafka-to-Kafka), but still requires downstream consumer idempotency for external APIs. |
| **Operational Complexity** | **Near-Zero**<br>Reuses existing infrastructure, monitoring, and backups. Can be configured and deployed in less than 1 day. | **High to Prohibitive**<br>Requires ZooKeeper/KRaft, JVM tuning, network configuration, disk provisioning, and dedicated administration. |

---

## Consequences

### Positive (Pros)
- **Immediate Time-to-Value**: Implementation, testing, and deployment can be completed within 3 to 5 business days, far below the 2-week limit.
- **Minimal Resource and Budget Cost**: Eliminates the licensing/hosting cost of managed Kafka (Confluent Cloud) or the high compute footprint of self-hosting a Kafka cluster.
- **Zero New Operational Dependencies**: No additional monitoring, alerting, or backup strategies are required, as Redis is already fully integrated into our operational workflows.
- **Ultra-low Latency**: In-memory message ingestion and reads minimize the overhead of decoupling notifications from the HTTP thread.
- **Excellent Python Integration**: Well-supported by Python libraries (e.g., `redis-py`, `walrus`), integrating cleanly with our Flask monolith.

### Negative (Cons)
- **Memory Footprint**: Keeping messages in memory represents a risk of Out-of-Memory (OOM) crashes if consumer processing lags behind publisher speed.
- **Lack of Native Long-term Retention**: Redis is not a durable archive. We cannot retain millions of historical notifications in Redis Streams long-term without high memory cost.
- **Lack of Native Exponential Backoff**: Redis Streams does not feature built-in delayed delivery or automatic exponential backoff retry policies.

### Mitigations & Follow-ups
To address the negative consequences of choosing Redis Streams, we will implement the following technical designs:

1. **Preventing OOM with Capped Streams**:
   All notification streams must be published using the capping modifier `MAXLEN ~ 100000` (or `MINID`). A stream limit of 100,000 entries consumes less than 100MB of RAM, providing a massive buffer for consumer downtime while preventing unbounded memory consumption.
2. **Archival and Logging**:
   Redis Streams will be treated strictly as a transient message transport layer. Once notifications are processed, their final statuses, delivery logs, and payloads are persisted to PostgreSQL or external object storage (S3) for long-term audits, keeping Redis lean.
3. **Consumer Idempotency for Exactly-Once Processing**:
   Every billing notification event will be published with a deterministic, unique UUID (e.g., generated in Postgres at event creation). Consumers will process each message inside a database transaction:
   ```sql
   INSERT INTO processed_notifications (notification_id, status) 
   VALUES (:uuid, 'processing') 
   ON CONFLICT (notification_id) DO NOTHING;
   ```
   If the row insertion succeeds, the consumer proceeds to call the external billing/email API. If it fails due to a unique constraint violation, the message is ignored as a duplicate. This pattern guarantees exactly-once processing despite at-least-once delivery.
4. **Custom Retry and DLQ Logic using PEL**:
   We will write a lightweight consumer loop that:
   - Claims pending messages that have been stalled in the PEL using `XAUTOCLAIM`.
   - Tracks retry counts by appending a metadata field to the stream item.
   - Routes messages that exceed a threshold (e.g., 5 failed attempts) to a dedicated Dead-Letter Queue (DLQ) stream for manual intervention and alerting.

---

## Alternatives Considered

### Apache Kafka

We rejected Apache Kafka due to its poor alignment with our team size, timeline, and budget constraints.

- **Why Rejected**:
  1. **High Operational Tax**: Running Kafka without a dedicated platform engineer would impose a severe ongoing maintenance burden on our small 6-person team, distracting from product delivery.
  2. **Violates Setup Constraints**: Deploying a secure, production-grade Kafka cluster, setting up client libraries, and establishing robust monitoring would require at least 3 to 4 weeks of dedicated work, exceeding our 2-week time constraint.
  3. **High Infrastructure Costs**: Kafka requires substantial system resources (specifically disk and RAM for ZooKeeper/KRaft and brokers). Managed solutions (Confluent Cloud) exceed our modest budget at our 10x peak scaling target.
  4. **The "Exactly-Once" Misconception**: While Kafka supports transactional Exactly-Once Semantics (EOS), this only applies to internal Kafka-to-Kafka streams. Because our notification system interacts with external network boundaries (SendGrid, webhook endpoints), Kafka cannot guarantee exactly-once delivery across these endpoints. We would still be required to build application-level deduplication, eliminating one of Kafka's key advantages.
- **When We Would Reconsider**:
  We would reconsider Apache Kafka if our throughput grows past 50,000 requests/second, if we hire a dedicated Site Reliability Engineer (SRE), or if we transition to an event-driven microservices architecture where global event sourcing and log retention are non-negotiable.
