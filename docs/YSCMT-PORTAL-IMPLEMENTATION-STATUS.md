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
- Certificate issuance requires approved/completed enrolment, completion of all active lessons and a passed exam; issuance is idempotent and certificates are verifiable.
- Classroom sessions, attendance, student messages, announcements, teacher replies and practice submissions have student-side APIs with enrolment/ownership checks.
- Admin dashboard counts and student directory are available only to database-authorized admins.
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

- Dedicated Student Portal CI passed on commit `13772dc320ecaa4982bd0c7a7fbd61ed62d17631`, run [45344616905](https://github.com/hackeryoung34-netizen/yscmt-backend/actions/runs/45344616905). It verified Django checks, migration drift, all migrations against disposable PostgreSQL 16, and API tests including enrollment-completion and self-review safeguards.
- The dashboard, practice queue and route additions are being verified by [45344715017](https://github.com/hackeryoung34-netizen/yscmt-backend/actions/runs/45344715017).
- The PostgreSQL-only preview guard passed in [45344769918](https://github.com/hackeryoung34-netizen/yscmt-backend/actions/runs/45344769918), including Django checks, migration drift, PostgreSQL 16 migrations and the full Student Portal API suite.
- An additional CI gate now explicitly verifies that preview startup rejects both a missing `DATABASE_URL` and a SQLite URL; run [45344908675](https://github.com/hackeryoung34-netizen/yscmt-backend/actions/runs/45344908675) is running for this stricter gate.
- Earlier failures were traced to literal escaped line breaks in `urls.py` and an extra closing brace in migration `0006_portal_audit_log.py`; both have been corrected.
- The separate legacy workflow `portal-api-tests.yml` reports failure with zero jobs returned for this migration branch. Its configured branch filters target the legacy independent branch, so it is not the authoritative check for this new preview branch. The dedicated preview workflow is the required gate.

## Remaining work before preview deployment

- Verify the newest CI run including the dashboard and PostgreSQL-only guard.
- Complete instructor-specific permissions and course assignment model after reconciling the source schema.
- Implement bank-transfer/payment-submission review and secure upload/storage mapping; the current Django payment slice covers Paystack only.
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
