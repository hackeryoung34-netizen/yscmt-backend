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

Recommended boundary: a narrow, self-only Postgres RPC rather than exposing the private schema or creating a service-role Edge Function.

Migration `202611140005_secure_portal_identity_rpc.sql` defines `public.portal_get_my_identity()`:

1. The function derives identity exclusively from `auth.uid()`; it accepts no user ID or role argument.
2. It reads the trusted role from `private.user_roles` and safe profile fields from `public.user_profiles`.
3. It uses `SECURITY DEFINER` with an empty `search_path` and fully qualified table/function references.
4. Execution is explicitly revoked from `PUBLIC` and `anon`, and granted only to `authenticated`.
5. The function returns at most the caller's own row. The private schema remains unexposed to the Data API.

This follows the Supabase guidance for narrowly scoped privileged functions: because a public-schema SECURITY DEFINER function is callable by default through inherited PUBLIC privileges, revoke those privileges explicitly and enforce the caller identity inside the function. Do not add a general-purpose role lookup RPC or accept a caller-supplied UUID.

### Django REST Framework integration

Implement a custom DRF authentication class that:

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
2. Add DRF authentication that calls `POST /rest/v1/rpc/portal_get_my_identity` using the caller's Bearer token and the publishable key; do not use a service-role key.
3. Add tests for the RPC and DRF identity adapter before enabling it.
4. Set DRF default permission to deny-by-default for the portal API and explicitly mark only health/public endpoints as anonymous.
5. Disable or isolate old Django registration and SimpleJWT endpoints for the new portal path; preserve unrelated legacy routes until their consumers are identified.
6. Add a `/api/health/` endpoint that reveals no environment variables or secrets.
7. Run unit tests, static checks, dependency audit, and Django deployment checks with production-like environment variables.
8. Deploy only to an isolated preview/staging environment after the user approves the destination and cost.
9. Test with a dedicated disposable Supabase Auth account only after explicit approval. Do not create a real user as part of a silent smoke test.
10. Only after preview acceptance, plan the portal path rewrite and production cutover as a separate approval step.

## Required security tests

- No token: `401`.
- Invalid/expired token: `401`.
- Valid student: identity returned with role `student`; cannot call admin endpoints.
- Valid instructor: cannot call admin endpoints.
- Valid admin: can call only the explicitly protected admin endpoints.
- Caller cannot elevate role by editing user metadata, app request body, query string, or local storage.
- Caller cannot request another user's identity by changing a user ID.
- The RPC rejects anonymous callers and cannot return another user's identity, even if a caller changes request parameters.
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

The Supabase schema and deny-by-default RLS baseline have been applied and verified separately. No source rows, Auth users, payment records, receipt files, or secrets have been imported. This document records the next implementation boundary; it does not claim the backend integration is implemented or live.
