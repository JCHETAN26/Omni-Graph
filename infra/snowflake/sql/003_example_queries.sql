-- Example queries for structured routing and policy checks.

-- Which employees can access a given project?
select
    e.employee_id,
    e.first_name,
    e.last_name,
    e.clearance_level,
    a.access_role,
    p.project_name
from guardian_stream.employee_project_access a
join guardian_stream.employees e on e.employee_id = a.employee_id
join guardian_stream.projects p on p.project_id = a.project_id
where p.project_name = 'Helios AI';

-- Which prompts were blocked because of insufficient clearance?
select
    request_id,
    employee_id,
    project_id,
    policy_outcome,
    created_at
from guardian_stream.audit_logs
where policy_outcome = 'BLOCKED_CLEARANCE'
order by created_at desc;

-- Which active policies are enforced at prompt time?
select
    policy_name,
    policy_type,
    minimum_clearance,
    required_action,
    severity
from guardian_stream.security_policies
where enforcement_scope = 'PROMPT'
  and is_active = true
order by severity desc;
