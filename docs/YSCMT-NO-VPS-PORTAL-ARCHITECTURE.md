# YSCMT Student Portal — No-VPS Hosting Architecture

**Status:** implementation/preview in progress. No production cutover has occurred.

## Decision

The first independent Student Portal release will not require a privately purchased VPS. Use the existing Vercel website project for static portal delivery and the existing Supabase project for authentication, PostgreSQL, and narrowly scoped database RPCs.

## Runtime layout

- **Main website:** remains on the existing Vercel project and production branch.
- **Student Portal UI:** static files under `/portal/` in the website repository, built as a separate Git branch preview first.
- **Domain path:** the intended production URL remains `https://yscmtenterprise.ng/portal`. A production rewrite is not enabled until preview acceptance and explicit approval.
- **Authentication:** Supabase Auth. The browser uses only the public publishable key.
- **Data access:** browser calls approved Postgres RPCs with the student's own Supabase access token. Each RPC derives the caller from `auth.uid()`, checks the trusted private role registry, and returns only allowed fields.
- **Database:** Supabase Postgres. No student business tables are directly granted to anon/authenticated browser roles.
- **Secrets:** no service-role key or database password is included in frontend code. Any server-only secret remains in the provider's secret store.

## Why this removes the VPS requirement

The portal is a static frontend and the data/authentication services are managed by Supabase. The first release therefore has no always-on Django server to maintain. The existing Django API adapter in `yscmt-backend` is retained as optional/legacy server-side code, but it is not a requirement for the student portal's initial hosting model.

## Free-tier and cost controls

- No VPS has been purchased or provisioned.
- The existing Supabase Free project is used for initial development.
- Vercel is using the already-existing website project for a preview deployment.
- Free plans have usage quotas and may change; do not assume unlimited or permanently free usage.
- No paid upgrade, paid add-on, domain purchase, or compute purchase is authorized.
- If the project reaches a free-tier limit, pause and ask before spending money.

## Security and migration gates

1. Keep RLS enabled on all application tables.
2. Keep business tables inaccessible directly from browser roles.
3. Expose only reviewed RPC functions; use `auth.uid()` and trusted private roles, never user-editable metadata.
4. Keep student registration disabled in the preview until the Auth trigger is tested with an approved disposable account.
5. Keep the admin route closed unless the private role RPC confirms `admin`.
6. Keep exam answer keys, Paystack secrets, payment verification, and certificate issuance server-side.
7. Do not import real users, passwords, payment records, receipts, or certificates until mapping and reconciliation are approved.
8. Keep Hatchable online for rollback until full parity and acceptance testing.
9. Do not change the production domain rewrite or main website until explicit approval.

## Current implementation status

- The Supabase base schema and private role registry migrations 001–004 are applied and verified.
- RPC migrations 005–007 (identity, course reads, pending enrolment) are committed to GitHub but not applied to Supabase.
- The website repository contains a Student Portal preview branch with student sign-in UI, course/lesson/enrolment client calls, and a role-gated admin preview route.
- The preview build is READY on Vercel, but it remains protected by Vercel SSO and is not a public production page.
- Registration is disabled in the preview.
- Existing Hatchable data and Auth users have not been imported.
- Production URL routing and the main website are unchanged.

## Next steps

1. Review and explicitly approve the RPC migrations for the Supabase destination.
2. Test Auth profile creation using a disposable account only after approval.
3. Complete the student progress, exams, payments, certificates, and admin APIs with the same fail-closed authorization model.
4. Verify preview UI against the deployed RPCs and test role separation.
5. Complete source-to-target data reconciliation and private receipt storage design.
6. Obtain explicit approval before production path routing or any live data import.
