-- Guardian-Stream synthetic seed data for structured governance and audit demos.

insert into guardian_stream.departments (department_id, department_name, cost_center, executive_owner) values
    ('D001', 'Platform Security', 'CC-1100', 'Anika Rao'),
    ('D002', 'Finance Engineering', 'CC-2100', 'Marcus Lee'),
    ('D003', 'Applied AI', 'CC-3100', 'Priya Natarajan'),
    ('D004', 'Legal Operations', 'CC-4100', 'Julian Park');

insert into guardian_stream.employees (
    employee_id, first_name, last_name, email, department_id, title, region,
    employment_status, manager_id, hire_date, clearance_level
) values
    ('E1001', 'Ava', 'Patel', 'ava.patel@guardianstream.dev', 'D001', 'Staff Security Engineer', 'US', 'ACTIVE', 'E1005', '2021-02-16', 'L4'),
    ('E1002', 'Noah', 'Kim', 'noah.kim@guardianstream.dev', 'D002', 'Senior Analytics Engineer', 'US', 'ACTIVE', 'E1006', '2022-08-01', 'L3'),
    ('E1003', 'Mia', 'Santos', 'mia.santos@guardianstream.dev', 'D003', 'Applied AI Engineer', 'US', 'ACTIVE', 'E1007', '2023-01-09', 'L3'),
    ('E1004', 'Lucas', 'Meyer', 'lucas.meyer@guardianstream.dev', 'D004', 'Legal Operations Analyst', 'DE', 'ACTIVE', 'E1008', '2021-11-15', 'L2'),
    ('E1005', 'Iris', 'Nguyen', 'iris.nguyen@guardianstream.dev', 'D001', 'Director of Platform Security', 'US', 'ACTIVE', null, '2019-06-10', 'L5'),
    ('E1006', 'Owen', 'Brooks', 'owen.brooks@guardianstream.dev', 'D002', 'Director of Finance Engineering', 'US', 'ACTIVE', null, '2018-09-24', 'L4'),
    ('E1007', 'Sophia', 'Raman', 'sophia.raman@guardianstream.dev', 'D003', 'Director of Applied AI', 'US', 'ACTIVE', null, '2020-04-06', 'L5'),
    ('E1008', 'Ethan', 'Cole', 'ethan.cole@guardianstream.dev', 'D004', 'Associate General Counsel', 'US', 'ACTIVE', null, '2017-05-19', 'L4');

insert into guardian_stream.projects (
    project_id, project_name, project_code, owning_department_id, business_domain, sensitivity_level, status
) values
    ('P2001', 'Atlas Ledger', 'FIN-L3-ATLAS', 'D002', 'financial-reporting', 'L3', 'ACTIVE'),
    ('P2002', 'Helios AI', 'AI-L4-HELIOS', 'D003', 'generative-ai', 'L4', 'ACTIVE'),
    ('P2003', 'Project Redwood', 'SEC-L5-REDWOOD', 'D001', 'threat-detection', 'L5', 'RESTRICTED'),
    ('P2004', 'CaseBridge', 'LEG-L2-CASE', 'D004', 'legal-operations', 'L2', 'ACTIVE');

insert into guardian_stream.employee_project_access (
    access_id, employee_id, project_id, access_role, granted_by, granted_at, expires_at
) values
    ('A3001', 'E1001', 'P2003', 'OWNER', 'E1005', '2025-01-03 09:00:00', null),
    ('A3002', 'E1003', 'P2002', 'EDITOR', 'E1007', '2025-01-04 10:30:00', null),
    ('A3003', 'E1002', 'P2001', 'ANALYST', 'E1006', '2025-01-04 11:00:00', null),
    ('A3004', 'E1004', 'P2004', 'REVIEWER', 'E1008', '2025-01-05 13:00:00', null),
    ('A3005', 'E1005', 'P2003', 'APPROVER', 'E1005', '2025-01-03 09:05:00', null),
    ('A3006', 'E1007', 'P2002', 'APPROVER', 'E1007', '2025-01-04 10:35:00', null),
    ('A3007', 'E1006', 'P2001', 'APPROVER', 'E1006', '2025-01-04 11:05:00', null);

insert into guardian_stream.security_policies (
    policy_id, policy_name, policy_type, enforcement_scope, minimum_clearance,
    blocked_pattern, required_action, severity, is_active, updated_at
) values
    ('SP4001', 'Restrict Redwood Mentions', 'KEYWORD_ACCESS', 'PROMPT', 'L5', 'Project Redwood', 'BLOCK_AND_ALERT', 'CRITICAL', true, '2026-05-01 08:00:00'),
    ('SP4002', 'Mask Email Addresses', 'PII_REDACTION', 'PROMPT', null, '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}', 'MASK', 'HIGH', true, '2026-05-01 08:05:00'),
    ('SP4003', 'Mask SSNs', 'PII_REDACTION', 'PROMPT', null, '\\b\\d{3}-\\d{2}-\\d{4}\\b', 'MASK', 'HIGH', true, '2026-05-01 08:06:00'),
    ('SP4004', 'Finance Data Requires L3', 'PROJECT_CLEARANCE', 'PROJECT', 'L3', 'Atlas Ledger', 'CHECK_CLEARANCE', 'MEDIUM', true, '2026-05-01 08:10:00'),
    ('SP4005', 'AI Project Requires L4', 'PROJECT_CLEARANCE', 'PROJECT', 'L4', 'Helios AI', 'CHECK_CLEARANCE', 'HIGH', true, '2026-05-01 08:11:00');

insert into guardian_stream.audit_logs (
    audit_id, request_id, employee_id, project_id, request_channel, original_prompt,
    sanitized_prompt, policy_outcome, redaction_count, response_status, created_at
) values
    ('L5001', 'REQ-0001', 'E1002', 'P2001', 'web', 'Summarize Atlas Ledger close metrics for q4 and send to alex@example.com', 'Summarize Atlas Ledger close metrics for q4 and send to [REDACTED_EMAIL]', 'ALLOWED_WITH_REDACTION', 1, 'COMPLETED', '2026-05-01 09:00:01'),
    ('L5002', 'REQ-0002', 'E1003', 'P2002', 'api', 'Give me the latest Helios AI platform highlights.', 'Give me the latest Helios AI platform highlights.', 'ALLOWED', 0, 'COMPLETED', '2026-05-01 09:02:14'),
    ('L5003', 'REQ-0003', 'E1004', 'P2003', 'web', 'Tell me about Project Redwood deployment plans.', 'Tell me about Project Redwood deployment plans.', 'BLOCKED_CLEARANCE', 0, 'DENIED', '2026-05-01 09:05:42'),
    ('L5004', 'REQ-0004', 'E1001', 'P2003', 'web', 'Review the latest Project Redwood incident summary for 123-45-6789.', 'Review the latest Project Redwood incident summary for [REDACTED_SSN].', 'ALLOWED_WITH_REDACTION', 1, 'COMPLETED', '2026-05-01 09:07:33');

insert into guardian_stream.request_metrics (
    metric_id, request_id, gateway_latency_ms, agent_latency_ms, total_latency_ms,
    token_usage_input, token_usage_output, blocked_attack, created_at
) values
    ('M6001', 'REQ-0001', 84.50, 412.32, 496.82, 1240, 280, false, '2026-05-01 09:00:01'),
    ('M6002', 'REQ-0002', 62.14, 355.90, 418.04, 980, 245, false, '2026-05-01 09:02:14'),
    ('M6003', 'REQ-0003', 48.11, 0.00, 48.11, 410, 0, true, '2026-05-01 09:05:42'),
    ('M6004', 'REQ-0004', 97.80, 501.23, 599.03, 1505, 320, false, '2026-05-01 09:07:33');
