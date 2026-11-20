# YSCMT Hatchable → Supabase source/target field map

Status: field-level mapping specification; target schema foundation is applied, but no Hatchable rows or Auth accounts have been copied.

Source project: `YSCMT Student Portal` (`proj_wtjM5VcpGROw`)
Destination: Supabase project `wzpkfjnymsxczbkiukrp`

## Identity rules

- Hatchable `users.id` and every source `user_id` are text identifiers. Create Supabase Auth users through the Admin Auth API using verified email ownership/invitation or password-reset onboarding. Never copy a password hash unless its format and portability are proven.
- After a destination Auth user exists, write `private.legacy_user_map(source_system='hatchable', legacy_user_id, auth_user_id, migration_status)`. All user-owned rows map through this table.
- `users.email` becomes the Auth email. `users.name` is the fallback display name; `student_profiles.full_name` takes precedence when non-empty. `student_profiles.phone` becomes profile phone. `users.email_verified_at` is evidence for verification only; do not mark an email confirmed unless the source verification record is valid and the migration policy explicitly accepts it.
- Do not import `google_sub` as a password or trusted authorization claim. Social identity linking must be completed through Supabase Auth's supported identity flow.
- All non-user source primary keys are UUIDs. Preserve those UUIDs in the destination where their target tables have matching IDs. This keeps course/lesson/exam/enrolment relationships stable. Do not regenerate IDs for those rows.
- Never derive authorization from Hatchable role strings, `raw_user_meta_data`, or a client-supplied role. Assign instructor/admin only through a trusted reviewed server-side process.

## Table-by-table mapping

| Hatchable source | Supabase destination | Mapping / notes |
|---|---|---|
| `users` | Supabase Auth `auth.users` + `public.user_profiles` + `private.legacy_user_map` | Source text `id` maps to Auth UUID. `email` to Auth email; `name` fallback for profile `full_name`; `email_verified_at` reviewed before confirming; do not directly migrate password data or `google_sub`. |
| `student_profiles` | `public.user_profiles` | `user_id` via legacy user map; `full_name` preferred over `users.name`; `phone`, `created_at`, `updated_at` mapped. |
| `courses` | `public.courses` | Preserve UUID `id`; copy title, description, level, active, created_at, fee_amount, fee_currency. |
| `enrollments` | `public.enrollments` | Preserve UUID `id`; map text `user_id` through legacy map; preserve course UUID; copy status and enrolled_at after validating allowed status. |
| `course_lessons` | `public.course_lessons` | Preserve UUID `id`; preserve course UUID; copy title, content, video_url, sort_order, active, timestamps. |
| `lesson_progress` | `public.lesson_progress` | Preserve UUID `id`; map user; preserve lesson UUID; copy completed_at. |
| `course_exams` | `public.course_exams` | Preserve UUID `id`; preserve course UUID; copy title, instructions, duration_minutes, pass_mark, active, timestamps. |
| `exam_questions` | `public.exam_questions` | Preserve UUID `id`; preserve exam UUID; copy question_text, options, correct_option, sort_order, created_at. Keep correct_option server-only; never return it in student exam payloads. |
| `exam_sessions` | `public.exam_sessions` | Preserve UUID `id`; preserve exam UUID; map text user_id; copy started_at/submitted_at. |
| `exam_attempts` | `public.exam_attempts` | Preserve UUID `id`; preserve exam UUID; map user; copy answers, score, passed, started_at, submitted_at only after validating scoring/session integrity. |
| `student_certificates` | `public.student_certificates` | Preserve UUID `id`; map user; preserve course UUID; copy certificate_code, student_name, course_title, issued_at; resolve unique collisions before import. |
| `payment_submissions` | `public.payment_submissions` | Preserve UUID `id`; preserve enrolment/course UUIDs; map user; copy amount, currency, transfer_reference, storage_key, content_type, file_name, status, admin_note and timestamps. Verify receipt objects separately; never make receipt storage public. |
| `paystack_payments` | `public.paystack_payments` | Preserve UUID `id`; preserve enrolment/course UUIDs; map user; copy reference, amount_kobo, currency, status, authorization_url, gateway_response, created_at, verified_at. Reconcile each successful payment against Paystack before treating it as paid. Never import secret keys. |
| `practice_submissions` | `public.practice_submissions` | Preserve UUID `id`; map user; copy lab_key, title, submission_text, project_url, status, reviewer_notes, submitted_at, reviewed_at; map nullable text `reviewed_by` via user map. |
| `classroom_sessions` | `public.classroom_sessions` | Preserve UUID `id`; preserve course UUID; copy title, description, meeting_url, starts_at, ends_at, status, timestamps; map source text `created_by` to Auth UUID only when it identifies a real user. Legacy literal `admin` requires manual attribution or null. |
| `classroom_attendance` | `public.classroom_attendance` | Preserve UUID `id`; preserve session UUID; map text user_id; copy joined_at. Preserve uniqueness of user/session. |
| `classroom_messages` | `public.classroom_messages` | Preserve UUID `id`; preserve course UUID; map text user_id; copy author_role, message, created_at. Re-derive author_role from trusted role registry if source values are not reliable. |
| `classroom_announcements` | `public.classroom_announcements` | Preserve UUID `id`; preserve nullable course UUID; copy title, body, published, created_at; map `created_by` only when it identifies a real source user. Legacy literal `admin` requires manual attribution or null. |
| `classroom_teacher_replies` | `public.classroom_teacher_replies` | Preserve UUID `id`; preserve course UUID; map text `created_by` to Auth UUID when it identifies a real user. The target column is nullable so a legacy literal `admin` can be retained as an unattributed historical reply; do not fabricate a user. |
| `admin_audit_logs` | `public.admin_audit_logs` | Preserve numeric id only if sequence collision is handled; map actor to nullable Auth UUID where a real user exists; copy actor_handle, action, target_type, target_id, details, created_at. Keep access server-only. |
| `site_settings` | `private.site_settings` | Copy setting_key, setting_value, updated_at only after reviewing each value for secrets, stale credentials, and environment-specific URLs. Never import secret values into frontend config. |

## Known source-specific conversion issues

- Source user ownership columns are text and commonly default to Hatchable's request-scoped user ID. Destination ownership columns are UUID foreign keys to Supabase Auth. Every such value must be resolved through `private.legacy_user_map`; unknown IDs are a hard migration error, not a reason to drop or guess ownership.
- Source creator/reviewer fields on classroom and practice tables are text. Destination references use Auth UUIDs. Literal defaults such as `admin` are not UUIDs and must be reviewed individually.
- Source `classroom_announcements.created_by`, `classroom_sessions.created_by`, `classroom_teacher_replies.created_by`, and `practice_submissions.reviewed_by` need explicit identity conversion.
- Payment receipt storage keys are not file bytes. Export and verify each referenced object separately, then import into a private Supabase Storage bucket with an access policy before updating destination references.
- Source payment rows and gateway responses are historical evidence, not proof of current settlement. Verify references, amounts and currencies against Paystack before approving enrolments.
- The target schema has intentionally stricter checks and foreign keys. Invalid source values must be quarantined in a migration report for review rather than silently coerced.

## Import order

1. Courses.
2. Course lessons and exams.
3. Exam questions.
4. Auth users, profiles and the legacy user map (after identity invitation/reset policy is approved).
5. Enrolments.
6. Lesson progress, exam sessions and attempts.
7. Certificates.
8. Payment submissions and Paystack history after reconciliation.
9. Practice submissions.
10. Classroom sessions, attendance, messages, announcements and teacher replies.
11. Audit logs and reviewed site settings.
12. Reset sequences where needed; run orphan, duplicate, count and relationship checks.

## Required pre-cutover reconciliation

- Compare source and destination counts for every table.
- Confirm every non-null source user ID maps to exactly one Auth UUID.
- Confirm all course, lesson, exam, enrolment and classroom foreign keys resolve.
- Confirm no exam answer keys are exposed in student responses.
- Confirm every imported payment is independently reconciled and all receipts remain private.
- Confirm no user can self-assign instructor/admin.
- Test student, instructor and admin API authorization.
- Keep Hatchable read-only/live for rollback until the user approves final cutover.

## Current status

This document is a field-level plan only. No Hatchable data, user accounts, payment records, receipt files, or settings have been exported or imported. The live Hatchable portal and `yscmtenterprise.ng` have not been changed.


## New exam-session linkage

The target `exam_attempts.exam_session_id` is a migration-generated nullable foreign key added by migration 009, not a legacy Hatchable field. Imported historical attempts may leave it null; all newly submitted portal attempts bind to exactly one exam session and use a unique index to make session submission idempotent.


## Payment field conversion and server-generated values

- Legacy Paystack transaction records map to `public.paystack_payments`; the new `reference`, `amount_kobo`, `currency`, and `exam_session_id` values are generated/validated by the new portal workflow.
- The current Paystack Edge Function supports NGN only and derives kobo amount from the stored `courses.fee_amount`; it never accepts a payment amount from the browser.
- Payment verification and webhook reconciliation are server-only; historical transaction rows must be reconciled against Paystack before enrolment approval is migrated.
