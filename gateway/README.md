# Gateway

The `gateway/` service will host the Java 21 Spring Boot ingress layer.

## Responsibilities
- Accept incoming prompt requests
- Apply deterministic PII masking for structured identifiers
- Enforce policy hooks and request validation
- Publish sanitized events to Kafka

## Planned MVP Components
- REST controller for prompt ingestion
- Sanitization service for regex-based masking
- Kafka producer
- Health endpoint
