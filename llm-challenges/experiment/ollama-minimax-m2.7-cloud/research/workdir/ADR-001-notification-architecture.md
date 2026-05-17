# ADR-001: Notification Subsystem — Kafka vs Redis Streams

## Status

**Proposed**

---

## Context

The notification module (emails and webhooks on task events) is currently embedded synchronously in the Flask HTTP request cycle. This has caused request timeouts (avg 800ms, spikes to 8s), silent failures on downstream errors, cascading failures from slow webhook endpoints exhausting connection pools, and zero delivery guarantees for billing-critical notifications.

We need to decouple notification processing, add retry with exponential backoff, guarantee at-least-once delivery (exactly-once for billing), and handle 10x traffic growth. Our constraints:

- **Team**: 6 engineers (3 senior, 3 mid-level), no dedicated infrastructure engineer, no Kafka experience
- **Existing infra**: Redis running in production for sessions and rate limiting
- **Timeline**: Must deliver value within 2 weeks of starting the work
- **Budget**: Cannot afford managed Confluent Cloud; self-managed or minimal-additional-cost only
- **Scale**: 500 req/s peak, ~2M tasks/month; must scale to 10x without re-architecture

---

## Decision

**We will use Redis Streams for the notification subsystem.**

Redis Streams satisfies the functional requirements (async decoupling, retry with backoff, consumer groups, at-least-once delivery) with significantly lower operational overhead than Kafka, leveraging our existing Redis investment and matching the team's current expertise. The two-week delivery constraint rules out the learning and operational curve of Kafka.

For billing-critical notifications requiring exactly-once semantics, we will implement idempotent consumers using a deduplication table in PostgreSQL (storing processed notification IDs with an expiry). This is a well-understood pattern for this team and avoids the operational cost of Kafka transactions.

---

## Consequences

### Pros of Redis Streams

| Property | Detail |
|---|---|
| **Operational simplicity** | Single additional component (Redis module already running). No new cluster to manage, no broker leadership, no partition rebalancing logic to understand. |
| **Team familiarity** | Engineers already operate and debug Redis in production. No new mental model, no Kafka training curve. |
| **Delivery speed** | Can have a working prototype in days, not weeks. Consumer groups, XREAD/XACK, and retry logic map directly to our requirements. |
| **Existing infra cost** | No new managed service bill. Redis Streams uses existing Redis nodes (with config adjustment for `maxmemory` and `stop-writes-on-bdfull`). |
| **Throughput adequate** | Redis Streams sustains 50k–100k ops/sec on commodity hardware; our 500 req/s peak is well within capacity. |
| **Message retention** | Stream entries retained on disk (`StreamLen 100000` limit) and TTL configurable — allows consumer restart to replay missed events. |
| **Consumer groups** | XREADGROUP + XACK provides at-least-once with acknowledgements, competing consumers, and dead-letter tracking via a separate stream. |
| **Retry semantics** | Implemented in the consumer: on failure, re-read from last acknowledged offset; optionally re-enqueue to a retry stream with TTL-based backoff. |
| **Pending Entries List (PEL)** | Redis tracks unacknowledged messages per consumer — enables recovery without message loss if a consumer crashes. |

### Cons of Redis Streams

| Property | Risk | Mitigation |
|---|---|---|
| **Exactly-once semantics** | Redis Streams guarantees at-least-once, not exactly-once. | Implement idempotent consumers: store notification UUID in a `processed_notifications(id, expires_at)` PostgreSQL table; check before processing. |
| **Disk-backed durability** | AOFfsync every second (default) means up to 1s data loss on disk failure. | Enable `appendfsync always` for billing stream if latency budget allows; or accept the 1s window for non-billing events. |
| **Message retention limits** | Long retention (weeks) can increase memory/disk usage significantly. | Use `MAXLEN` or `MINID` trimming policies; route billing audit logs to PostgreSQL for long-term storage instead. |
| **Scalability ceiling** | Redis is single-threaded for some operations; very high throughput (500k+/sec) would eventually require sharding. | Our 500 req/s ceiling leaves 1000x headroom before this becomes relevant. |
| **No native partition offset tracking across language clients** | Consumer lag monitoring requires XINFO or third-party tools. | Use Redis INFO + Prometheus exporter or a lightweight custom dashboard. |
| **Operational gap for Kafka-grade features** | No native cross-datacenter replication, no schema registry, no connect ecosystem. | Not required for current scope; re-evaluate if WebSocket push scales to multi-region within 2 quarters. |

---

## Alternatives Considered

### Apache Kafka

**Rejected.**

| Property | Kafka | Redis Streams |
|---|---|---|
| **Operational complexity** | Requires ZooKeeper or KRaft cluster, partition leadership, replication factor configuration, broker monitoring. Without a dedicated infra engineer, initial setup and incident response will consume significant engineering time. | Single Redis instance, familiar tooling, existing monitoring. |
| **Learning curve** | No team experience. Consumer groups, offset management, retention policies, and exactly-once transactions require 2–4 weeks of ramp-up before productive work begins. | Linear mental model: streams behave like append-only lists with consumer groups. |
| **Setup time** | Production-ready Kafka cluster (3 brokers, replication, monitoring, alerts) realistically takes 3–4 weeks for a team with no prior experience — exceeding our 2-week constraint. | Existing Redis cluster requires config changes and a consumer library. Prototype in days, production-ready in 1–2 weeks. |
| **Exactly-once** | Native exactly-once semantics via Kafka Transactions (producer + consumer). | Requires idempotent consumer layer (PostgreSQL dedup table). |
| **Throughput** | 100k–1M messages/sec — overkill for our current and 2-year projected load. | 50k–100k ops/sec — adequate for 500 req/s with 100x headroom. |
| **Cost** | Self-managed on EC2: 3+ brokers × $150–300/month = $450–900/month bare minimum before compute/storage. Managed MSK: starts ~$0.10/partition-hour, rapidly exceeding budget. | Zero marginal cost (uses existing Redis nodes with config adjustments). |
| **Fleet management** | Need to manage Kafka version upgrades, security patches, broker failures. | Handled by existing Redis operational practices. |

Kafka would be the correct choice if we had an infrastructure engineer, a team with prior Kafka experience, or a requirement for millions of events per second with multi-region replication. Given our constraints, the operational overhead would be disproportionate to the benefit.

---

## Summary

Redis Streams delivers the required decoupling, retry semantics, consumer groups, and at-least-once delivery — the critical pieces — without introducing new infrastructure, new operational concepts, or a timeline risk. The exactly-once requirement for billing events is satisfied via an idempotent consumer pattern that is straightforward to implement and audit. Kafka is a superior technology for high-throughput, multi-team, multi-region scenarios; this system does not (yet) qualify.