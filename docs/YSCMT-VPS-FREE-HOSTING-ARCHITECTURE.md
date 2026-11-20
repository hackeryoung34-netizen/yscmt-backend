# YSCMT Student Portal — VPS-free hosting architecture

## Decision

The independent Student Portal will not require a customer-managed VPS, Linux server, SSH administration, or an always-on Django process.

Use a managed/serverless design:

- **Cloudflare Workers Static Assets** hosts the React/Vite portal frontend and serves it globally. The portal can be built from the existing `hackeryoung34-netizen/yscmt-react` repository on a dedicated migration branch.
- **Supabase Auth + Postgres + PostgREST RPC** provide login, trusted roles, data storage, and the secured portal operations.
- **GitHub** remains the source of truth and CI system.
- The existing main website stays on its current host. A later, separately approved edge-routing change will send only `/portal/*` to the new portal, leaving all other paths unchanged.

The student browser calls Supabase using the public publishable key and the user's own Supabase access token. The publishable key is designed for client use; no service-role key, database password, Paystack secret, or other privileged credential may be shipped to the browser.

## Why no separate Django server is needed for the portal

The Supabase portal RPCs are designed to derive the current user from `auth.uid()`, check the trusted role stored in `private.user_roles`, and return only permitted records. The client never supplies a user ID to choose whose data is read or changed. The student enrolment RPC only creates `pending` records. The browser can call these RPCs directly through Supabase's authenticated Data API.

The Django Supabase adapter and API endpoints in the backend migration branch are useful reference code and can remain as an optional future API layer. They are not a requirement for hosting the portal and will not be deployed as an always-on server for this architecture.

## Hosting and cost constraints

- Cloudflare Workers Free currently includes up to 100,000 requests per day and a 10 ms CPU-time limit per invocation. If the workload exceeds free limits, requests may be restricted or a paid plan may be needed. Review current limits before launch.
- Supabase Free currently includes 500 MB database storage per project, 50,000 monthly active users, 5 GB egress, and 1 GB file storage. Free projects can pause after one week of inactivity. It is suitable for development and a limited initial trial, not a promise of uninterrupted production availability.
- Vercel Hobby is documented as for non-commercial personal use only. Since YSCMT Enterprise is a business, do not assume a Hobby account is suitable for the production portal. Do not upgrade any account or incur charges without explicit approval.
- No VPS purchase, subscription upgrade, or paid add-on is authorized by this plan.

## Security boundaries

1. RLS remains enabled on all exposed tables. Do not add broad browser table grants to make the UI work.
2. Browser-readable user profile rows remain self-scoped.
3. Business operations are exposed only through narrow, reviewed RPC functions.
4. Admin and instructor access must use `private.user_roles`, never client-editable Auth metadata.
5. Never put Supabase service-role keys, database connection strings, Paystack secret keys, or privileged storage credentials in Vite `VITE_*` variables.
6. Payment verification, Paystack webhooks, exam scoring, certificate issuance, and admin approvals require server-side trusted logic (Supabase Edge Functions or Cloudflare Worker endpoints) and must not be implemented as client-trusted actions.
7. Do not import legacy users, payments, receipts, or create Auth accounts without explicit approval and reconciliation.

## Deployment sequence

1. Keep Hatchable and the current main website untouched.
2. Finish and review the portal UI on a dedicated Git branch.
3. Build a Cloudflare Workers Static Assets preview with a `workers.dev` URL; do not bind the production domain.
4. Complete the Supabase RPC migrations in a controlled test process. Migrations 005–007 are currently staged in GitHub and have not been applied.
5. Use a disposable test account only after explicit approval; verify login, student course catalogue, lesson access, pending enrolment, role isolation, and sign-out.
6. Implement server-side payment, exam, certificate, and admin workflows with idempotency and audit logging.
7. Verify the portal preview end-to-end.
8. Only after a separate explicit approval, configure a narrow Cloudflare route for `yscmtenterprise.ng/portal/*`. Preserve the main website and provide a rollback route.

## Current status

- Supabase schema migrations 001–004 applied and verified.
- Supabase RPC migrations 005–007 staged in GitHub, not applied.
- Django portal auth/course/enrolment endpoints and tests staged in the backend PR; 18 tests passed in GitHub Actions.
- No Cloudflare portal Worker/Static Assets deployment created yet.
- No production DNS, route, main website, or Hatchable changes made.
- No VPS purchased; none is required by this design.
