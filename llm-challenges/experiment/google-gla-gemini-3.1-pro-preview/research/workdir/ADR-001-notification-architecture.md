# Title
ADR-001: Notification Subsystem Architecture (Kafka vs. Redis Streams)

# Status
Proposed

# Context
Our SaaS project management platform currently handles notifications (emails, webhooks) synchronously within the HTTP request cycle. With growing usage (85,000 MAU, ~500 req/s peak), this architecture is causing request timeouts, silent failures with third-party providers, and cascading connection pool exhaustion. 

We need to decouple notifications into an asynchronous subsystem. Our specific requirements and constraints are:
- **Scale:** Currently ~500 req/s peak; must support 10x growth (~5000 req/s) without re-architecting.
- **Reliability:** At-least-once delivery for general notifications, and strictly **exactly-once semantics** for billing-critical events. Need retry support with exponential backoff.
- **Future-proofing:** Must support the addition of real-time WebSocket push notifications within 2 quarters.
- **Team & Ops:** We are a team of 6 engineers with no dedicated infrastructure engineer and no prior Kafka experience. We have a modest budget (disqualifying premium managed event streaming platforms).
- **Time-to-market:** We must deliver value within 2 weeks.
- **Current Stack:** Python/Flask monolith, PostgreSQL, and Redis (currently used for session and rate limiting).

We are evaluating two primary options for the message broker: Apache Kafka and Redis Streams.

# Decision
We will use **Redis Streams** as the message broker for our new asynchronous notification subsystem.

**Justification:**
Given our strict constraint of a 2-week time-to-value and a small engineering team with no dedicated infrastructure personnel, introducing a complex distributed system like Kafka is an unacceptable operational risk. 

Redis Streams offers the necessary technical properties while drastically minimizing operational complexity:
1. **Operational Complexity & Infrastructure:** We already run Redis in production. Using Redis Streams requires zero new infrastructure provisioning, enabling us to easily meet the 2-week deadline. 
2. **Throughput:** Our 10x scaling target of 5,000 req/s is trivial for Redis Streams, which can comfortably process tens of thousands of messages per second on modest hardware.
3. **Consumer Groups:** Redis Streams natively supports consumer groups (similar to Kafka), allowing us to load-balance email/webhook processing across multiple worker instances and easily attach a new independent consumer group for WebSockets in the future.
4. **Exactly-Once Semantics:** While Redis Streams natively guarantees *at-least-once* delivery, we will achieve the required exactly-once semantics for billing events via **idempotent consumers**. We will use our existing PostgreSQL database to transactionally record processed message IDs alongside business state updates, effectively preventing duplicate processing.
5. **Message Retention:** Since notifications are transient, we do not need the infinite disk-based retention of Kafka. We can cap Redis memory usage using the `MAXLEN` directive on our streams, ensuring operational stability.

# Consequences

**Pros:**
- **Zero New Infrastructure:** Leverages our existing Redis deployment, keeping infrastructure costs and operational burden low.
- **Fast Delivery:** Familiarity with Redis allows the team to hit the 2-week setup and migration deadline.
- **Built-in Consumer Groups:** Allows distinct, parallel processing lines for Webhooks, Emails, and future WebSockets.
- **Low Latency:** In-memory nature provides sub-millisecond write times, completely eliminating the HTTP blocking issue.

**Cons:**
- **Memory Bound:** Message retention is constrained by RAM. We must implement aggressive trimming (`XTRIM` / `MAXLEN`) to prevent out-of-memory crashes.
- **Application-Level Exactly-Once:** We cannot rely on broker-level transactional guarantees (like Kafka's transactional API) and must strictly enforce idempotency in our application logic.
- **Custom Dead-Letter Queues (DLQ):** Redis Streams does not natively route failed messages to a DLQ. We will have to write custom logic utilizing `XPENDING` and `XCLAIM` to handle retries and move poisoned messages to a dedicated DLQ stream.
- **Durability Risks:** Redis persistence (AOF/RDB) is generally strong, but not as fundamentally durable as Kafka's distributed commit log. We must ensure our Redis persistence is configured appropriately for disaster recovery.

# Alternatives Considered

**Apache Kafka**
Kafka is the industry standard for high-throughput, durable event streaming and natively supports exactly-once semantics via its transactional API. 

*Why it was rejected:* 
- **Operational Complexity:** Operating a Kafka cluster (even with KRaft) requires specialized knowledge our team currently lacks. Monitoring, partitioning, and handling broker failures would demand significant engineering cycles away from product work.
- **Time & Budget Constraints:** We cannot afford a fully managed solution like Confluent Cloud for our target scale. Self-hosting and securing Kafka within a 2-week window is entirely unfeasible for a team of 6.
- **Overkill:** Kafka's disk-based, infinitely retained architecture is designed for millions of messages per second and event sourcing. For transient notifications peaking at 5,000 req/s, the operational tax far outweighs the architectural benefits.