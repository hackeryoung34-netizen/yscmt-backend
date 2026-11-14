# YSCMT Supabase-backed Django API: authentication implementation plan

Status: design only; not deployed.

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

Recommended boundary:

1. Add a narrowly scoped Supabase Edge Function named `portal-identity`.
2. Require JWT verification on the function.
3. Inside the function, validate the caller with Supabase Auth `getUser(accessToken)`.
4. Use a server-only service-role client inside the function to read exactly one row from `private.user_roles` for that verified Auth user ID, and the matching `public.user_profiles` row.
5. Return only `id`, `email`, safe profile fields, and the trusted role. Never return service credentials or other users' rows.
6. Return `401` for missing/invalid identity and `403` for an authenticated identity without a valid portal role.
7. Keep `verify_jwt=true`; do not disable JWT verification to make the function easier to call.

The function must not accept a requested user ID or role from the caller. It must derive the user ID from the verified token. Its service-role key must exist only in Edge Function secrets.

### Django REST Framework integration

Implement a custom DRF authentication class that:

- Reads only the Bearer token.
- Calls the private `portal-identity` Edge Function over HTTPS with the Supabase publishable key and caller's Bearer token.
- Uses strict timeouts and bounded response size.
- Maps invalid/expired token responses to DRF `AuthenticationFailed`.
- Creates a lightweight request principal from the verified identity response (UUID, email, role, display name).
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
- `SUPABASE_PORTAL_IDENTITY_FUNCTION_URL` (or derive from the validated project URL)
- `SECRET_KEY` (new random production secret; no fallback)
- `DEBUG` (must default to false)
- `ALLOWED_HOSTS`
- `DATABASE_URL` only if the chosen deployment uses a database connection for Django's own framework tables.

The Supabase service-role/secret key belongs only in the Edge Function secret store. It must never be added to Vercel client variables, React source, Git, or a browser bundle.

## Safe API rollout sequence

1. Add isolated Supabase identity function source and tests; do not deploy it yet.
2. Add DRF authentication and role permission classes behind an explicit feature flag, with tests using mocked identity responses.
3. Set DRF default permission to deny-by-default for the portal API and explicitly mark only health/public endpoints as anonymous.
4. Disable or isolate old Django registration and SimpleJWT endpoints for the new portal path; preserve unrelated legacy routes until their consumers are identified.
5. Add a `/api/health/` endpoint that reveals no environment variables or secrets.
6. Run unit tests, static checks, dependency audit, and Django deployment checks with production-like environment variables.
7. Deploy only to an isolated preview/staging environment after the user approves the destination and cost.
8. Test with a dedicated disposable Supabase Auth account only after explicit approval. Do not create a real user as part of a silent smoke test.
9. Only after preview acceptance, plan the portal path rewrite and production cutover as a separate approval step.

## Required security tests

- No token: `401`.
- Invalid/expired token: `401`.
- Valid student: identity returned with role `student`; cannot call admin endpoints.
- Valid instructor: cannot call admin endpoints.
- Valid admin: can call only the explicitly protected admin endpoints.
- Caller cannot elevate role by editing user metadata, app request body, query string, or local storage.
- Caller cannot request another user's identity by changing a user ID.
- Edge Function rejects invalid JWTs and does not return secrets.
- All API views deny by default.
- Exam question payloads never include `correct_option`.
- Payment approval, certificate issuance, and enrolment approval remain server-side and auditable.

## Explicitly out of scope until separately approved

- Creating real Auth users or changing existing users.
- Importing Hatchable student, payment, or receipt data.
- Enabling Paystack live processing.
- Deploying the Edge Function or Django backend to production.
- Buying a VPS or upgrading any paid service.
- Changing Vercel production routing, DNS, the main website, or Hatchable.

## Current progress

The Supabase schema and deny-by-default RLS baseline have been applied and verified separately. No source rows, Auth users, payment records, receipt files, or secrets have been imported. This document records the next implementation boundary; it does not claim the backend integration is implemented or live.
