# YSCMT Student Portal — implementation status

Branch: `migration/neon-django-preview`

## Implemented in the isolated branch

A first Django-native vertical slice now exists under `yscmt/student_portal/`:

- Separate UUID-based portal identity model, independent of legacy Django `auth.User`.
- Password hashes generated and checked with Django's password hashers.
- Student-only public registration; clients cannot choose instructor/admin roles.
- Portal JWT access and refresh tokens using a dedicated `PORTAL_JWT_SIGNING_KEY` environment variable when configured.
- JWT authentication resolves the identity and trusted role from PostgreSQL on every request; role claims in a token are not treated as authoritative.
- ORM-backed active course catalogue and course detail.
- Student enrolment creation always derives the student from the authenticated token and creates a `pending` record.
- Duplicate enrolments are rejected by a database unique constraint.
- Lesson content is withheld until enrolment is approved or completed.
- Lesson completion is recorded idempotently, and course progress returns total/completed lesson counts and a percentage.
- API tests cover registration, login/profile, unauthenticated access, duplicate enrolment, lesson gating, progress authorization, and idempotent completion.
- GitHub Actions preview workflow runs Django checks, migration drift checks, migrations and Student Portal tests against disposable PostgreSQL 16.

## Important scope boundary

This is a first vertical slice, not full feature parity with the Hatchable/Supabase portal. Exams and question secrecy, payments and Paystack verification, certificates, classroom, practice submissions, attendance, announcements, teacher replies, audit logs, admin workflows, storage migration, and source-record mapping remain to be implemented and tested.

## Not yet done

- Latest Student Portal preview workflow passed on commit `4cfc0948ece2c806c4c8068d9afc746b887565a8` (run [45258013044](https://github.com/hackeryoung34-netizen/yscmt-backend/actions/runs/45258013044)). Django checks, migration drift check, full Django migrations against disposable PostgreSQL 16, and Student Portal API tests passed, including the lesson progress endpoints.
- A separate legacy `Portal API tests` workflow also reported a failed run on the same commit ([45258009244](https://github.com/hackeryoung34-netizen/yscmt-backend/actions/runs/45258009244)); it is not the new preview workflow. Its failure needs investigation before deployment; do not treat the overall branch as fully green.
- No migration has been run against the Neon database.
- No real student records, payment data, password hashes, receipts, or certificates have been copied.
- No Render service has been created.
- No production frontend, Vercel settings, DNS, or Hatchable settings have been changed.

## Deployment gate

Do not create the Render preview until the CI workflow passes and the migration files have been independently reviewed. The Render service must be Free, use the already-selected `My Workspace`, point to this branch, and use the Neon development connection only via Render's secret environment configuration. Keep Hatchable active.
