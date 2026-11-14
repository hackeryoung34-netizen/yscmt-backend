# YSCMT Supabase-backed Django API: authentication implementation plan

Status: implementation in progress; not deployed.

Branch: `migration/independent-portal`

## Goal

Keep Django as the private application API for the independent Student Portal while Supabase Auth becomes the identity provider and Supabase Postgres remains the portal data store. The portal must eventually be served at:

- Student: `https://yscmtenterprise.ng/portal`
- Admin: `https://yscmtenterprise.ng/portal/admin`

This work must not change the live Hatchable portal, the main website, DNS, Vercel production routing, or production data.

## Findings from the current Django project

The existing project is present under `yscmt/`. It currently has:

- `yscmt/yscmt/settings.py` with a hard-coded fallback `SECRET_KEY`.
- `DEBUG=True` as the default.
- SQLite as the implicit database fallback when `DATABASE_URL` is missing.
- DRF's global default permission set to `AllowAny`.
- Django SimpleJWT token endpoints at `/api/token/` and `/api/token/refresh/`.
- A legacy Django user model and account registration serializer.

These are legacy behaviours, not a safe production configuration for the independent portal. Do not simply point the existing Django ORM models at the new Supabase schema: the target schema is deliberately server-only and does not mirror the old Django ORM models.

## Authentication contract

### Identity source

Supabase Auth is the only identity source for the migrated portal. A browser obtains a Supabase access token through Supabase Auth and sends it as:

```http
Authorization: Bearer <supabase-access-token>
```

Do not issue a second Django password or SimpleJWT account for the same portal user. Keep old Django token endpoints disabled for the portal API once the Supabase integration is enabled.

### Trusted role lookup

The role must come from `private.user_roles`, never from browser-supplied metadata, request JSON, local storage, or editable user metadata.

Recommended boundary: a narrow, self-only Postgres RPC rather than exposing the private schema or creating a service-role Edge Function.

Migration `202611140005_secure_portal_identity_rpc.sql` defines `public.portal_get_my_identity()`:

1. The function derives identity exclusively from `auth.uid()`; it accepts no user ID or role argument.
2. It reads the trusted role from `private.user_roles` and safe profile fields from `public.user_profiles`.
3. It uses `SECURITY DEFINER` with an empty `search_path` and fully qualified table/function references.
4. Execution is explicitly revoked from `PUBLIC` and `anon`, and granted only to `authenticated`.
5. The function returns at most the caller's own row. The private schema remains unexposed to the Data API.

This follows the Supabase guidance for narrowly scoped privileged functions: because a public-schema SECURITY DEFINER function is callable by default through inherited PUBLIC privileges, revoke those privileges explicitly and enforce the caller identity inside the function. Do not add a general-purpose role lookup RPC or accept a caller-supplied UUID.

### Django REST Framework integration

A separate portal-only route namespace has now been added:

- `GET /api/portal/v1/me/` returns the caller's verified portal identity.
- `GET /api/portal/v1/courses/` lists active courses and only the caller's own enrollment status.
- `GET /api/portal/v1/courses/<uuid>/` returns active course metadata.
- `GET /api/portal/v1/courses/<uuid>/lessons/` returns lesson content only for the caller's approved/completed enrollment.
- Student catalogue/detail/lesson views explicitly use Supabase authentication and the trusted `student` role.
- The routes are mounted separately from legacy `/api/auth/` and SimpleJWT routes; global DRF defaults and legacy endpoint behaviour remain unchanged.
- The new RPCs are narrowly scoped, derive identity from `auth.uid()`, do not accept a user ID, and cap list results at 100 rows.

The adapter lives in `yscmt/accounts/portal_auth.py`; role permissions are in `portal_permissions.py`; the bounded RPC client is in `portal_rpc.py`; and portal views/routes are in `portal_views.py` and `portal_urls.py`. Mocked tests cover identity validation, upstream failures, bounded/malformed responses, missing tokens, student/instructor role boundaries, and the student course routes. The tests are committed but have not yet been executed.

The adapter contract is:

- Reads only the Bearer token.
- Calls `POST /rest/v1/rpc/portal_get_my_identity` over HTTPS with the Supabase publishable key and caller's Bearer token.
- Uses strict timeouts and bounded response size.
- Maps invalid/expired token responses to DRF `AuthenticationFailed`.
- Creates a lightweight request principal from the verified RPC response (UUID, email, role, display name, phone).
- Does not create or look up a Django `auth.User` row.
- Never logs the access token, publishable key, response headers, or secret material.

Use explicit role permissions:

- `student`: student-owned operations only.
- `instructor`: only explicitly assigned teaching operations.
- `admin`: administrative operations.
- Default deny for every route unless a route explicitly declares a permission.

Do not infer Django superuser status from the portal role. Do not trust `is_staff`, `is_superuser`, `user_metadata`, or a role field sent by the client.

## Required environment variables

Backend-only configuration:

- `SUPABASE_URL`
- `SUPABASE_PUBLISHABLE_KEY`
- No service-role key is required by Django for this identity lookup. The caller's Supabase access token is sent to the RPC with the publishable key.
- `SECRET_KEY` (new random production secret; no fallback)
- `DEBUG` (must default to false)
- `ALLOWED_HOSTS`
- `DATABASE_URL` only if the chosen deployment uses a database connection for Django's own framework tables.

The Supabase service-role/secret key is not needed for this identity lookup. If a later server-side workflow requires it, keep it only in server-side secrets; never add it to Vercel client variables, React source, Git, or a browser bundle.

## Safe API rollout sequence

1. Review migration 005, then apply it to the destination Supabase project only after the user approves the schema change; verify anonymous execution is denied and authenticated callers can retrieve only their own role.
2. Review the isolated DRF adapter and portal identity endpoint; mocked tests are committed but have not been run in CI.
3. After migration 005 is separately approved and applied, test the RPC grants and self-only result using a dedicated disposable Auth account; the test must not create a real user without approval.
4. Review and separately approve migration `202611140006_student_course_read_rpcs.sql`; then test course catalogue/detail and lesson access against disposable test identities. The RPC migration is committed but not applied.
5. Build portal enrolment, lesson progress, exam and admin endpoints in this isolated namespace, with per-route permissions and ownership checks.
6. Set DRF default permission to deny-by-default for the portal API and explicitly mark only health/public endpoints as anonymous.
7. Disable or isolate old Django registration and SimpleJWT endpoints for the new portal path; preserve unrelated legacy routes until their consumers are identified.
8. Add a `/api/health/` endpoint that reveals no environment variables or secrets.
9. Run unit tests, static checks, dependency audit, and Django deployment checks with production-like environment variables.
10. Deploy only to an isolated preview/staging environment after the user approves the destination and cost.
11. Test with a dedicated disposable Supabase Auth account only after explicit approval. Do not create a real user as part of a silent smoke test.
12. Only after preview acceptance, plan the portal path rewrite and production cutover as a separate approval step.

## Required security tests

- No token: `401`.
- Invalid/expired token: `401`.
- Valid student: identity returned with role `student`; cannot call admin endpoints.
- Valid instructor: cannot call admin endpoints.
- Valid admin: can call only the explicitly protected admin endpoints.
- Caller cannot elevate role by editing user metadata, app request body, query string, or local storage.
- Caller cannot request another user's identity by changing a user ID.
- The RPC rejects anonymous callers and cannot return another user's identity, even if a caller changes request parameters.
- Course catalogue/detail/lesson routes use only the student role; instructors and admins are denied until separate workflows are implemented.
- Existing Django endpoints and global DRF `AllowAny` defaults have not been changed.
- All API views deny by default.
- Exam question payloads never include `correct_option`.
- Payment approval, certificate issuance, and enrolment approval remain server-side and auditable.

## Explicitly out of scope until separately approved

- Creating real Auth users or changing existing users.
- Importing Hatchable student, payment, or receipt data.
- Enabling Paystack live processing.
- Deploying the Django backend to production.
- Buying a VPS or upgrading any paid service.
- Changing Vercel production routing, DNS, the main website, or Hatchable.

## Current progress

The Supabase schema and deny-by-default RLS baseline have been applied and verified separately. Migration 005 is committed to this branch but has not been applied to Supabase. The isolated Django identity adapter, role permissions, portal identity endpoint, student course list/detail/lesson endpoints, narrow Supabase RPC migration 006, and mocked tests are committed. Additional tests for upstream failures, oversized/malformed payloads, expired tokens, and instructor/admin separation were added in commit 708735239d4332d65984875adbd527766997f7a9. The mocked tests have not yet been executed in CI. Migration 006 has not been applied to Supabase, so course endpoints are code-complete but not operational against the destination database yet. No source rows, Auth users, payment records, receipt files, or secrets have been imported. Nothing in this work is deployed or live.


## Student self-service enrolment API — implementation added, not deployed

- `POST /api/portal/v1/enrollments/` accepts a `course_id` only.
- The backend validates the UUID and calls the allow-listed `portal_create_enrollment` RPC.
- The database derives the student from `auth.uid()`, verifies the trusted `student` role and active course, and inserts status `pending`.
- The client cannot supply a user ID or approval status. The existing unique constraint prevents a second enrolment for the same student/course.
- Duplicate enrolment is surfaced as HTTP 409; missing/inactive course as HTTP 404; non-student role as HTTP 403.
- Staff approval remains intentionally unimplemented and must be a separate admin-only, audited operation.

Migration `202611140007_student_enrollment_create_rpc.sql` is committed to the migration branch only. It has **not** been applied to Supabase. The new API endpoint is therefore not operational against the destination until that migration is separately reviewed and approved.

A GitHub Actions workflow was added to run the isolated Django portal auth/API test module on pushes and pull requests. Check its run result before treating the code as validated.


## Student learning and assessment RPCs staged (not deployed)

- Migration 008 adds self-scoped lesson completion and course progress summary functions. Completion is idempotent and requires an active lesson plus approved/completed enrolment.
- Migration 009 adds active exam catalogue, timed exam sessions, question delivery without `correct_option`, server-side scoring, and idempotent submission per exam session. It bounds exams to 100 questions and answer payloads to 64 KiB.
- The Student Portal preview UI now includes lesson completion/progress and a timed exam flow. The database RPC migrations remain unapplied; these controls will remain unavailable until the migrations are reviewed and explicitly approved.
- A disposable PostgreSQL integration-test harness and GitHub Actions workflow were added to apply migrations 001–009 and exercise student enrolment, progress, exam timing/scoring, answer-key isolation, and browser table-access restrictions. Its run result must be checked before treating the SQL as validated.

The exam RPC migration 009 also adds a unique per-session attempt link, server-side scoring and answer-key isolation. It remains unapplied pending review; no live exam sessions or attempts have been created.
