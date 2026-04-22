# ADR-001: Notification Architecture — Apache Kafka vs. Redis Streams

## Status

**Proposed**

## Context

Our Python/Flask monolith handles notifications (emails, webhooks, future WebSocket pushes) synchronously inside the HTTP request cycle. At peak load (~500 req/s), this produces:

- **800 ms average latency**, spiking to **8 s** during peak hours because the caller waits for SMTP/webhook round-trips.
- **Silent failures**: no retry, no dead-letter queue.
- **Cascading failures**: slow downstream endpoints have exhausted connection pools and caused site-wide outages twice this year.
- **No delivery guarantees**: billing-critical events (trial expired, payment failed) can be dropped or duplicated.

We must decouple notification production from consumption, add retry/backoff, and guarantee at-least-once delivery—with exactly-once semantics for billing. Within two quarters we also need to support real-time WebSocket push.

**Hard constraints**

- Engineering team: **6 people** (3 senior, 3 mid-level), **no dedicated infrastructure engineer**.
- We already operate **Redis** in production (session store, rate limiting).
- **No Kafka experience** on the team.
- **≤ 2 weeks** of setup/migration work before the first production value is delivered.
- **Modest budget**: managed Confluent Cloud at scale is not affordable today.
- Must support **10× traffic growth** (~5,000 req/s) without re-architecting.

## Decision

We will use **Redis Streams** as the notification backbone.

### Justification

The choice is driven by **operational feasibility within the 2-week window** and **the team’s existing operational expertise**, while still meeting throughput, ordering, and growth requirements.

1. **Throughput headroom for 10× growth**  
   Our current peak is ~500 req/s. A single Redis instance can sustainably process **> 10,000 messages/second** with sub-millisecond latency. Even at 10× growth we remain well within single-node headroom, and Redis Cluster can scale horizontally if we eventually exceed that.

2. **Ordering guarantees**  
   Redis Streams preserves **total order within a single stream**. Producer code will shard billing events into a dedicated `stream:billing` partition and operational events into `stream:ops`, giving us deterministic ordering per notification class without the complexity of Kafka topic partitioning.

3. **Message retention**  
   Redis is memory-bound, but Streams supports **consumer-group-aware trimming** (`MAXLEN` or `MINID`). We will cap streams at ~1 M entries (~512 MB with our payload size) and archive every billing event to PostgreSQL before trimming. This satisfies audit requirements without requiring the multi-terabyte disk retention Kafka would need to be valuable.

4. **Consumer groups**  
   Redis Streams has **native consumer groups** (`XREADGROUP`) with automatic ownership tracking, pending-entry lists for failed messages, and claim semantics. This gives us the same consumer-scaling model as Kafka without a separate consumer-coordinator process.

5. **Exactly-once semantics for billing**  
   Neither Redis Streams nor a self-hosted Kafka cluster gives us “free” exactly-once delivery in a Python/Flask stack. Kafka’s EOS requires **idempotent producers + transactional consumers**, which demand careful client-side configuration and significant debugging expertise we do not have.  
   We will instead implement **application-level exactly-once**:
   - Producers assign a deterministic `idempotency_key` (UUID v5 derived from entity + event type + timestamp bucket) to every billing message.
   - Consumers `INSERT … ON CONFLICT DO NOTHING` the key into a PostgreSQL `idempotency_log` table before processing.
   - This pattern is operationally simpler, leverages our existing RDBMS expertise, and is robust enough for our scale.

6. **Operational complexity**  
   We already monitor, back up, and failover Redis today. Adding Streams is a **configuration change**, not a new distributed system to operate. By contrast, self-hosting a production Kafka cluster (3+ brokers, ZooKeeper or KRaft, replication, ISR tuning, rebalancing) would consume our entire 2-week budget merely for provisioning, with no time left for application migration.

## Consequences

### Pros

- **Fast time-to-value**: Streams can be enabled on our existing Redis nodes; the first async notification pipeline can ship in days, not weeks.
- **Low operational risk**: Same monitoring, alerting, and runbooks we already use for sessions and rate limiting.
- **Low latency**: P95 read latency stays < 5 ms, keeping WebSocket push viable when we add it next quarter.
- **Built-in pending list**: `XPENDING` / `XCLAIM` give us a native retry/dead-letter mechanism without extra infrastructure.
- **Cost**: $0 incremental infrastructure spend; no managed-service bill.

### Cons

- **Memory ceiling**: Retention is bounded by RAM. If message volume unexpectedly explodes beyond 10× or our trimming logic stalls, we could evict data before it is consumed. We will mitigate this with aggressive monitoring on memory usage and a fallback archival path to PostgreSQL.
- **Exactly-once is application-owned**: We must maintain the idempotency table schema, indexes, and cleanup jobs. A bug in consumer code could still duplicate a billing email if the idempotency check is skipped.
- **Fewer ecosystem tools**: We do not get Kafka Connect, Schema Registry, or ksqlDB out of the box. Any future stream-processing needs (e.g., real-time analytics) will require custom Python workers.
- **Single-point-of-failure**: Our current Redis setup is a single primary. A total Redis outage pauses notifications. We will schedule a follow-up ADR on Redis Sentinel or Cluster for HA, but that is out of scope for the 2-week migration.

## Alternatives Considered

### Apache Kafka

**Why it was rejected**

Kafka is technically superior on paper for long-term streaming workloads:

- **Higher theoretical throughput**: Kafka clusters routinely sustain millions of messages per second.
- **Disk-based retention**: Messages stay on disk for days or weeks, decoupling retention from RAM.
- **Native exactly-once semantics (EOS)**: Idempotent producers and transactions provide end-to-end exactly-once processing without application-level deduplication tables.

However, for **our** team and timeline, these advantages are outweighed by **operational intractability**:

- **Setup cost exceeds budget**: A minimal production cluster needs 3 brokers, replication factor ≥ 2, and either ZooKeeper or KRaft bootstrap. For a team with zero Kafka experience, reaching production-readiness—including partitioning strategy design, consumer rebalancing tuning, and monitoring instrumentation—would consume **4–8 weeks**, not 2.
- **Ongoing operational tax**: Without a dedicated infrastructure engineer, routine tasks such as partition rebalancing, broker replacement, and offset-management debugging would pull application engineers away from product work.
- **Exactly-once is not “free”**: Kafka EOS requires transactional producer/consumer code, careful `transactional.id` management, and deep understanding of `isolation.level`. Misconfiguration still produces duplicates or gaps. The learning curve is steep enough that we would likely ship application-level idempotency anyway during the first iteration.
- **Budget**: Managed Kafka (Confluent, MSK) would solve the operational problem but is explicitly ruled out by our modest budget.

Given our current scale (500 req/s, 10× target still < 5,000 req/s), Kafka is **premature optimization**. We will revisit Kafka if we exceed Redis’s single-node throughput ceiling or hire dedicated platform engineering capacity.
