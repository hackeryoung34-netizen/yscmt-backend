# YSCMT Student Portal — Neon/Django migration plan

**Status:** isolated preview migration branch; planning and implementation work only.  
**Base:** `migration/independent-portal`  
**Target branch:** `migration/neon-django-preview`  
**Production status:** unchanged. Hatchable remains active. No production routing, DNS changes, live-data import, or cutover is authorized by this work.

## 1. Target architecture

- **Frontend:** retain the existing Vercel website and its current production deployment. Portal UI is previewed separately before any production routing.
- **API:** Django REST Framework served as a Render preview web service. Use the Render workspace explicitly selected by the owner; do not create a service until that workspace is confirmed.
- **Database:** dedicated Neon project `YSCMT-Student-Portal`, project ID `rough-paper-00162484`, Frankfurt region, branch `development`, database `yscmt_student_portal`.
- **Authentication:** Django-native portal identity and signed JWT access/refresh tokens. Do not depend on Supabase Auth, Supabase REST, Supabase RPC, or Supabase-specific SQL.
- **Database access:** Django ORM using the Neon PostgreSQL connection string supplied only through server-side environment variables.
- **Secrets:** Django secret key, database URL, JWT signing configuration, and payment-provider secrets remain in the hosting provider's secret store. Never put them in frontend code, Git, logs, or chat.
- **Storage:** receipt and private upload storage must use a private object store with short-lived signed access; do not rely on Render's ephemeral filesystem.

## 2. Important compatibility finding

The current independent portal API in `yscmt/accounts/portal_views.py` still calls `SupabasePortalAuthentication` and `call_portal_rpc`. The SQL under `supabase/migrations/` depends on Supabase-specific objects such as `auth.users`, `auth.uid()`, Supabase roles, and Supabase RPC execution grants. Those SQL files must not be applied to Neon as-is.

The existing Django project also contains legacy models tied to Django's built-in `auth.User`. Do not casually replace `AUTH_USER_MODEL` on an established project. The portal identity implementation must be designed so it does not break legacy apps or their migrations.

## 3. Implementation sequence

1. Inventory the current Django models, migrations, portal endpoints, frontend API contract, and source Hatchable field mapping.
2. Define a portal-native identity model and JWT authentication adapter, isolated from legacy Django authentication. Use trusted database role fields; never accept role claims from user-editable profile data.
3. Implement Django ORM models for portal courses, lessons, enrolments, lesson progress, exams, exam sessions/attempts, certificates, payment records, practice submissions, classrooms, attendance, messages, announcements, and audit events.
4. Implement DRF serializers, views, and permissions. Derive the student identity from the verified JWT; never accept a user ID, payment state, exam score, certificate status, or staff role from the request body.
5. Preserve the current API route contract where safe: `/api/portal/v1/me/`, `courses/`, course detail, lessons, and enrolments. Extend routes only after frontend contract review.
6. Generate Django migrations and apply them only to the new empty Neon development database after reviewing the migration plan.
7. Add automated tests for unauthenticated access, student isolation, instructor/admin permissions, enrolment gating, lesson progress ownership, exam answer-key secrecy, timed exam expiry/idempotency, and payment verification boundaries.
8. Run migrations and tests against a disposable PostgreSQL database in CI before connecting the preview service to Neon.
9. Deploy a non-production Render preview only after the owner chooses the Render workspace. Use a free plan unless the owner separately approves a paid plan. No service should be created in an ambiguous workspace.
10. Integrate the Vercel preview with the preview API, verify CORS/CSRF/host settings, and test end-to-end using synthetic accounts and data only.
11. Reconcile source table counts and foreign-key mappings in a separate rehearsal. Do not import real student, payment, password, receipt, or certificate data until mapping, backup, and explicit approval are complete.
12. Obtain separate explicit approval before production routing or cutover. Keep Hatchable active and available for rollback until post-cutover acceptance is complete.

## 4. Data migration safeguards

- Preserve source IDs in explicit legacy mapping columns/tables; do not assume source IDs match new Django IDs.
- Do not copy password hashes unless their format and security properties are proven compatible. Prefer a controlled reset/invitation flow.
- Import parent records before dependent records and validate foreign keys.
- Reconcile source/target counts and payment/certificate references; record exceptions instead of silently dropping rows.
- Use synthetic test data for all early migration and API tests.
- Never change source Hatchable records during rehearsal.

## 5. Hosting and cost safeguards

- Neon project is on the Free plan and currently empty. Keep all work within the free plan; pause if an operation requires a paid upgrade or unexpected charge.
- Render preview service, if created, must be in the workspace selected by the owner and on the Free plan. Render free services may sleep and are not a production uptime guarantee.
- Do not use an expiring free Render Postgres database for student records; Neon is the selected database.
- No paid VPS, add-on, storage, or plan upgrade is authorized.
- No production DNS, Vercel production settings, or Hatchable settings are to be changed in this phase.

## 6. Current verified state

- Neon project `YSCMT-Student-Portal` exists in the Yusufa organization on the Free plan.
- Neon development branch and endpoint are ready; the database has no application tables yet.
- Hatchable project `proj_wtjM5VcpGROw` remains active.
- GitHub branch `migration/neon-django-preview` was created from `migration/independent-portal`.
- No Django migration has been applied to Neon; no source records have been exported/imported.
- No Render service has been created because two Render workspaces are connected and the owner must choose the intended workspace.
- No production deployment, routing, DNS change, or cutover has occurred.
