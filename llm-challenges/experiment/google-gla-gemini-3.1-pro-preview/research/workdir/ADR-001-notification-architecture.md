# Title
ADR-001: Notification Subsystem Architecture - Redis Streams vs. Apache Kafka

# Status
Proposed

# Context
Our SaaS project management platform currently handles notifications (emails, webhooks) synchronously within the HTTP request cycle of our Python/Flask monolith. With 85,000 MAU and ~2M tasks/month, peak traffic reaches 500 req/s. The synchronous approach is causing significant issues:
- **Request timeouts**: Notification latency averages 800ms, spiking to 8s during peak hours.
- **Silent failures**: Webhook/email provider outages result in dropped notifications without retries.
- **Cascading failures**: Slow external endpoints have caused connection pool exhaustion.
- **Delivery guarantees**: Billing-critical notifications lack delivery guarantees.

We need an asynchronous, decoupled architecture capable of supporting retries, dead-letter queues, real-time WebSocket pushes, and a 10x traffic growth (to ~5,000 req/s). Critically, billing events require exactly-once semantics.

Our constraints heavily dictate our options: we have a 6-person engineering team with no dedicated infrastructure engineer, modest budget, no prior Apache Kafka experience, a strict 2-week timeline to deliver value, and we already run Redis in production.

# Decision
We will use **Redis Streams** as the backbone for the new notification subsystem. 

**Justification:**
Given our team size, lack of infrastructure engineers, and tight 2-week deadline, operational complexity is the primary deciding factor. Redis is already running in our stack, and the team is familiar with it. Redis Streams provides the necessary messaging primitives—specifically **Consumer Groups**—to enable decoupled processing, message acknowledgment, and retries for failed deliveries. 

While Redis Streams natively provides *at-least-once* delivery guarantees rather than Kafka's transactional semantics, we will achieve the required **exactly-once semantics** for billing notifications via consumer-side idempotency. Consumers will generate a unique idempotency key for each message and verify/store it in our existing PostgreSQL database within a transaction before triggering the external side effect (email/webhook). 

At our target scale of 5,000 req/s, Redis Streams easily handles the throughput in-memory, providing sub-millisecond write latency without the need to manage distributed consensus or complex partition clustering.

# Consequences
**Pros:**
- **Zero New Infrastructure Overhead**: Leverages our existing Redis expertise and infrastructure, fitting well within the 6-engineer team constraints.
- **Speed of Delivery**: The API is simple, and integrating a Python Redis Streams consumer loop can comfortably be completed within the 2-week constraint.
- **Throughput & Performance**: Easily handles our current 500 req/s and our 10x target of 5,000 req/s.
- **Consumer Groups**: Built-in support for consumer groups allows us to scale out worker processes, track pending messages, and implement dead-letter queues for robust error handling.

**Cons:**
- **Memory-Bound Message Retention**: Unlike disk-based message brokers, Redis Streams stores data in memory. We will need to actively trim the streams (e.g., `MAXLEN`) to prevent OOM errors, meaning historical message retention is short-term only.
- **No Native Exactly-Once Processing**: Redis does not offer transactional consume-produce loops. We must build and strictly maintain application-level idempotency using PostgreSQL to satisfy billing requirements.
- **Durability Risks**: Depending on our Redis persistence configuration (RDB/AOF), a catastrophic node failure could result in minor data loss of un-fsync'd messages. 

# Alternatives Considered
**Apache Kafka**
Kafka is the industry standard for distributed event streaming. It offers unmatched throughput, disk-backed infinite message retention, and exactly-once processing capabilities via its transactional API. 

*Why it was rejected:* 
Kafka entirely violates our operational constraints. The setup, maintenance, and tuning of a Kafka cluster (along with ZooKeeper or KRaft controllers) requires dedicated infrastructure expertise that our team lacks. A managed solution like Confluent Cloud breaks our modest budget constraint. The learning curve for Kafka concepts (partitions, offsets, rebalancing, transactional producers) is steep and would absolutely prevent us from delivering value within the required 2-week window. For a target of 5,000 req/s, Kafka is severe overkill that introduces unacceptable operational risk.