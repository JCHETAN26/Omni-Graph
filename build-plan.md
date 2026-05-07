# Build Plan: Guardian-Stream AI Infrastructure

## 1. Project Overview
**Guardian-Stream** is an enterprise-grade, distributed AI governance and real-time processing platform for secure Retrieval Augmented Generation (RAG).

### Core Pattern
- **Java Gateway as Semantic Firewall:** A high-performance Spring Boot service intercepts incoming requests, applies rule-based redaction, enforces access policy, and publishes sanitized messages to Kafka.
- **Python Agent as Cognitive Layer:** A LangGraph- and LlamaIndex-based service consumes sanitized events, performs routing and retrieval, and generates grounded responses.
- **Separation of Concerns:** Java handles concurrency, deterministic security checks, and ingress control. Python handles orchestration, retrieval, and agentic reasoning.

## 2. Monorepo Structure
```text
guardian-stream/
├── gateway/          # Java (Spring Boot) - Security Gateway & Kafka Producer
├── agent/            # Python (FastAPI/LangGraph) - RAG & Kafka Consumer
├── dashboard/        # Next.js - Admin observability and metrics UI
├── infra/            # Docker Compose, Kubernetes manifests, KEDA config
├── shared/           # Protobuf/Avro schemas for Kafka message contracts
└── docs/             # Technical specs, runbooks, and architecture diagrams
```

## 3. Dataset and PII Strategy
To keep the system credible and measurable, Guardian-Stream uses a layered PII detection model with realistic evaluation targets.

### Layered PII Pipeline
- **Layer 1: Java Gateway, Rule-Based**
  - High-speed regex and deterministic filters
  - Best for structured identifiers such as emails, SSNs, credit cards, and IP addresses
- **Layer 2: Python Agent, Contextual NLP**
  - Handles harder unstructured entities such as names, organizations, and ambiguous references
  - Candidate tooling: spaCy, Hugging Face NER, or Apache Presidio in the Python runtime

### Reference Datasets
- **Knowledge Base:** SEC EDGAR filings or a localized sample of the Enron Email Corpus for document search and retrieval
- **Structured Audit Metadata:** Snowflake tables for compliance logs, latency metrics, and query tracking
- **Security Test Harness:** JailbreakBench-style prompts to validate sanitization and policy enforcement

## 4. System Components

### Gateway
- Java 21
- Spring Boot
- Kafka producer
- Rule-based sanitization
- RBAC and policy enforcement hooks

### Agent
- Python 3.12
- FastAPI
- LangGraph
- LlamaIndex
- Kafka consumer
- Retrieval and verification workflow

### Storage and Retrieval
- Snowflake for structured audit and compliance data
- Vector database for semantic search
- Recommended MVP choice: ChromaDB for local development
- Scale-up path: Milvus or Pinecone

### Infrastructure
- Docker Compose for local development
- Kubernetes for production deployment
- KEDA for Kafka lag-driven autoscaling

### Dashboard
- Next.js 15
- Admin UI for latency, throughput, blocked requests, and reasoning trace visibility

## 5. Phase-by-Phase Roadmap

### Phase 1: Local Docker Compose MVP
**Goal:** Build a working vertical slice from prompt ingestion to sanitized event processing.

**Flow**
- User prompt
- Java gateway sanitization and validation
- Kafka topic publish
- Python consumer receives event
- Mocked retrieval or model response
- Response returned through webhook or WebSocket

**Focus Areas**
- Docker Compose
- Local Kafka broker
- Minimal Spring Boot gateway
- Minimal Python consumer
- Shared event schema

### Phase 2: Agentic RAG Integration
**Goal:** Replace mocked responses with grounded retrieval and routing.

**Focus Areas**
- LangGraph state machine
- Router node for structured vs unstructured requests
- LlamaIndex ingestion and retrieval
- Local vector database
- Sample corporate and financial documents

### Phase 3: Auditability and Enterprise Storage
**Goal:** Add durable compliance logging and structured analytics.

**Focus Areas**
- Snowflake integration
- Audit log schema
- Query tracking
- Security event reporting

### Phase 4: Kubernetes and Event-Driven Scaling
**Goal:** Deploy the platform with elastic scaling and operational observability.

**Focus Areas**
- Kubernetes manifests
- KEDA `ScaledObject` for Kafka lag
- Health checks and service discovery
- Load testing and failure recovery

## 6. Validation Targets
These are targets to validate through testing, not fixed claims.

- **Gateway latency:** Target P99 pre-processing latency under 250 ms
- **Structured PII redaction:** Target 100% masking for emails, SSNs, and credit card patterns within the defined test set
- **Contextual entity detection:** Target greater than 90% accuracy for names and organizations on evaluation samples
- **Elasticity:** Zero message loss during a simulated 10x ingestion spike while consumers scale based on Kafka lag

## 7. Suggested Initial Schemas

### Kafka Topics
- `sanitized-prompts`
- `system-responses`
- `security-events`

### Snowflake Tables
- `AUDIT_LOGS`
- `SECURITY_POLICIES`
- `REQUEST_METRICS`

## 8. Early Implementation Priorities
Start with the smallest end-to-end slice that proves the architecture.

1. Create the monorepo folders.
2. Define a shared Kafka message contract.
3. Build the Java gateway with regex-based masking for structured PII.
4. Build the Python consumer that reads sanitized events and returns a mocked response.
5. Stand everything up with Docker Compose.
6. Add retrieval, audit logging, and autoscaling after the core loop works reliably.

## 9. Prompt Starters for Coding Assistants

### Gateway
"Create a Spring Boot service under `gateway/` that accepts a JSON payload, masks credit cards and emails with regex, and publishes the sanitized event to the `sanitized-prompts` Kafka topic."

### Agent
"Under `agent/`, create a LangGraph workflow with a router that chooses between vector retrieval and a mock SQL tool based on user intent."

### Infrastructure
"Generate a Docker Compose setup under `infra/` for a local Kafka broker, the Java gateway, and the Python agent."

### Scaling
"Create a KEDA `ScaledObject` manifest under `infra/` that scales the Python consumer deployment based on Kafka consumer lag."
