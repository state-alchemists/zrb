# ADR-001: Notification Subsystem — Async Processing Architecture

**Status:** Proposed

---

## Context

We run a SaaS project management platform (85k MAU, ~500 req/s peak). Notifications (email, webhook) are sent synchronously inside the HTTP request cycle, causing request timeouts, silent failures, and cascading outages. We need to decouple notification delivery from request handling.

### Requirements

- **Async dispatch**: move notification delivery out of the HTTP request cycle
- **Retry with exponential backoff** for transient delivery failures
- **At-least-once delivery** for all notifications; **exactly-once** for billing events
- **WebSocket push** capability within 2 quarters
- **10x traffic headroom** without re-architecting

### Constraints

- **Team**: 6 engineers (3 senior, 3 mid-level), no dedicated infrastructure engineer
- **Existing stack**: Redis is already in production (session storage, rate limiting). No Kafka or other message broker.
- **Team experience**: No Kafka experience. Team is comfortable with Redis.
- **Timeline**: Must ship value within 2 weeks of setup/migration work.
- **Budget**: Modest. Managed Confluent Cloud is unaffordable; self-hosted Kafka would add significant operational cost.
- **Exactly-once semantics** are mandatory for billing-critical notifications.

---

## Decision

**Adopt Redis Streams** as the notification message broker.

Notifications will be produced into Redis Streams from the Flask request handler (non-blocking, sub-millisecond write), and consumed by a separate background worker process (Python daemon) that handles delivery, retry logic, and dead-letter queues. Billing notifications will use idempotent consumers with a deduplication key stored in Redis to achieve exactly-once delivery.

### Why Redis Streams over Kafka

| Criterion | Redis Streams | Kafka | Why It Tips the Scale |
|---|---|---|---|
| **Existing infrastructure** | ✅ Already in production | ❌ New cluster to provision, monitor, and secure | Zero-cost infra addition. Reuses existing Redis deployment. |
| **Team expertise** | ✅ Team is comfortable with Redis | ❌ Zero Kafka experience | No learning curve. Can ship in days, not weeks. |
| **Time-to-value** | ✅ Days to integrate | ❌ Weeks to learn + deploy + tune | Must deliver within 2 weeks. |
| **Operational burden** | ✅ Single process, no new moving parts | ❌ Requires brokers, ZooKeeper/KRaft, monitoring | 6-person team cannot absorb a distributed system to babysit. |
| **Throughput at our scale** | ✅ Handles 100k+ msg/s on modest hardware | ✅ Handles millions | Current peak is ~500 req/s; 10x is 5k req/s. Both exceed this by orders of magnitude. Kafka is overkill. |
| **Exactly-once semantics** | ⚠️ Achieved via idempotent consumers + dedup keys | ✅ Built-in (transactions, idempotent producer) | Both can achieve it. Redis requires application-level discipline; Kafka provides it at the protocol level. |
| **Message retention** | ⚠️ Bounded by memory (configurable) | ✅ Disk-based, long-term retention | For a notification queue, long-term retention isn't needed — messages are consumed and dead-lettered. |
| **Consumer groups** | ✅ Solid consumer group support with PEL | ✅ Mature consumer group rebalancing | Both support this adequately. |
| **Ordering** | ✅ Per-stream ordering guaranteed | ✅ Per-partition ordering guaranteed | Both meet the ordering needs for per-task notification sequences. |
| **Budget** | ✅ $0 additional infra cost | ❌ Requires dedicated EC2 instances + EBS | Kafka (even self-hosted) would triple our message-infra cost. |

### Architecture Outline

```
HTTP Request
    │
    ▼
Flask Handler ──► XADD notification:stream {task_id, type, payload}
                        │
                        ▼
              Redis Stream (PEL tracks pending)
                        │
                        ▼
              Background Worker (Python)
                    │          │
                    ▼          ▼
              Email API    Webhook     ──► Retry with backoff (3 attempts)
                    │          │              └─► Dead-letter queue on failure
                    ▼          ▼
               XACK on success   (billing: dedup check before send)
```

### Exactly-Once Implementation for Billing

Billing notifications will carry a deduplication key (`billing:<event_id>`). The consumer worker will:

1. **Before processing**: `SET billing:<event_id> "processing" NX PX <timeout>` — fails if key exists (duplicate).
2. **Process**: Deliver the notification.
3. **On success**: `SET billing:<event_id> "delivered"` with TTL.

This, combined with `XREADGROUP` and `XACK`, provides exactly-once delivery in the presence of consumer crashes and restarts.

---

## Consequences

### 👍 Positive

1. **Immediate time-to-value**: Integration can be shipped within 1 week. Redis Streams `XADD` / `XREADGROUP` is a thin API over Redis the team already knows.
2. **Zero new infrastructure**: No new servers, processes, or backing services to learn, deploy, or monitor.
3. **WebSocket-friendly**: Redis Pub/Sub (or the same Streams) can feed a WebSocket relay — no Kafka-to-WebSocket bridge needed later.
4. **Retry is built-in**: The PEL (Pending Entry List) in consumer groups provides automatic retry — unacknowledged messages are re-delivered to another consumer in the group.
5. **Operationally simple**: The existing Redis alerting, backup, and failover procedures carry over unchanged.
6. **Budget-neutral**: No additional compute or managed-service costs.

### 👎 Negative

1. **Exactly-once requires discipline**: Redis Streams provides no native exactly-once guarantee. The dedup-key approach is battle-tested but requires every billing consumer to implement the pattern correctly. A bug in the dedup logic could cause duplicate delivery.
2. **Memory-bound retention**: Streams live in RAM. If consumers fall behind, the stream grows until it hits `maxmemory` or the configured `MAXLEN` trim. At 10x scale, we will need to monitor stream length and consumer lag.
3. **Lower ceiling than Kafka**: At extreme scale (millions of messages per second, terabytes of data), Redis Streams would struggle while Kafka thrives. This is not a concern at our current or projected 10x volume (~5k msg/s).
4. **No partitioning fan-out**: Kafka allows multiple independent consumer groups reading from the same topic at independent offsets. Redis Streams supports this, but the per-stream consumer group model is less flexible with many independent subscribers. Mitigation: use separate streams or separate consumer groups within a stream.
5. **Future migration cost**: If we outgrow Redis Streams, migrating to Kafka later will require a dual-write migration. This is acceptable offset against years of simpler operations.

---

## Alternatives Considered

### Apache Kafka (Self-hosted)

Kafka offers robust persistence (disk-based), native exactly-once semantics, high throughput, and long retention. However:

- **Team inexperience**: The 6-person team has zero Kafka exposure. Learning deployment, tuning, and operations would take 3–6 weeks — half the timeline.
- **Operational burden**: A production Kafka cluster requires ZooKeeper or KRaft, broker sizing, partition tuning, and continuous monitoring. We have no dedicated infrastructure engineer.
- **Overkill for load**: 500–5,000 messages/second is a trivial load for Kafka. We would pay the operational complexity tax for capacity we will not need for years.
- **Budget pressure**: Self-hosted Kafka on AWS (3 brokers × m6g.large + EBS) costs ~$500/month before any managed service overhead. Not a blocker alone, but significant for a modest budget with no clear payoff at this scale.

**Recommendation: Reject** — too much operational complexity and learning curve for the team size and scale.

### RabbitMQ

RabbitMQ is a battle-tested message broker with good routing and retry support. It was considered but rejected because:

- It is not currently in the stack — requires new infrastructure.
- Consumer groups work differently (AMQP queues) and scaling consumers requires manual queue configuration.
- No native stream-with-retention model; queues are transient by default (though quorum queues and streams were added in later versions).
- Would still require a dedicated Erlang VM to learn, deploy, and tune.

**Recommendation: Reject** — adds operational complexity comparable to Kafka with fewer scaling advantages.

### AWS SQS / SNS

Serverless, fully managed, zero operational overhead. Rejected because:

- **Cost at scale**: At 500 req/s × 2M tasks/month, SQS/SNS costs are manageable today but grow linearly with throughput. No budget control.
- **Vendor lock-in**: Ties the notification subsystem irrevocably to AWS.
- **WebSocket integration**: No native push-to-client; requires a separate WebSocket relay server, adding complexity.
- **No ordering guarantees**: SQS FIFO queues limit throughput to 300 msg/s — insufficient at 10x scale. Standard queues offer only best-effort ordering.

**Recommendation: Reject** — cost unpredictability and vendor lock-in outweigh convenience.

### Keep Synchronous (Status Quo)

Maintain the existing synchronous notification path. Rejected because it is the source of all four documented problems: timeouts, silent failures, cascading failures, and no delivery guarantees. Any growth or reliability investment mandates async decoupling.

**Recommendation: Reject** — does not solve any of the documented problems.

---

## Migration Plan

| Phase | Timeline | Work |
|---|---|---|
| **Phase 1: Critical path** | Week 1 | Add Redis Stream producer to HTTP handler for task-update events. Deploy single consumer worker for email notifications. Enable retry with dead-letter queue. |
| **Phase 2: Billing** | Week 2 | Add exactly-once dedup for billing events. Validate against payment-failed and trial-expired flows. |
| **Phase 3: WebSocket** | Quarter 2 | Add consumer that publishes to Redis Pub/Sub; WebSocket server subscribes and pushes to clients. |
| **Phase 4: Monitoring** | Ongoing | Add consumer lag alerts, dead-letter count dashboards, stream length tracking. |
