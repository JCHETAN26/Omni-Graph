# Architecture Notes

## Phase 1 Vertical Slice
- Client sends prompt to the Java gateway
- Gateway sanitizes structured PII and publishes to Kafka
- Python agent consumes the event and returns a mocked response
- The end-to-end flow is observable through logs and shared request IDs

## Design Principles
- Keep the ingress path deterministic and fast
- Push contextual reasoning into the Python runtime
- Define contracts early so services can evolve independently
- Prove the local workflow before introducing cloud dependencies
