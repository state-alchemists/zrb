# ADR-001: Message Broker for Notification Subsystem

## Status
Proposed

## Context
The current notification subsystem (emails, webhooks) operates synchronously within the HTTP request cycle of our Python/Flask monolith. This design is causing API timeouts (up to 8s latency during our 500 req/s peak), cascading connection pool exhaustion, and silent data loss when external endpoints fail. 

We must decouple the notification process into an asynchronous system capable of retries, backoffs, and at-least-once delivery. Furthermore, billing-critical events require exactly-once processing semantics. We must also support a 10x traffic increase (~5,000 req/s peak). 

However, we operate under strict constraints: a 6-person engineering team with no dedicated infrastructure engineer, no prior Apache Kafka experience, a tight budget that prohibits enterprise managed services (like Confluent Cloud), and a mandate to deliver business value within a 2-week window. We currently have Redis deployed in production.

## Decision
**We will implement the notification message broker using Redis Streams.**

### Justification
1. **Operational Complexity:** Our team already manages Redis in production. Introducing a complex distributed log system like Apache Kafka from scratch without a dedicated infrastructure engineer represents an unacceptable operational risk and would violate the 2-week delivery constraint.
2. **Throughput:** Redis Streams operates entirely in-memory and easily handles tens of thousands of operations per second. It will trivially accommodate our current peak of 500 req/s and our 10x growth target of 5,000 req/s.
3. **Message Guarantees:** Redis Streams provides Consumer Groups and explicit acknowledgments (`XACK`). This guarantees at-least-once delivery, allowing us to safely retry failed webhook/email deliveries.
4. **Exactly-Once Semantics:** While Kafka supports exactly-once processing natively within its ecosystem, *no* broker can guarantee exactly-once delivery to external webhooks or SMTP servers. To achieve our billing requirements, we will pair Redis Streams' at-least-once delivery with **idempotent consumers**, utilizing our existing PostgreSQL database to track processed idempotency keys in the same transaction that updates business state.

## Consequences

**Pros:**
* **Speed of Delivery:** Leverages existing infrastructure and team knowledge, easily meeting the 2-week setup constraint.
* **Low Overhead:** No new vendor contracts, minimal infrastructure cost increases, and zero new operational paradigms to learn (like ZooKeeper or KRaft).
* **Consumer Groups:** Natively supports horizontal scaling of consumers and handles state tracking of read messages.
* **Low Latency:** In-memory queueing ensures sub-millisecond publish times, completely unblocking the synchronous web requests.

**Cons:**
* **Memory Constraints:** Unlike Kafka, which writes to disk, Redis Streams stores messages in RAM. We must rigorously configure stream length limits (`XTRIM`) to prevent Out-Of-Memory (OOM) crashes.
* **Manual DLQ Management:** Redis does not have a built-in Dead Letter Queue. We will have to write custom logic utilizing `XPENDING` and `XCLAIM` to detect, reassign, and eventually discard persistently failing messages.
* **Durability Risks:** While Redis persists to disk via AOF/RDB, it is primarily an in-memory store. In a hard crash, a small window of un-fsync'd messages could be lost compared to Kafka's robust distributed replication.

## Alternatives Considered
**Apache Kafka**
Kafka is the industry standard for high-throughput, durable event streaming and offers unparalleled message retention and native exactly-once processing capabilities. 

*Why it was rejected:* 
The operational burden is vastly disproportionate to our team size and budget. Self-hosting Kafka requires managing brokers, partition balancing, and consensus (ZooKeeper/KRaft), which would require dedicated DevOps resources we do not have. Managed options like Confluent Cloud exceed our budget. Furthermore, the steep learning curve means we would miss our 2-week deadline, making it the wrong choice for our current maturity stage.