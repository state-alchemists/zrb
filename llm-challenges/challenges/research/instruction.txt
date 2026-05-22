Read `system_context.md`. It describes a real production system and a specific architectural problem we need to solve.

Write an Architecture Decision Record (ADR) evaluating two options for the notification subsystem:
1. **Apache Kafka**
2. **Redis Streams**

Your ADR must follow this exact structure:
- **Title**
- **Status** (e.g. "Proposed")
- **Context** — the problem and constraints
- **Decision** — which option you choose and a clear justification
- **Consequences** — pros AND cons of your decision
- **Alternatives Considered** — why you rejected the other option

Make a definitive recommendation. Use specific technical properties (throughput, ordering guarantees, message retention, consumer groups, exactly-once semantics, operational complexity) to justify your choice given the team size and constraints described.

Save as `ADR-001-notification-architecture.md`.
