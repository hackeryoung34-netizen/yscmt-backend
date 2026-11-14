# YSCMT Student Portal — canonical domain path

## User-approved public URLs

- Student Portal: https://yscmtenterprise.ng/portal
- Admin Dashboard: https://yscmtenterprise.ng/portal/admin

The user explicitly chose a path on the existing domain, not a subdomain. Keep the main website at https://yscmtenterprise.ng/ unchanged.

## Verified current hosting facts (2026-11-14)

- Vercel project `yscmtenterprise` exists (project ID `prj_NzOt8fLWtrNztrjZCAfFdfSSwtis`).
- The apex domain `yscmtenterprise.ng` and `www.yscmtenterprise.ng` are verified on that project; apex currently redirects to www with HTTP 308.
- The latest production deployment observed is READY, while the project metadata's latest deployment is a READY preview on branch `feature/community-path-preview`.
- The public website repository is `hackeryoung34-netizen/yscmtenterprise`. Its current `vercel.json` contains cache headers only; it has no `/portal` rewrite yet. Its root page is a static `index.html`.
- The existing React/Vite LMS frontend is `hackeryoung34-netizen/yscmt-react`. Its current Vite config has no `base` setting, and its React BrowserRouter has no `basename`; routes such as `/admin` currently assume the app is mounted at the domain root.
- Supabase project `YSCMT-Student-Portal` now exists in organization `Community`, project ref `wzpkfjnymsxczbkiukrp`, region `eu-west-3` (Paris), PostgreSQL 17.11.0.019, status `ACTIVE_HEALTHY`. It was created after a displayed $0/month quote. This quote is not a promise that all future usage or upgrades remain free; do not enable paid plans or incur charges without approval.
- Supabase public schema currently has no application tables. No Hatchable data has been exported or imported.
- Hatchable project `proj_wtjM5VcpGROw` is confirmed ACTIVE at version 47, with 31 active API routes and 21 database tables. Preserve it for rollback.
- The 21 Hatchable tables are: `users`, `student_profiles`, `courses`, `enrollments`, `course_lessons`, `lesson_progress`, `course_exams`, `exam_questions`, `exam_attempts`, `exam_sessions`, `student_certificates`, `payment_submissions`, `paystack_payments`, `practice_submissions`, `classroom_sessions`, `classroom_attendance`, `classroom_messages`, `classroom_announcements`, `classroom_teacher_replies`, `admin_audit_logs`, and `site_settings`.
- Hatchable identity currently uses platform user IDs stored as text in application rows. Supabase Auth identities use UUIDs. Migration must create an explicit legacy-user-to-Supabase-user mapping; never assume the IDs are interchangeable or silently recreate passwords.
- Existing payment integration includes Paystack secret credentials in Hatchable. Secret values were not read or copied. Reconfigure credentials securely in the new server-side environment; never put them in frontend code or this document.

## Supabase implementation constraints

- Use Supabase Auth for identity only after designing the legacy account migration and admin-role assignment. Do not use user-editable user metadata for authorization.
- Every exposed table must have RLS enabled with table-specific policies. Admin privileges must be assigned through a trusted server-side process or protected app metadata, not a client-editable profile field.
- Supabase's 2026-04-28 breaking-change notice says new public tables are no longer automatically exposed to the Data API by default (enforced on all projects from 2026-10-30). If the portal needs browser Data API access, explicitly configure exposure and grants only after RLS policies are tested. A server-side-only access design may be preferable for sensitive tables.
- Keep service-role/secret keys server-side only. Only publishable keys may be considered for browser use, and only with tested RLS.
- Do not import production/student/payment records until schema, identity mapping, authorization, and a reversible export/backup process have been reviewed.

## Recommended implementation shape (not yet applied)

1. Keep the main website Vercel project and apex domain assignment intact.
2. Build and test the independent portal frontend/backend on a separate preview target first. Do not use the production apex domain for preview.
3. Configure the portal frontend for a path mount: Vite `base: "/portal/"` and React Router `basename="/portal"`, after checking all asset paths, redirects, authentication callbacks, and API URL construction.
4. Design the destination schema from all 21 Hatchable tables, explicitly mapping legacy text user IDs to Supabase Auth UUIDs. Preserve source IDs where safe and map foreign keys consistently.
5. Review role model and RLS policies for students, instructors, and administrators table by table. Payment webhooks and privileged actions must remain server-side.
6. Create schema only after the SQL and policies have been reviewed. Verify RLS and policies with both anonymous and authenticated test cases, then run Supabase security advisors.
7. Build and test data export/import on a disposable or empty destination dataset first. Recheck Hatchable row counts immediately before any eventual import; earlier counts are only historical snapshots.
8. Once the portal has a verified deployment URL, add Vercel rewrites to the existing website project so browser requests under `/portal` are proxied to that portal deployment. Preserve the browser-visible path and explicitly handle both `/portal` and `/portal/:path*`.
9. Keep `/portal/admin` mapped to the portal app's `/admin` route. Confirm SPA fallback for nested routes and that static assets and API requests do not collide with the main website.
10. Test student sign-in, admin authorization, courses, lessons, exams, payments, certificates, classroom, refresh/reload on nested routes, and mobile layout against the preview URL.
11. Only after acceptance tests and explicit user approval, promote routing to production. Keep Hatchable available until the new portal is proven and rollback is tested.

## Safety gates

- No DNS, nameserver, domain-assignment, or apex redirect changes are needed for this path-based design.
- Do not edit production website routing, deploy to production, promote a deployment, import/modify live data, enable a paid Supabase plan, purchase a VPS, or disable/delete Hatchable without explicit approval.
- Before any proxy rewrite is written, verify the actual portal deployment URL and test it independently. Never use a guessed Vercel URL.
- Report what was actually checked and distinguish a plan from an implemented or deployed route.


## No-VPS preview decision (2026-11-14)

The independent portal's first hosting model is Vercel static hosting + Supabase Auth/Postgres/RPC. A private VPS is not required for the initial student portal. The website repository now has a preview-only branch, `migration/student-portal-preview`, with the portal UI under `/portal/` and SPA rewrites in that branch only. Vercel built the preview successfully (READY). Its preview deployment is protected by Vercel SSO.

The production project/domain routing is unchanged. Do not merge the preview branch or add the production `/portal` rewrite until the user explicitly approves cutover. The frontend uses only the Supabase publishable key and caller JWT; no service-role key is present in browser code. Registration is disabled during preview.

See `docs/YSCMT-NO-VPS-PORTAL-ARCHITECTURE.md` for runtime, security, cost, and release gates.
