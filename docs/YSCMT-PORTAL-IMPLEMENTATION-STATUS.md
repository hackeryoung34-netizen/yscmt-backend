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
- API tests cover registration, login/profile, unauthenticated access, duplicate enrolment, and lesson gating.
- GitHub Actions workflow runs Django checks, migration drift checks, migrations and tests against disposable PostgreSQL 16.

## Important scope boundary

This is a first vertical slice, not full feature parity with the Hatchable/Supabase portal. Exams, question secrecy, payments and Paystack verification, certificates, classroom, practice submissions, attendance, announcements, teacher replies, audit logs, admin workflows, lesson progress endpoints, storage migration, and source-record mapping remain to be implemented and tested.

## Not yet done

- GitHub Actions has not yet been observed passing.
- No migration has been run against the Neon database.
- No real student records, payment data, password hashes, receipts, or certificates have been copied.
- No Render service has been created.
- No production frontend, Vercel settings, DNS, or Hatchable settings have been changed.

## Deployment gate

Do not create the Render preview until the CI workflow passes and the migration files have been independently reviewed. The Render service must be Free, use the already-selected `My Workspace`, point to this branch, and use the Neon development connection only via Render's secret environment configuration. Keep Hatchable active.
