# YSCMT Student Portal — implementation status

Branch: `migration/neon-django-preview`

## Implemented in the isolated branch

A first Django-native vertical slice exists under `yscmt/student_portal/`:

- Separate UUID-based portal identity model, independent of legacy Django `auth.User`.
- Django password hashing and verification.
- Student-only public registration; clients cannot choose instructor/admin roles.
- Portal JWT access and refresh tokens.
- Authentication resolves identity and trusted role from PostgreSQL on each request.
- ORM-backed active course catalogue and course detail.
- Student enrolment derives the student from the authenticated identity and creates a pending record.
- Database unique constraint prevents duplicate student/course enrolments.
- Lesson content is withheld until enrolment is approved or completed.
- Idempotent lesson completion and course progress counts/percentage.
- API tests cover registration, login/profile, unauthenticated access, duplicate enrolment, lesson gating, progress authorization and idempotent completion.

## CI verification

- Student Portal preview workflow passed on commit `d95b1e21286b5c83fc085aff4d953565536a540d`, run [45342000065](https://github.com/hackeryoung34-netizen/yscmt-backend/actions/runs/45342000065).
- Verified steps: dependency installation, Django system checks, migration drift check, migrations against disposable PostgreSQL 16, and Student Portal API tests.
- A separate legacy workflow run [45341997923](https://github.com/hackeryoung34-netizen/yscmt-backend/actions/runs/45341997923) reported failure. Its workflow is separate from the new preview workflow; its failure must be investigated before treating every repository check as green.

## Remaining feature parity

Exams and question secrecy, exam attempts/scoring, payment intents and server-side Paystack verification, certificates, classroom/practice submissions, attendance, announcements, teacher replies, audit logs, admin workflows, storage migration, and source-record mapping remain to be implemented and tested.

## Not yet done

- No migration has been run against the Neon database.
- No real student records, payment data, password hashes, receipts, or certificates have been copied.
- No Render service has been created.
- No production frontend, Vercel settings, DNS, or Hatchable settings have been changed.

## Deployment gate and safety

Do not create the Render preview until the planned feature scope and tests are ready and migration files have been reviewed. Any preview must be Free, use the already-selected My Workspace, point to this branch, and use the Neon development connection only through Render secret environment configuration. Keep Hatchable active. Do not perform production cutover or disable Hatchable.
