# YSCMT Student Portal — Source Schema Inventory

Branch: `migration/neon-django-preview`

## Safety boundary

This is a schema and compatibility inventory only. It does not execute SQL, import student records, change Hatchable, change production routing, or create a Render service. The Neon project remains a new empty development database.

## Source of truth reviewed

The repository contains twelve Supabase SQL migrations under `supabase/migrations/`. Migration 001 defines the base Student Portal schema; migrations 003 and 005–012 add trusted roles, identity/course/enrollment/progress/exam/payment/classroom/admin workflows. The old SQL is **not** portable to Neon as-is because it references `auth.users`, `auth.uid()`, Supabase roles, RLS, private schemas, and Supabase RPC grants.

## Base source entities

| Source table | Key fields / relationships | Migration treatment |
|---|---|---|
| `user_profiles` | UUID user ID, full name, phone, avatar URL, timestamps | Map to a new portal identity/profile model; do not reuse Django `auth.User` PK. |
| `private.user_roles` | UUID user ID, trusted student/instructor/admin role | Keep roles server-controlled; never accept role from client input. |
| `private.legacy_user_map` | source system + legacy ID → UUID identity; pending/linked/verified/review | Preserve as migration audit/link table when data migration is approved. |
| `courses` | UUID, title, description, level, active, fee amount/currency | Dedicated portal course model; preserve currency and active state. |
| `enrollments` | UUID, identity, course, pending/approved/completed/rejected, unique identity/course | Enforce unique identity/course and create pending only from student self-service. |
| `course_lessons` | UUID, course, title, content, video URL, sort order, active | Dedicated portal lesson model; order by sort order and creation time. |
| `lesson_progress` | UUID, identity, lesson, completed timestamp, unique identity/lesson | Scope all reads/writes to the authenticated identity. |
| `course_exams` | UUID, course, title, instructions, duration, pass mark, active | Separate exam model; preserve inactive state and constraints. |
| `exam_questions` | UUID, exam, JSON options, correct option, sort order | Never return correct option in student-facing question responses. |
| `exam_sessions` | UUID, exam, identity, start/submitted timestamps | Enforce identity ownership. |
| `exam_attempts` | UUID, exam, identity, JSON answers, score, passed, timestamps | Server calculates score; never trust submitted score. |
| `student_certificates` | UUID, certificate code, identity/course, display-name/title snapshots | Preserve uniqueness of certificate code and identity/course. |
| `payment_submissions` | UUID, enrolment/identity/course, amount/currency, storage metadata, status, review fields | Payment approval is staff-only; file storage migration needs separate mapping. |
| `paystack_payments` | UUID, enrolment/identity/course, unique reference, amount kobo, currency, status, gateway response | Server-only gateway verification; never accept client-supplied success. |
| `practice_submissions` | UUID, identity, lab key/title, submission, project URL, review status/notes | Identity-scoped student access; reviewer fields staff-only. |
| `classroom_sessions` | UUID, course, meeting URL, start/end, status, creator | Validate end after start; staff controls creation/status. |
| `classroom_attendance` | session + identity, joined timestamp, unique identity/session | Identity-scoped attendance. |
| `classroom_messages` | course + identity, trusted author role, message, timestamp | Derive author role from trusted identity; don't accept arbitrary role. |
| `classroom_announcements` | optional course, title/body, published, creator | Public-to-enrolled or portal-wide read rules must be preserved. |
| `classroom_teacher_replies` | course, creator, message, timestamp | Instructor/admin-only creation. |
| `admin_audit_logs` | actor, handle, action, target, JSON details, timestamp | Append-only audit trail; never expose secrets. |
| `private.site_settings` | key/value JSON and timestamp | Keep server-side; no student read/write endpoint. |

## Existing Django model mismatch

The legacy Django apps have a simpler and separate schema:
- `courses.Course` uses an integer Django primary key, `name`, `description`, `price`; it lacks source UUID, level, active, and fee currency.
- `lessons.Lesson` points to the legacy Course and uses integer PKs; source lessons use UUIDs and active/sort-order fields.
- `enrollments.Enrollment` points to Django's built-in User and Course and has no status field; source enrolments use a portal identity UUID and four-state status.
- The existing `accounts.Profile` is a one-to-one extension of Django's built-in User and is not the source portal profile.

Therefore, directly pointing the current legacy models at the new Neon tables or changing `AUTH_USER_MODEL` would risk breaking existing Django migrations and consumers. The portal needs its own explicit models and authentication adapter, while legacy apps remain untouched until separately assessed.

## Student API behavior that must be preserved

1. `GET /api/portal/v1/me/`: authenticated user's own identity and trusted role.
2. `GET /api/portal/v1/courses/`: active catalogue, with only the caller's own enrolment status.
3. `GET /api/portal/v1/courses/{id}/`: one active course and caller's enrolment status.
4. `GET /api/portal/v1/courses/{id}/lessons/`: lesson content only when caller has approved/completed enrolment.
5. `POST /api/portal/v1/enrollments/`: accept course ID only; derive identity from token and always create pending; duplicate enrolment is a conflict.
6. Progress endpoints from migration 008: mark completion idempotently and calculate progress only for the caller's approved/completed enrolment.

## Authentication migration requirements

- New portal identity UUIDs must remain independent of legacy Django user integer IDs.
- Store passwords only as Django-compatible password hashes; never plaintext.
- Trusted role is stored server-side and is never read from user-editable JWT metadata.
- JWT signing key must be a dedicated environment secret, distinct from `SECRET_KEY`.
- Validate token signature, expiry, issuer/audience where configured, active identity, and allowed role.
- Do not migrate Supabase passwords unless the current hash format and secure verification path are explicitly validated. Password reset may be required for some accounts.
- Add throttling to login and avoid account enumeration in login errors.

## Current implementation gate

No portal identity or new portal tables have been created in Neon yet. The next code change must include models, migrations, token issue/refresh/login behavior, ORM-backed views, permission tests, and a disposable-PostgreSQL migration test before any Neon schema migration or Render deployment. Do not run the old Supabase SQL files against Neon.
