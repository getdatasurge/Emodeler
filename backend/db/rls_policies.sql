-- Row-Level Security policies (spec Ch 9.3 / build plan §2.2).
--
-- Postgres/Supabase ONLY — not applied to the SQLite beta. The ORM ships org_id
-- on every user-data table now, so going multi-tenant (Phase 4) is just applying
-- these policies + removing the permissive single-tenant grant; no schema change.
--
-- Apply after the Supabase project exists and `public.users` is populated
-- (users.id = auth.users.id, users.org_id = the org).

-- Caller's org, resolved from the users table.
create or replace function public.app_org_id() returns uuid
  language sql stable as $$
    select org_id from public.users where id = auth.uid()
  $$;

alter table projects         enable row level security;
alter table faces            enable row level security;
alter table scenarios        enable row level security;
alter table calculation_jobs enable row level security;
alter table scenario_results enable row level security;
alter table audit_log        enable row level security;

-- Projects: full org isolation.
create policy projects_org_rw on projects
  using (org_id = public.app_org_id())
  with check (org_id = public.app_org_id());

-- Child tables inherit isolation by joining to their project.
create policy faces_org_rw on faces
  using (exists (select 1 from projects p
                 where p.id = faces.project_id and p.org_id = public.app_org_id()));

create policy scenarios_org_rw on scenarios
  using (exists (select 1 from projects p
                 where p.id = scenarios.project_id and p.org_id = public.app_org_id()));

create policy jobs_org_rw on calculation_jobs
  using (exists (select 1 from projects p
                 where p.id = calculation_jobs.project_id and p.org_id = public.app_org_id()));

create policy results_org_rw on scenario_results
  using (exists (select 1 from calculation_jobs j
                 join projects p on p.id = j.project_id
                 where j.id = scenario_results.job_id and p.org_id = public.app_org_id()));

-- Audit log: org-scoped read; writes happen via the service role (bypasses RLS).
create policy audit_org_read on audit_log for select
  using (org_id = public.app_org_id());

-- NOTE: the EnergyPlus worker connects with the Supabase service-role key, which
-- bypasses RLS — it needs cross-user reads to run queued jobs.
