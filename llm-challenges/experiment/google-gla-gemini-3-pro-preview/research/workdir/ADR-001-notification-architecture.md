# Title
ADR-001: Notification Subsystem Architecture (Redis Streams vs. Apache Kafka)

# Status
Proposed

# Context
The current notification system is handled synchronously within the HTTP request cycle of our Python/Flask monolith. With 85,000 monthly active users and peak traffic of 500 req/s, this architecture is causing severe request timeouts (spikes up to 8s), silent failures when external providers are down, and cascading outages due to connection pool exhaustion. Furthermore, we lack delivery guarantees for critical billing events (e.g., "trial expired").

We need to decouple notifications into an asynchronous subsystem that supports:
- Exponential backoff and retries.
- At-least-once delivery for general notifications, and exactly-once semantics for billing events.
- Foundation for real-time WebSocket push notifications within 6 months.
- Headroom for 10x traffic growth (peak 5,000 req/s).

**Constraints:**
- The engineering team consists of 6 developers (no dedicated infrastructure engineer).
- Budget is modest (managed services like Confluent Cloud are out of scope).
- Solution must deliver value in under 2 weeks.
- The team has no prior Apache Kafka experience.
- Redis is already running in production for session management and rate limiting.

# Decision
We will use **Redis Streams** as the message broker for the asynchronous notification subsystem. 

**Justification:**
Given our team size, tight 2-week deadline, and lack of dedicated infra support, operational simplicity is our highest priority. Redis Streams provides the necessary technical primitives without the severe operational complexity of Kafka:
- **Throughput & Headroom:** Redis easily handles >100,000 operations per second in memory. Our 10x scale target (5,000 req/s) consumes a fraction of a single Redis node's capacity.
- **Consumer Groups:** Redis Streams natively supports consumer groups (`XREADGROUP`), allowing us to horizontally scale notification worker processes and track unacknowledged messages via the Pending Entries List (PEL) for reliable retries.
- **Exactly-Once Semantics:** While Redis Streams inherently provides *at-least-once* delivery, we will achieve end-to-end exactly-once semantics for billing events by utilizing our primary PostgreSQL database. Workers will use deterministic message IDs from Redis as idempotency keys in PostgreSQL transactions when processing billing events.
- **Ordering Guarantees:** Redis Streams appends messages in a strictly ordered, time-based log, guaranteeing chronological processing when needed.
- **Operational Complexity:** Zero new infrastructure is required. We are already operating Redis, meaning we can begin implementing the application logic immediately, easily fitting into the 2-week setup window.

# Consequences

**Pros:**
- **Fast Time-to-Market:** Leverages existing infrastructure, virtually guaranteeing we meet the 2-week deadline.
- **Low Operational Overhead:** No new services to monitor, patch, or maintain. No Zookeeper or JVM tuning required.
- **Cost Effective:** No additional infrastructure or managed service fees.
- **Built-in Retry Mechanics:** `XPENDING` and `XCLAIM` commands give us the exact tools needed to build a dead-letter queue and handle stalled external webhooks.

**Cons:**
- **Memory-Bound Retention:** Unlike Kafka, which writes to disk, Redis Streams stores messages in RAM. We must proactively manage memory by aggressively trimming acknowledged messages (`XTRIM`) and moving dead-letter payloads to PostgreSQL.
- **No Native End-to-End Exactly-Once:** Kafka has native transactional support for exactly-once processing (mostly for stream-to-stream). With Redis, we take on the burden of writing idempotent consumers using Postgres.
- **Less Ecosystem Tooling:** Kafka has a richer ecosystem of off-the-shelf connectors (Kafka Connect) which we will miss if we later want to pipe data directly to analytical data warehouses.

# Alternatives Considered
**Apache Kafka**
Kafka is the industry standard for high-throughput, fault-tolerant message streaming. It offers infinite disk-bound retention, robust consumer groups, and high durability. 

We rejected Kafka primarily due to **operational complexity and constraints**. Deploying, securing, and tuning a highly available Kafka cluster (along with ZooKeeper/KRaft) requires specialized knowledge our 6-person team currently lacks. The learning curve and infrastructure configuration would almost certainly violate our 2-week deadline. While a managed service like Confluent Cloud would solve the operational burden, it violates our modest budget constraint at the scale we require. Finally, Kafka's massive throughput capabilities (millions of msgs/sec) represent extreme over-engineering for our 10x target of 5,000 req/s.