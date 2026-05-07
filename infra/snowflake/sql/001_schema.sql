-- Guardian-Stream Snowflake schema for synthetic governance and audit data.

create or replace schema guardian_stream;

create or replace table guardian_stream.departments (
    department_id string not null,
    department_name string not null,
    cost_center string not null,
    executive_owner string not null,
    primary key (department_id)
);

create or replace table guardian_stream.employees (
    employee_id string not null,
    first_name string not null,
    last_name string not null,
    email string not null,
    department_id string not null,
    title string not null,
    region string not null,
    employment_status string not null,
    manager_id string,
    hire_date date not null,
    clearance_level string not null,
    primary key (employee_id)
);

create or replace table guardian_stream.projects (
    project_id string not null,
    project_name string not null,
    project_code string not null,
    owning_department_id string not null,
    business_domain string not null,
    sensitivity_level string not null,
    status string not null,
    primary key (project_id)
);

create or replace table guardian_stream.employee_project_access (
    access_id string not null,
    employee_id string not null,
    project_id string not null,
    access_role string not null,
    granted_by string not null,
    granted_at timestamp_ntz not null,
    expires_at timestamp_ntz,
    primary key (access_id)
);

create or replace table guardian_stream.security_policies (
    policy_id string not null,
    policy_name string not null,
    policy_type string not null,
    enforcement_scope string not null,
    minimum_clearance string,
    blocked_pattern string,
    required_action string not null,
    severity string not null,
    is_active boolean not null,
    updated_at timestamp_ntz not null,
    primary key (policy_id)
);

create or replace table guardian_stream.audit_logs (
    audit_id string not null,
    request_id string not null,
    employee_id string not null,
    project_id string,
    request_channel string not null,
    original_prompt string not null,
    sanitized_prompt string not null,
    policy_outcome string not null,
    redaction_count number(10, 0) not null,
    response_status string not null,
    created_at timestamp_ntz not null,
    primary key (audit_id)
);

create or replace table guardian_stream.request_metrics (
    metric_id string not null,
    request_id string not null,
    gateway_latency_ms number(10, 2) not null,
    agent_latency_ms number(10, 2) not null,
    total_latency_ms number(10, 2) not null,
    token_usage_input number(10, 0),
    token_usage_output number(10, 0),
    blocked_attack boolean not null,
    created_at timestamp_ntz not null,
    primary key (metric_id)
);
