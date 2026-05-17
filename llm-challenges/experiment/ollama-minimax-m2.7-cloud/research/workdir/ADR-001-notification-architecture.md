# ADR-001: Notification Subsystem Message Broker

## Status

**Proposed**

## Context

We operate a SaaS project management platform (85,000 MAU, ~2M tasks/month, peak 500 req/s). The notification module currently processes emails and webhooks synchronously inside the HTTP request cycle, causing:

1. **Latency**: Average 800ms, spikes to 8s during peak hours
2. **Silent failures**: No retry mechanism when email providers or webhook endpoints fail
3. **Cascading failures**: Two incidents where slow webhook endpoints caused connection pool exhaustion
4. **No delivery guarantees**: Billing-critical notifications lack exactly-once semantics

**Scaling requirements:**
- Decouple notifications from HTTP request cycle
- Retry with exponential backoff
- At-least-once delivery for billing events, exactly-once where feasible
- Support WebSocket push notifications within 2 quarters
- Handle 10x traffic growth (5,000 req/s) without re-architecting

**Team constraints:**
- 6 engineers (3 senior, 3 mid-level), no dedicated infrastructure engineer
- No Kafka experience on the team
- Existing production Redis (session storage, rate limiting)
- 2-week maximum to deliver initial value
- Modest budget — cannot afford managed Confluent Cloud
- Must maintain exactly-once semantics for billing notifications

## Decision

**We will use Redis Streams as the message broker for the notification subsystem.**

### Justification

Given the team's constraints (no Kafka experience, no dedicated infra engineer, existing Redis proficiency, tight timeline), Redis Streams provides the best balance of capability, operational simplicity, and time-to-value. The team can implement and operate Redis Streams using existing Redis knowledge, eliminating the steep learning curve and operational overhead that Kafka would introduce.

Redis Streams supports:
- Consumer groups via `XREADGROUP` with `XACK` for acknowledgment-based retry
- Message retention via `EXPIRE` on stream keys
- At-least-once delivery with manual acknowledgment
- Exactly-once semantics for billing notifications via idempotency keys embedded in message payloads
- Sufficient throughput for current load (500 req/s) and near-term scale (10x)

Kafka's superior throughput and durability become relevant at much higher volumes (>10,000 msg/s sustained) or when message retention spans weeks. Our peak of 5,000 msg/s is well within Redis Streams' practical capacity, especially given that notification payloads are small (JSON under 4KB). If we encounter scaling limits, Redis Cluster can distribute reads across replicas.

## Consequences

### Pros

1. **No new infrastructure**: We already run Redis in production. No additional services to provision, monitor, or maintain.
2. **Operational familiarity**: The team already understands Redis. No new mental models, no unfamiliar CLI tools, no cluster management.
3. **Simple consumer groups**: `XREADGROUP` provides reliable competing consumer pattern. Workers claim jobs, process them, and `XACK` on success. On failure, the message remains pending and can be retried by the same or another worker.
4. **Exactly-once via idempotency keys**: Billing notifications include a unique `idempotency_key` (e.g., `billing_event:{user_id}:{event_type}:{timestamp}`). Workers check against a Redis set before processing, then mark as processed after successful delivery. This guarantees exactly-once semantics without distributed transactions.
5. **Retry with exponential backoff**: Pending messages not acknowledged within a timeout window can be reclaimed using `XPENDING` + `XCLAIM`. Each retry increments a counter; messages exceeding a threshold (e.g., 5 retries) route to a dead-letter stream for manual intervention.
6. **Fast delivery**: Redis Streams offers sub-millisecond latency for consumer reads — faster than Kafka's typical 5–50ms end-to-end latency.
7. **Native integration with existing cache**: Session data, rate limiting, and notification state share the same Redis instance, reducing cross-service data movement.
8. **Lower operational overhead**: No JVM, no Zookeeper/KRaft, no partition balancing. Single `redis-server` process; Redis Cluster for HA if needed.

### Cons

1. **Single-threaded bottleneck**: Redis is single-threaded for command processing. At very high throughput (>50,000 req/s), this becomes a constraint. Our target of 5,000 req/s is well below this, but 10x growth beyond that would require Redis Cluster sharding.
2. **No native exactly-once**: Unlike Kafka's transactional producers, Redis Streams requires application-level idempotency logic. This is a minor implementation concern but adds code to maintain.
3. **Limited message retention**: Redis Streams are not designed for weeks-long retention like Kafka. For audit or replay use cases, we would need to fork messages to a separate store. For our notification use case (retry within hours, not days), this is acceptable.
4. **Smaller ecosystem**: Fewer third-party integrations, monitoring tools, and community patterns compared to Kafka. The team cannot leverage existing Kafka expertise.
5. **No log compaction**: Kafka supports log compaction for key-based message updates. Redis Streams does not; we must design around this if we need mutable notification state.
6. **Operational risk concentration**: Adding notification workloads to the same Redis instance used for sessions and rate limiting introduces resource contention risk. Mitigation: dedicated Redis instance or memory reservation via `maxmemory-policy`.

## Alternatives Considered

### Apache Kafka

Kafka offers best-in-class durability, throughput, and exactly-once semantics at the broker level. Consumer groups, message retention (configurable to weeks), and offset management are mature and battle-tested.

**Why we rejected it:**

1. **Operational complexity**: Running Kafka requires either a managed service (Confluent Cloud — budget-prohibitive at scale) or self-managed brokers with Zookeeper or KRaft. Partition assignment, replication factor, ISR tuning, and controller elections are non-trivial. For a team of 6 with no Kafka experience and no dedicated infra engineer, this creates significant operational burden.

2. **Time-to-value**: Initial Kafka setup, including broker configuration, producer/consumer library integration, schema registry (if Avro/Protobuf), and monitoring, typically exceeds 2 weeks for a team new to the technology. Our constraint is firm on this timeline.

3. **Overengineering for current scale**: Kafka's strengths (million+ msg/s, weeks of retention, cross-datacenter replication) are not needed for our current load (500 req/s peak) or near-term target (5,000 req/s). Redis Streams handles this comfortably.

4. **Resource overhead**: Kafka brokers are memory and disk hungry (JVM heap, page cache for throughput). Our modest AWS instances are better suited to Redis, which shares our existing infra.

5. **No existing expertise**: The team would need to learn consumer group rebalancing, offset commits, retention policies, and cluster management from scratch. This learning curve delays delivery and increases risk.

**Kafka would be the correct choice** if we anticipated:
- Sustained throughput >10,000 msg/s
- Regulatory requirement for multi-week message audit trails
- Multi-region replication for disaster recovery
- Cross-team event streaming (multiple producer/consumer teams)

Given our current constraints, the operational cost of Kafka outweighs its benefits.

---

**Note on future migration**: If Redis Streams becomes insufficient (e.g., throughput exceeds 20,000 msg/s or retention needs extend beyond days), Kafka remains a viable migration target. The notification producers and consumers are decoupled from the transport layer — swapping Redis Streams for Kafka would require changes to the message broker integration only, not the business logic.