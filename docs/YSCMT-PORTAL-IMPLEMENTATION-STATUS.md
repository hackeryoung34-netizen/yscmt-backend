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

## Exam API routes now added

- `GET /api/portal/v1/courses/{course_id}/exams/`
- `POST /api/portal/v1/exams/{exam_id}/start/`
- `GET /api/portal/v1/exam-sessions/{session_id}/questions/`
- `POST /api/portal/v1/exam-sessions/{session_id}/submit/`

## CI verification

- Previous complete Student Portal CI passed on commit `da7bc047dcc187d7c44c00d70805c6a72220b5a3`, run [45342438730](https://github.com/hackeryoung34-netizen/yscmt-backend/actions/runs/45342438730). It verified Django checks, migration drift, all migrations against disposable PostgreSQL 16, and the initial exam API tests.
- The additional expired-session test was added in commit `fbcd83620df92933a41aa630f18e3187f79ca7c6`; its workflow run is pending verification.
- A separate legacy workflow currently reports failure with no jobs returned by the GitHub jobs endpoint. This is distinct from the dedicated preview workflow and needs separate investigation.

## Remaining feature parity

Payment intents and server-side Paystack verification, certificates, classroom/practice submissions, attendance, announcements, teacher replies, audit logs, admin workflows, storage migration, and source-record mapping remain to be implemented and tested.

## Not yet done

- No migration has been run against the Neon database.
- No real student records, payment data, password hashes, receipts, or certificates have been copied.
- No Render service has been created.
- No production frontend, Vercel settings, DNS, or Hatchable settings have been changed.

## Deployment gate and safety

Do not create the Render preview until the planned feature scope and tests are ready and migration files have been reviewed. Any preview must be Free, use the already-selected My Workspace, point to this branch, and use the Neon development connection only through Render secret environment configuration. Keep Hatchable active. Do not perform production cutover or disable Hatchable.
