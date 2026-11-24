# YSCMT Student Portal — implementation status

Branch: `migration/neon-django-preview`

## Implemented in the isolated branch

A Django-native portal foundation exists under `yscmt/student_portal/`:

- Separate UUID-based portal identity model, independent of legacy Django `auth.User`.
- Django password hashing and verification.
- Student-only public registration; clients cannot select instructor/admin roles.
- Portal JWT access and refresh tokens; authentication resolves identity and trusted role from PostgreSQL on every request.
- ORM-backed active course catalogue and course detail.
- Student enrolment derives the student from the authenticated identity and creates a pending record; database constraint prevents duplicate student/course enrolments.
- Lesson content is withheld until enrolment is approved or completed.
- Idempotent lesson completion and course progress counts/percentage.
- Exam catalogue is restricted to approved/completed course enrolments.
- Timed exam sessions can resume while active; only one active session per student/exam is allowed.
- Question delivery deliberately omits the correct answer field.
- Exam submissions are checked and scored on the server; one persisted attempt per session; repeat submission returns the same result.
- Expired sessions are closed and recorded as failed attempts rather than silently discarded.
- Paystack payment intents are created from the stored course fee; the client cannot set amount or currency.
- Payment initialization and verification run server-side only; secret-key test/live mode is checked before use.
- Enrolment is approved only after Paystack reports success with matching reference, amount, currency and gateway domain; mismatches leave the enrolment pending.
- Repeated verification is idempotent, and payment initialization fails closed when gateway secrets are absent.

## Exam API routes now added

- `GET /api/portal/v1/courses/{course_id}/exams/`
- `POST /api/portal/v1/exams/{exam_id}/start/`
- `GET /api/portal/v1/exam-sessions/{session_id}/questions/`
- `POST /api/portal/v1/exam-sessions/{session_id}/submit/`
- `POST /api/portal/v1/enrollments/{enrollment_id}/payments/initialize/`
- `POST /api/portal/v1/payments/{reference}/verify/`

## CI verification

- Student Portal preview CI passed on commit `6ba2f9ad1299553453ff48ade14e65450f3d0459`, run [45343183083](https://github.com/hackeryoung34-netizen/yscmt-backend/actions/runs/45343183083). It verified Django checks, migration drift, all migrations against disposable PostgreSQL 16, and the Student Portal API tests including exam timeout and Paystack initialization/verification safeguards.
- A separate legacy workflow reports failure with no jobs returned by the GitHub jobs endpoint. This is distinct from the dedicated preview workflow and remains a separate investigation item.

## Remaining feature parity

Certificates, classroom/practice submissions, attendance, announcements, teacher replies, audit logs, admin workflows, storage migration, Paystack webhook reconciliation, and source-record mapping remain to be implemented and tested.

## Not yet done

- No migration has been run against the Neon database.
- No real student records, payment data, password hashes, receipts, or certificates have been copied.
- No Render service has been created.
- No production frontend, Vercel settings, DNS, or Hatchable settings have been changed.

## Deployment gate and safety

Do not create the Render preview until the planned feature scope and tests are ready and migration files have been reviewed. Any preview must be Free, use the already-selected My Workspace, point to this branch, and use the Neon development connection only through Render secret environment configuration. Keep Hatchable active. Do not perform production cutover or disable Hatchable.
