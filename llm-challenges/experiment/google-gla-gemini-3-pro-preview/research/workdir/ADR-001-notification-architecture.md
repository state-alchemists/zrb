# Title
ADR-001: Message Broker for Asynchronous Notification Subsystem

# Status
Proposed

# Context
Our SaaS project management platform (85,000 MAU, ~2M tasks/month, peak ~500 req/s) currently processes notifications (emails, webhooks) synchronously within the HTTP request cycle. This architecture has led to request timeouts (latency spikes up to 8s), silent message drops when external providers fail, cascading system failures from connection pool exhaustion, and a lack of delivery guarantees for billing-critical events.

To support 10x traffic growth and the upcoming introduction of real-time WebSocket push notifications within two quarters, we must decouple notification processing from the web request cycle. 

Our constraints are strict:
- A 6-person engineering team with no dedicated infrastructure engineer.
- No prior team experience operating Apache Kafka.
- A maximum of two weeks for setup and migration before delivering value.
- A modest budget that precludes expensive managed services like Confluent Cloud.
- We already successfully operate Redis in production for session storage and rate limiting.
- We must guarantee exactly-once processing semantics for billing-critical events.

We evaluated two message broker technologies to serve as the backbone of our asynchronous processing pipeline: Apache Kafka and Redis Streams.

# Decision
We will use **Redis Streams** as the message broker for the new asynchronous notification subsystem.

**Justification:**
Given our team size (6 developers, no infra engineer), our strict two-week migration window, and our existing operational footprint (Redis is already in production), Redis Streams provides the best balance of capability and operational simplicity. 

Redis Streams natively supports **Consumer Groups**, allowing us to reliably distribute notification processing across multiple consumer instances. The Pending Entries List (PEL) feature enables robust retry mechanisms with exponential backoff for failed webhook or email deliveries. 

While Kafka natively supports transactional messaging, we can achieve the required exactly-once semantics for billing notifications by pairing Redis Streams' at-least-once delivery guarantees (via consumer groups and explicit `XACK`) with idempotent consumer logic. We will enforce this idempotency by tracking processed message IDs in our existing PostgreSQL database using transactions.

At our target 10x scale (peak ~5,000 req/s), Redis can comfortably handle the throughput without the significant operational overhead of deploying and maintaining a distributed Kafka cluster.

# Consequences

**Pros:**
- **Zero New Infrastructure Setup:** We reuse our existing Redis deployment, completely de-risking the two-week implementation timeline and avoiding new operational burdens.
- **Low Operational Complexity:** No need to manage KRaft/Zookeeper, partition replication, or JVM memory tuning without a dedicated infrastructure engineer.
- **Built-in Consumer Groups:** Natively supports competing consumers and message acknowledgment, preventing silent failures and making dead-letter queues straightforward to implement via PEL.
- **Cost Effective:** Avoids the high infrastructure costs of a self-hosted Kafka cluster or premium managed stream services.

**Cons:**
- **Memory Bound Storage:** Unlike Kafka, which persists to disk, Redis Streams holds data in RAM. We must carefully configure data retention (e.g., using `MAXLEN`) to prevent Out of Memory (OOM) crashes on our Redis instance.
- **Idempotency Burden:** Redis does not have Kafka's built-in transactional producer/consumer semantics; exactly-once processing must be explicitly handled at the application layer via idempotency keys and database constraints.
- **Limited Ecosystem:** Kafka has a richer ecosystem of stream processing frameworks and connectors. We will have to build custom WebSocket fan-out logic later this year instead of relying on off-the-shelf Kafka connectors.

# Alternatives Considered

**Apache Kafka**
Kafka is the industry standard for high-throughput, durable event streaming and offers unparalleled persistence, strict ordering guarantees, and massive scalability. It was rejected for the following reasons:
1. **Operational Risk:** Self-hosting Kafka requires managing brokers, partition rebalancing, and underlying storage. Without a dedicated infrastructure engineer and zero prior Kafka experience on the team, this poses a severe operational risk.
2. **Implementation Timeline:** Bootstrapping a production-grade Kafka cluster, setting up monitoring, and writing robust consumers cannot be confidently achieved within the two-week constraint.
3. **Budget Violations:** Utilizing a fully managed Kafka offering like Confluent Cloud to bypass operational complexity violates our current budget constraints.
4. **Overkill for Target Scale:** Our 10x scale target (5,000 req/s peak) is well within the capabilities of Redis Streams. The massive throughput capabilities of Kafka (hundreds of thousands of messages per second) are unnecessary for our medium-term growth and do not justify the added complexity.