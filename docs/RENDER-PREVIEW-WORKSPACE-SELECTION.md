# Render preview workspace selection — YSCMT Student Portal

Date: 2026-11-23

The owner selected option 2: **My Workspace — hackeryoung34**.

Verified Render account link:
- link name: `hackeryoung34`
- workspace ID: `tea-d7ofvkjeo5us73e6tdgg`
- services currently listed in this workspace: none
- workspace listing confirms the selected workspace is accessible.

## Deployment gate

Do not create or deploy the portal web service yet. The current Django portal endpoints still authenticate against Supabase and invoke Supabase RPCs. The selected Neon database is PostgreSQL, but it does not provide Supabase Auth, `auth.users`, `auth.uid()`, or Supabase REST RPC endpoints. Deploying the current branch without first replacing those dependencies would produce a non-functional preview and could encourage unsafe configuration workarounds.

Next actions:
1. Implement a portal-native Django identity/authentication path and ORM-backed data access, isolated from legacy Django user models.
2. Review and add PostgreSQL migrations for the portal-owned models.
3. Run Django system checks, migrations and security tests against a disposable PostgreSQL database.
4. Only after these pass, create the Render web service in workspace `tea-d7ofvkjeo5us73e6tdgg`, Free plan, Frankfurt region, connected to branch `migration/neon-django-preview`.
5. Set secrets only through Render's environment-variable store; never commit or print them.
6. Configure Neon only after the Django schema/migration review. Use synthetic data for preview.
7. Keep Hatchable active and all production domains/routes unchanged.

No Render service, environment variable, database migration, source-data import, production deployment, DNS change, or cutover was performed by this workspace-selection step.
