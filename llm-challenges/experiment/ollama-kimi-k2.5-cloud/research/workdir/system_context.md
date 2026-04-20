# System Context: Notifier Subsystem Decision

## Product Overview

We run a SaaS project management platform. Current metrics:
- 85,000 monthly active users
- ~2M tasks created per month
- Peak: ~500 req/s during business hours

## Current Architecture

- **Backend**: Python/Flask monolith (~50k lines)
- **Database**: PostgreSQL (single primary, one read replica)
- **Infrastructure**: 4 web servers behind an nginx load balancer, hosted on AWS
- **Cache**: Redis (used for session storage and rate limiting today)
- **Notifications**: Handled synchronously inside the HTTP request cycle

## The Problem

The notifications module sends emails and webhooks when tasks are updated, assigned, or completed. As usage has grown, this has caused:

1. **Request timeouts**: Sending notifications blocks the response. Average latency 800ms, spikes to 8s during peak hours.
2. **Silent failures**: If an email provider or webhook endpoint is down, the notification is silently dropped. No retry, no dead-letter queue.
3. **Cascading failures**: Two incidents this year where a slow webhook endpoint caused connection pool exhaustion, taking down unrelated features.
4. **No delivery guarantees**: Billing-critical notifications (e.g., "trial expired", "payment failed") must be delivered exactly once, but the current system has no such guarantee.

## Scaling Target

We need to:
- Decouple notifications from the HTTP request cycle (async processing)
- Support retry with exponential backoff
- Guarantee at-least-once delivery for billing events, exactly-once where feasible
- Add real-time WebSocket push notifications within 2 quarters
- Handle 10x traffic growth without re-architecting

## Constraints

- Engineering team: 6 people (3 senior, 3 mid-level), no dedicated infrastructure engineer
- We already run Redis in production (session/rate limiting)
- No Kafka experience on the team today
- Must not require more than 2 weeks of setup/migration work before delivering value
- Budget: modest — cannot afford managed Confluent Cloud at full scale today
- Must maintain exactly-once semantics for billing notifications
