# YSCMT Student Portal — implementation status

Branch: `migration/neon-django-preview`

## Implemented in the isolated branch

A Django-native portal foundation exists under `yscmt/student_portal/`:

- UUID-based portal identity, independent of legacy Django `auth.User`, with Django password hashing.
- Public registration always creates a student; clients cannot self-assign instructor/admin roles.
- Portal JWT access/refresh; each request resolves identity and trusted role from the database.
- Active course catalogue, course details, enrolment, lesson access gating and progress tracking.
- Duplicate enrolments and duplicate lesson progress are prevented by database constraints.
- Timed exams, resumable sessions, student-scoped question delivery, server-side scoring, timeouts recorded as failed attempts, and one attempt per session.
- Correct answer keys are never included in student question responses.
- Paystack payment initialization uses the stored course fee, never a client-supplied amount. Server-side verification checks success, reference, amount, currency and expected test/live gateway domain before approving enrolment.
- Bank-transfer receipt metadata model and migration `0008_portal_payment_submission` are implemented. Admin-only review validates enrolment/student/course ownership, stored fee and currency, pending status, and student-prefixed private object key before approval; decisions are audited.
- Bank-transfer review queue is available at `GET /api/portal/v1/admin/payment-submissions/`; review uses `POST /api/portal/v1/admin/payment-submissions/{submission_id}/review/`. The admin overview includes pending bank submissions.
- Certificate issuance requires approved/completed enrolment, completion of all active lessons and a passed exam; issuance is idempotent and certificates are verifiable.
- Classroom sessions, attendance, student messages, announcements, teacher replies and practice submissions have student-side APIs with enrolment/ownership checks.
- Admin dashboard counts and student directory are available only to database-authorized admins.
- Admins can assign and unassign active instructors to active courses; each assignment is audited.
- Instructors can list only courses assigned to them and see only approved/completed students within those assigned courses.
- Assigned instructors can create classroom sessions with validated time ranges and HTTPS meeting links, publish course-specific announcements, and post teacher replies. Each action creates an audit event.
- Instructor classroom endpoints reject instructors who are not assigned to the target course; tests cover role, assignment and HTTPS validation.
- Instructor assignment model and migration `0007_course_instructor_assignment` have been added, with API permission tests.
- Admin-only enrolment review (approve/reject/complete) and practice review APIs are implemented.
- Enrolment completion is blocked unless every active lesson is complete and at least one course exam has been passed.
- Admins cannot review their own enrolment. Completed enrolments cannot be downgraded.
- Admin review actions create audit events; audit-log listing is admin-only.
- Preview setting `PORTAL_REQUIRE_POSTGRES=true` now fails closed if `DATABASE_URL` is missing or points to SQLite. The temporary SQLite fallback remains only for legacy/local initialization when the flag is not enabled.

## Admin API routes

- `GET /api/portal/v1/admin/overview/`
- `GET /api/portal/v1/admin/students/`
- `GET /api/portal/v1/admin/enrollments/?status=pending`
- `POST /api/portal/v1/admin/enrollments/{enrollment_id}/review/`
- `GET /api/portal/v1/admin/practice/submissions/?status=submitted`
- `POST /api/portal/v1/admin/practice/submissions/{submission_id}/review/`
- `GET /api/portal/v1/admin/audit-logs/`

## CI verification

- Dedicated Student Portal preview workflow passed on commit `377b2dcea9e7786154a45ee42fd360c1a92c872b`, run [45345817463](https://github.com/hackeryoung34-netizen/yscmt-backend/actions/runs/45345817463).
- Verified checks include rejection of missing `DATABASE_URL` and SQLite, Django system checks, migration-file consistency, all portal migrations against disposable PostgreSQL, and the complete Student Portal API test suite including the new instructor classroom tests.
- The separate legacy workflow `portal-api-tests.yml` reports failure with zero jobs returned for this migration branch. Its configured branch filters target the legacy independent branch, so it is not the authoritative check for this new preview branch. The dedicated preview workflow is the required gate.

## Remaining work before preview deployment

- Reconcile instructor permissions and the full classroom workflow against all source behavior and the frontend contract.
- Complete private receipt upload/download integration. The payment-submission model and admin review are ready, but no student receipt-upload endpoint is enabled because a private object-storage provider and its credentials have not been configured. Do not accept client-supplied storage keys; add server-issued, owner-bound upload authorization and private downloads only after storage setup.
- Review the full model/schema mapping against Supabase source migrations and Hatchable source records.
- Add a safe, repeatable synthetic-data migration rehearsal and reconciliation report.
- Review certificate asset handling and storage migration.
- Only after these gates pass, consider a Free Render preview using the selected workspace and Neon development branch.

## Not yet done

- No migration has been run against Neon.
- No real student records, password hashes, payment data, receipts or certificates have been copied.
- No Render service has been created.
- No production frontend, Vercel settings, DNS or Hatchable settings have been changed.

## Deployment gate and safety

Keep Hatchable active as the production service and fallback. Do not perform production cutover, disable Hatchable, change production DNS/Vercel configuration, or import real student data without explicit approval and a verified backup/mapping. Use synthetic data for preview tests. Do not introduce paid services or upgrades without explicit approval.
