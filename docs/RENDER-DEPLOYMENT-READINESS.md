# YSCMT Backend Deployment Readiness Review

Review date: 2026-11-27
Reviewed branch: `render-v2-setup`
Reviewed commit: `65072749d10eccc63a4a6ea1e9815b7522dc0164`

## Verified positive findings

- GitHub Actions workflow `Django backend checks` completed successfully for the reviewed commit on 2026-11-21.
- The successful run completed dependency installation, `python manage.py check`, and `python manage.py test --verbosity 2`.
- Production settings on this branch require `SECRET_KEY` and `DATABASE_URL`; they do not fall back to the hard-coded secret or SQLite in production.
- The project has a root health response at `/`.
- The admin dashboard API uses DRF `IsAdminUser`; the account profile and payment creation endpoints inspected require authentication.
- Lesson progress is scoped to the authenticated user and checks course enrollment before recording completion.
- Neon destination projects for Student Portal, Connect, and AdForge AI exist and their default branches were reported ready during this review.

## Production blockers / risks

1. **No Render service exists yet.** The connected Render workspaces returned empty service lists. A configured Render blueprint in GitHub is not a deployed service.
2. **No live backend health check has been verified.** The previously configured frontend API URL points at a Render hostname, but it is not evidence that a running Render service exists.
3. **The default DRF permission is `AllowAny`.** This is safe only where every view explicitly overrides permissions or is intentionally public. Audit every URL/view pair and add explicit permissions before public deployment.
4. **Payment flow is not production-ready based on the inspected API.** The current payment creation endpoint only creates a pending payment record. No Paystack checkout initialization, signed webhook verification, idempotency handling, or verified-success enrollment was present in that endpoint.
5. **The Render blueprint proposes a new Render Postgres database.** Do not create it by default; YSCMT already has Neon destinations. Configure a least-privilege Neon database role and use its connection string instead, after schema/migration review.
6. **Media persistence is unresolved.** Django currently uses local `MEDIA_ROOT`; Render container filesystems are not a durable media store. Configure a persistent object-storage target before moving certificates/uploads into production.
7. **The existing React frontend and Django API contract still needs end-to-end verification**, including login, refresh, course enrollment, progress, certificates, admin access, payment state transitions, and error handling.

## Safe deployment sequence

1. Complete the view-by-view permission and object-ownership audit.
2. Complete Paystack initialization + webhook signature verification + idempotency tests.
3. Configure persistent media/object storage and backups.
4. Create a least-privilege database role on the intended Neon project; do not use an owner credential in the app.
5. Set Render environment variables without exposing secrets: `SECRET_KEY`, `DATABASE_URL`, `DEBUG=False`, allowed hosts, frontend URL, and payment/storage credentials.
6. Deploy the backend as a separate service without changing the production `/portal` route.
7. Verify the health endpoint and all end-to-end acceptance tests.
8. Only after the replacement is proven, plan an explicitly approved cutover. Keep Hatchable available until then.

## Decision

**Not approved for production cutover yet.** The successful CI run is encouraging, but it does not prove the live API, payment processing, storage, authorization coverage, or account migration are production-ready. Keep existing production routing and Hatchable service unchanged.
