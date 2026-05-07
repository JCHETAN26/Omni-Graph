# Guardian-Stream

Guardian-Stream is a monorepo for a security-first AI governance platform built around a Java ingress gateway, a Python agent service, and an observability dashboard.

## Repository Layout
- `gateway/`: Spring Boot security gateway and Kafka producer
- `agent/`: Python agent service, Kafka consumer, and RAG workflow
- `dashboard/`: Next.js admin UI for observability
- `infra/`: Local and production infrastructure definitions
- `shared/`: Cross-service contracts and schemas
- `docs/`: Architecture notes and implementation docs

## MVP Goal
The first milestone is a local vertical slice:

1. Accept a prompt at the Java gateway.
2. Sanitize and validate the payload.
3. Publish a message to Kafka.
4. Consume it in the Python agent.
5. Return a mocked, traceable response.

## Getting Started
Use [build-plan.md](/Users/chetan/Guardian-Stream/build-plan.md:1) as the project blueprint. The repo scaffold is intentionally minimal so we can implement Phase 1 without rework.
