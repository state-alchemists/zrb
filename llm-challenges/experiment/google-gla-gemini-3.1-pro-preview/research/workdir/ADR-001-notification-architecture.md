# ADR-001: Notification Subsystem Architecture

## Status
Proposed

## Context
Our SaaS platform's current synchronous notification system is causing HTTP request timeouts (averaging 800ms, spiking to 8s), cascading failures (connection pool exhaustion), and silent data loss. We must decouple notifications from the HTTP request cycle into an asynchronous architecture. 

Our scaling targets demand handling up to 5,000 req/s (10x our current 500 req/s peak), supporting retries/dead-letter queues, and accommodating a future WebSocket real-time push layer. Furthermore, billing-critical events require exactly-once semantics (or reliable at-least-once with idempotency).

We evaluated Apache Kafka and Redis Streams under the following strict constraints:
- A 6-person engineering team with no dedicated infrastructure engineer.
- No existing team experience with Apache Kafka.
- Redis is already running in production for caching/rate-limiting.
- A tight deadline to deliver value (under 2 weeks).
- A modest infrastructure budget precluding expensive managed solutions like Confluent Cloud.

## Decision
We will use **Redis Streams** as the foundational message broker for the notification subsystem.

To satisfy the strict "exactly-once" delivery requirement for billing notifications while using Redis Streams (which natively provides "at-least-once" guarantees), we will implement **idempotent consumers**. The consumer workers will process messages and record the processing state (using unique idempotency keys/message IDs) in our existing PostgreSQL database within the same database transaction that updates the system state.

**Justification:**
1. **Time-to-Value & Operational Complexity:** Redis Streams requires zero new infrastructure provisioning since Redis is already in our stack. This guarantees we can meet the 2-week implementation constraint. Self-hosting Kafka requires managing Zookeeper/KRaft, JVM tuning, and partition management—a massive operational burden for a team of 6 lacking infrastructure specialists.
2. **Performance:** Redis Streams handles millions of messages per second in memory. Our 10x target of 5,000 req/s is trivial for Redis. 
3. **Consumer Groups:** Redis Streams natively supports Consumer Groups (`XREADGROUP`), which allows us to load-balance notifications across multiple Python/Flask worker instances and handles unacknowledged message tracking (Pending Entries List) for our required retry/exponential backoff mechanics.
4. **Budget:** Leveraging our existing Redis deployment completely avoids the steep base costs associated with managed message queues or the EC2/EBS footprint of a self-hosted Kafka cluster.

## Consequences

### Pros
- **Immediate Start:** No new infrastructure required; the team can start writing producer/consumer code immediately.
- **Low Operational Overhead:** No new distributed systems (Kafka brokers, Zookeeper) to monitor, patch, or tune.
- **Feature Complete:** Native support for consumer groups and pending entries enables the necessary load balancing, retries, and dead-letter queues.
- **Easy WebSockets:** Redis Streams/PubSub meshes easily with future WebSocket broadcasting for our upcoming real-time push requirements.

### Cons
- **App-Level Idempotency Required:** Because Redis Streams provides at-least-once delivery, the engineering team must strictly enforce idempotency in the consumer application layer to safely handle potential duplicate billing events.
- **Memory Bound:** Message retention is limited by RAM. We must rigorously enforce `MAXLEN` limits on our streams to prevent Redis from running out of memory and crashing our rate-limiting/session caches.
- **Durability Risks:** While Redis has AOF/RDB backups, it is primarily an in-memory store. In the event of a catastrophic crash between disk syncs, a small window of in-flight messages could be lost compared to Kafka's robust disk-first log appends. 

## Alternatives Considered

**Apache Kafka:**
Kafka is the industry standard for event streaming. It natively provides robust persistence, massive disk-based message retention, highly scalable partitioning, and true exactly-once semantics (via Kafka Transactions). 

*Why it was rejected:* 
We rejected Kafka due to its sheer operational complexity and our lack of domain expertise. For a team of 6 developers without a dedicated DevOps engineer, self-hosting and maintaining Kafka is a severe operational risk that would drastically extend the delivery timeline beyond the 2-week constraint. Furthermore, managed Kafka (like Confluent Cloud) violates our modest budget constraint. While Kafka's exactly-once semantics are desirable, simulating them via idempotent consumers with PostgreSQL + Redis Streams is significantly cheaper, faster to ship, and safer for our specific team composition.