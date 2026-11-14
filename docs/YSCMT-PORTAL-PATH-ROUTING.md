# YSCMT Student Portal — canonical domain path

## User-approved public URLs

- Student Portal: https://yscmtenterprise.ng/portal
- Admin Dashboard: https://yscmtenterprise.ng/portal/admin

The user explicitly chose a path on the existing apex domain, not a subdomain. Keep the main website at https://yscmtenterprise.ng/ unchanged.

## Verified current hosting facts (2026-11-14)

- Vercel project `yscmtenterprise` exists (project ID `prj_NzOt8fLWtrNztrjZCAfFdfSSwtis`).
- The apex domain `yscmtenterprise.ng` and `www.yscmtenterprise.ng` are verified on that project; apex currently redirects to www with HTTP 308.
- The latest production deployment observed is READY, while the project metadata's latest deployment is a READY preview on branch `feature/community-path-preview`.
- The public website repository is `hackeryoung34-netizen/yscmtenterprise`. Its current `vercel.json` contains cache headers only; it has no `/portal` rewrite yet. Its root page is a static `index.html`.
- The existing React/Vite LMS frontend is `hackeryoung34-netizen/yscmt-react`. Its current Vite config has no `base` setting, and its React BrowserRouter has no `basename`; routes such as `/admin` currently assume the app is mounted at the domain root.
- Supabase currently lists no projects. Do not assume a destination database exists.
- Hatchable project `proj_wtjM5VcpGROw` is confirmed ACTIVE at version 47, with the existing student/admin API functions active. Preserve it for rollback.

## Recommended implementation shape (not yet applied)

1. Keep the main website Vercel project and apex domain assignment intact.
2. Build and test the independent portal frontend/backend on a separate preview target first. Do not use the production apex domain for preview.
3. Configure the portal frontend for a path mount: Vite `base: "/portal/"` and React Router `basename="/portal"`, after checking all asset paths, redirects, authentication callbacks, and API URL construction.
4. Once the portal has a verified deployment URL, add Vercel rewrites to the existing website project so browser requests under `/portal` are proxied to that portal deployment. Preserve the browser-visible path, strip the prefix only in the upstream destination as required by the app build, and explicitly handle both `/portal` and `/portal/:path*`.
5. Keep `/portal/admin` mapped to the portal app's `/admin` route. Confirm SPA fallback for nested routes and that static assets and API requests do not collide with the main website.
6. Test student sign-in, admin authorization, courses, lessons, exams, payments, certificates, classroom, refresh/reload on nested routes, and mobile layout against the preview URL.
7. Only after acceptance tests and an explicit user approval, promote the routing change to production. Keep Hatchable available until the new portal is proven and rollback is tested.

## Safety gates

- No DNS, nameserver, domain-assignment, or apex redirect changes are needed for this path-based design.
- Do not edit the production website's `vercel.json`, deploy to production, promote a deployment, import or modify live data, create a potentially billable Supabase project, purchase a VPS, or disable/delete Hatchable without explicit approval.
- Before any proxy rewrite is written, verify the actual portal deployment URL and test it independently. Never use a guessed Vercel URL.
- Report what was actually checked and distinguish a plan from an implemented or deployed route.
