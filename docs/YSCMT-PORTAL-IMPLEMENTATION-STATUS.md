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
- Classroom sessions, attendance, messages, announcements, teacher replies and practice submissions have student-side APIs with enrolment/ownership checks.
- Admin-only enrolment review (approve/reject) and practice review APIs have been added.
- Admin review actions create audit events; audit-log listing is admin-only.
- Public registration cannot grant admin privileges; admin APIs check the database-backed role.

## Current admin routes

- `GET /api/portal/v1/admin/enrollments/?status=pending`
- `POST /api/portal/v1/admin/enrollments/{enrollment_id}/review/`
- `POST /api/portal/v1/admin/practice/submissions/{submission_id}/review/`
- `GET /api/portal/v1/admin/audit-logs/`

## CI verification

- Previous dedicated Student Portal preview workflow passed on commit `f8d878792ce5a6740c55fe34fc43e450ec912587`, run [45343850546](https://github.com/hackeryoung34-netizen/yscmt-backend/actions/runs/45343850546).
- The new admin review/audit-log implementation adds migration `0006_portal_audit_log` and tests for role protection and audit creation.
- CI for the latest changes is running: [45344202996](https://github.com/hackeryoung34-netizen/yscmt-backend/actions/runs/45344202996). Do not treat the new admin changes as verified until it passes.
- A separate legacy workflow `portal-api-tests.yml` continues to report failure with no jobs returned by the GitHub jobs endpoint. It is separate from the dedicated preview workflow and still needs diagnosis.

## Remaining work before preview deployment

- Verify the latest admin migration and tests in CI.
- Review the full model/schema mapping against Supabase source migrations and Hatchable source records.
- Add and test remaining administrative workflows, instructor permissions, and webhook reconciliation.
- Add a safe, repeatable synthetic-data migration rehearsal and reconciliation report.
- Add a deployment guard requiring a PostgreSQL `DATABASE_URL` for non-debug preview; do not allow the ephemeral SQLite fallback for student records.
- Review upload/storage migration and certificate asset handling.
- Only after these gates pass, consider a Free Render preview using the selected workspace and Neon development branch.

## Not yet done

- No migration has been run against Neon.
- No real student records, password hashes, payment data, receipts or certificates have been copied.
- No Render service has been created.
- No production frontend, Vercel settings, DNS or Hatchable settings have been changed.

## Deployment gate and safety

Keep Hatchable active as the production service and fallback. Do not perform production cutover, disable Hatchable, change production DNS/Vercel configuration, or import real student data without explicit approval and a verified backup/mapping. Use synthetic data for preview tests. Do not introduce paid services or upgrades without explicit approval.
