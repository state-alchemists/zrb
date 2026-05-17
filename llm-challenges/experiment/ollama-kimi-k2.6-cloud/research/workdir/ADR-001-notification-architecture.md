# ADR-001: Notification Architecture — Redis Streams

## Status

Proposed

## Context

Our synchronous notification module is a systemic bottleneck. Key metrics and constraints from `system_context.md`:

- **Current load**: 85,000 MAU, ~2M tasks/month, peak ~500 req/s.
- **Current pain**: Notifications block the HTTP response cycle. Average latency is 800ms, spiking to 8s at peak. Silent failures, no retry, and two incidents this year where slow webhook endpoints caused connection pool exhaustion and cascading failures.
- **Hard requirement**: Billing-critical notifications (trial expired, payment failed) must not be duplicated.
- **Targets**: Async processing, exponential backoff retry, at-least-once delivery, exactly-once for billing, real-time WebSocket push within 2 quarters, and headroom for 10x traffic growth (~5,000 req/s peak).
- **Team constraints**: 6 engineers, no dedicated infrastructure role. We already operate Redis (sessions, rate limiting). No Kafka experience on the team. Setup and migration must deliver value within 2 weeks. Budget is modest — managed Confluent Cloud is not viable.

The core decision is which message broker to adopt: **Apache Kafka** or **Redis Streams**.

## Decision

We will adopt **Redis Streams** as the message broker for the notification subsystem.

### Justification

| Criterion | Redis Streams | Apache Kafka (self-hosted) |
|---|---|---|
| **Operational fit** | Already in production; team has on-call runbooks, monitoring, and failover playbooks. | Greenfield infrastructure — new EC2 instances, new failure modes, new on-call burden. |
| **Setup timeline** | Can reuse existing Redis instance or provision a second node in hours. | Self-hosted cluster (3+ brokers, ZooKeeper or KRaft) requires days of provisioning, tuning, and stabilization. |
| **Throughput at scale** | Peak 500 req/s is trivial; 10x growth to ~5,000 req/s is well within a single Redis instance — and can be sharded if needed. | Superior ceiling, but that margin is unnecessary for our growth horizon. |
| **Exactly-once for billing** | Not native. Achieved by application-level idempotency: consumers use PostgreSQL unique constraints on deterministic notification UUIDs before emitting side effects (sending email, calling API). | Native exactly-once (idempotent producer + transactions + consumer isolation). |
| **Ordering guarantees** | Per-stream ordering by default. | Partition-scoped ordering; requires careful key design. |
| **Message retention** | Trims by length or age; bounded by available memory. Can offload to PostgreSQL audit tables for long-term compliance. | Disk-backed, configurable time/size retention. Superior for long-term replay and audit. |
| **Consumer groups** | Supported with automatic claim and explicit ACKs. Rebalancing is simpler but less sophisticated than Kafka. | Mature consumer group protocol with automatic partition rebalancing. |
| **Real-time roadmap** | Redis Pub/Sub (already available) is the natural substrate for WebSocket push within 2 quarters. | Would require an additional bridge or separate pub/sub layer. |
| **Ecosystem** | Smaller ecosystem; connectors for SendGrid, Twilio, Slack must be built in-house. | Rich ecosystem (Kafka Connect, ksqlDB), but adds operational weight we cannot absorb. |
| **Cost** | Incremental (larger instance or second node). | Significant new infrastructure cost (brokers, storage, monitoring, engineering time). |

**Definitive reasoning**: A 6-person team without a dedicated infrastructure engineer cannot safely own and operate a self-hosted Kafka cluster inside a 2-week deadline. The operational risk — misconfigured replication, broker imbalance, partition exhaustion, or unclear failure modes — directly contradicts our goal of eliminating cascading failures. Redis Streams gives us async decoupling, consumer groups, explicit ACK/retry, and sufficient throughput today and at 10x scale, while keeping our operational surface area minimal. The exactly-once gap for billing is closed by idempotent consumers, which is a pattern we can implement reliably inside our existing PostgreSQL-backed application.

## Consequences

### Pros

- **Rapid time-to-value**: Can be production-ready in under one week, meeting the 2-week constraint with margin.
- **Leverages existing expertise**: Engineers already know how to monitor, back up, and fail over Redis.
- **Minimal new infrastructure**: Reuses or minimally expands an existing dependency rather than introducing a distributed system with distinct failure modes.
- **Natural path to WebSocket push**: Redis Pub/Sub is already part of the same technology; streaming and real-time push share operational concerns.
- **Controllable exactly-once implementation**: Application-level idempotency (e.g., `INSERT INTO processed_events (idempotency_key, …) ON CONFLICT DO NOTHING`) is explicit, testable, and auditable inside our monolith.

### Cons

- **Application-level exactly-once burden**: Duplicate processing can still occur if the idempotency check is bypassed or misimplemented. This requires strict code review and integration tests for billing consumers.
- **Durability ceiling**: Messages live in memory. A catastrophic failure before AOF/RDB persistence can lose in-flight data. We mitigate this by treating Redis Streams as a queue, not a source of truth, and by acking only after successful idempotent PostgreSQL writes.
- **Limited retention**: Long-term audit trails cannot live in Redis. We must archive processed billing events to PostgreSQL or S3.
- **Coarse consumer group rebalancing**: Scaling consumers up or down can cause brief duplicate processing during rebalancing; idempotency is the safety net.
- **Ecosystem gap**: No off-the-shelf connectors for external providers. We will write and maintain these integrations ourselves.
- **Future Redis saturation**: At 10x scale plus WebSocket Pub/Sub, session, and rate-limit traffic, Redis may need to be split into workload-dedicated nodes. This is a known, incremental migration rather than a full re-architecture.

## Alternatives Considered

### Apache Kafka (self-hosted)

Kafka was rejected as the primary choice for this phase.

- **Throughput and retention are superior**, and native exactly-once is compelling. However, these properties are only valuable if the system is operated correctly.
- **Operational complexity is prohibitive for our team size**: A production Kafka cluster requires broker tuning, partition planning, replication factor management, and ZooKeeper/KRaft oversight. The learning curve and ongoing toil are incompatible with a 6-person engineering team that has zero prior experience and no dedicated infrastructure engineer.
- **Timeline risk**: Standing up a stable, monitored, production-hardened Kafka cluster, writing client code, and migrating traffic safely cannot be done in 2 weeks without accepting unacceptable risk.
- **Budget constraint**: Managed Kafka (Confluent Cloud, MSK) would eliminate the operational burden but is explicitly ruled out by budget constraints.
- **Risk/reward mismatch**: Our current incidents stem from operational coupling and lack of backpressure. Introducing a complex distributed system we do not yet know how to operate increases, rather than decreases, the probability of future cascading failures.

Kafka remains a valid future candidate if our scale eventually outgrows Redis Streams or if we hire dedicated platform engineering. We will instrument stream depth, consumer lag, and Redis resource utilization to provide an objective trigger for that future evaluation.
