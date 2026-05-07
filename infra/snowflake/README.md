# Snowflake Assets

This directory holds committed Snowflake setup assets for structured governance data.

## SQL Files
- `001_schema.sql`: Core schema for departments, employees, projects, access grants, policies, audit logs, and request metrics
- `002_seed_data.sql`: Synthetic governance demo data
- `003_example_queries.sql`: Example structured queries for routing and access checks

## Intended Usage
This dataset gives the agent a structured source of truth for:
- employee clearance levels
- project access mappings
- policy lookups
- audit log inspection
- latency and blocked-request analytics
