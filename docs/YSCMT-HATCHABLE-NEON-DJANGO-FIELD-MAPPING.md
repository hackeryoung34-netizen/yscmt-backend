# Hatchable → Neon/Django field-level migration map

Status: source schema inspected read-only; target Django models/migrations exist; **no source rows or files have been imported**. This document supersedes the older Supabase-target mapping for the Neon/Django preview path.

- Source: Hatchable project `YSCMT Student Portal` (`proj_wtjM5VcpGROw`), version 53.
- Target: Neon project `YSCMT-Student-Portal`, database `yscmt_student_portal`, Django app `student_portal`.
- Mapping branch: `migration/neon-django-preview`.
- Snapshot date: 2026-11-24. Counts are aggregate-only; no user emails, names, setting values, payment references, receipt objects or audit details were exported.

## 1. Source row-count snapshot

| Hatchable table | Rows | Django target |
|---|---:|---|
| `users` | 5 | `PortalIdentity` + `PortalLegacyUserMap` |
| `student_profiles` | 0 | `PortalIdentity` |
| `courses` | 4 | `PortalCourse` |
| `course_lessons` | 16 | `PortalLesson` |
| `enrollments` | 0 | `PortalEnrollment` |
| `lesson_progress` | 0 | `PortalLessonProgress` |
| `course_exams` | 4 | `PortalExam` |
| `exam_questions` | 40 | `PortalExamQuestion` |
| `exam_sessions` | 0 | `PortalExamSession` |
| `exam_attempts` | 0 | `PortalExamAttempt` |
| `payment_submissions` | 0 | `PortalPaymentSubmission` |
| `paystack_payments` | 0 | `PortalPayment` |
| `practice_submissions` | 0 | `PortalPracticeSubmission` |
| `classroom_sessions` | 0 | `PortalClassroomSession` |
| `classroom_attendance` | 0 | `PortalClassroomAttendance` |
| `classroom_messages` | 0 | `PortalClassroomMessage` |
| `classroom_announcements` | 0 | `PortalClassroomAnnouncement` |
| `classroom_teacher_replies` | 0 | `PortalTeacherReply` |
| `student_certificates` | 0 | `PortalCertificate` |
| `admin_audit_logs` | 20 | `PortalAuditLog` |
| `site_settings` | 1 | `PortalSiteSetting` (private schema) |

Totals: 21 source tables; 90 rows across the listed tables. This is a point-in-time snapshot, not an import manifest. Recount immediately before any approved export/import.

## 2. Field mapping

| Source table / fields | Target model / fields | Transformation and validation |
|---|---|---|
| `users.id`, `email`, `name`, `email_verified_at`, `image`, `created_at`, `updated_at` | `PortalIdentity`: `email`, `full_name`, `email_verified_at`, `avatar_url`, timestamps; `PortalLegacyUserMap`: `legacy_user_id`, `identity_id` | Preserve source text ID only in private legacy map; create a new UUID identity. Email must be unique and validated. No source password hash exists, so set `must_reset_password=true`; never invent a password. Name falls back from `users.name` when no non-empty profile name exists. Copy verification timestamp only after policy review. |
| `users.google_sub`, `users.hatchable_user_id` | No direct auth-provider link | Both fields are currently empty for all five source users. Do not treat either as a password, trusted role, or proof of identity. |
| `student_profiles.user_id`, `full_name`, `phone`, `created_at`, `updated_at` | `PortalIdentity`: `full_name`, `phone`, timestamps | Join through `PortalLegacyUserMap`; non-empty profile full name takes precedence over `users.name`. Source table currently has zero rows. |
| `courses.id`, `title`, `description`, `level`, `active`, `created_at`, `fee_amount`, `fee_currency` | `PortalCourse`: same UUID, `title`, `description`, `level`, `is_active`, `created_at`, `fee_amount`, `fee_currency` | Preserve UUIDs and monetary precision. Validate unique title, non-negative fee and supported currency before insert. |
| `course_lessons.id`, `course_id`, `title`, `content`, `video_url`, `sort_order`, `active`, timestamps | `PortalLesson`: same UUID, FK `course`, content fields, `is_active`, timestamps | Preserve UUID and course FK; validate parent course exists. Preserve ordering and inactive lessons. Video URL target allows up to 1000 characters. |
| `enrollments.id`, `user_id`, `course_id`, `status`, `enrolled_at` | `PortalEnrollment`: same UUID, FK `student`, FK `course`, `status`, `created_at` | Map user through private legacy map; preserve course UUID. Map `enrolled_at` to `created_at`; validate status. No rows currently exist. |
| `lesson_progress.id`, `user_id`, `lesson_id`, `completed_at` | `PortalLessonProgress`: same UUID, FK `student`, FK `lesson`, `completed_at` | Map user; preserve lesson UUID and timestamp. Enforce unique student/lesson pair. |
| `course_exams.id`, `course_id`, `title`, `instructions`, `duration_minutes`, `pass_mark`, `active`, timestamps | `PortalExam`: same UUID, FK `course`, corresponding fields, `is_active` | Preserve UUID and timestamps; validate duration/pass mark and parent course. |
| `exam_questions.id`, `exam_id`, `question_text`, `options`, `correct_option`, `sort_order`, `created_at` | `PortalExamQuestion`: same UUID, FK `exam`, matching question fields | Preserve UUID, JSON options and answer index. Correct answer is server-only and must never appear in student API responses. |
| `exam_sessions.id`, `exam_id`, `user_id`, `started_at`, `submitted_at` | `PortalExamSession`: same UUID, FK `exam`, FK `student`, timestamps | Map user and exam. Preserve nullable submitted timestamp. |
| `exam_attempts.id`, `exam_id`, `user_id`, `answers`, `score`, `passed`, `started_at`, `submitted_at` | `PortalExamAttempt`: same UUID, FK `exam`, FK `student`, `answers`, score/result/timestamps, FK `session` | Source attempts do not contain `session_id`. Pair to a source session by exact `exam_id + user_id + started_at`; if zero or multiple matches, quarantine for manual review rather than guess. Validate answer ownership and score consistency before import. |
| `paystack_payments.id`, `enrolment_id`, `user_id`, `course_id`, `reference`, `amount_kobo`, `currency`, `status`, `authorization_url`, `gateway_response`, timestamps | `PortalPayment`: same UUID, FK `enrollment`, FK `student`, reference, amount, currency, status, gateway response and timestamps | Map enrollment/user; course is derived through enrollment in the target model. Preserve gateway response only after secret/PII review. Re-verify every successful payment with Paystack before using it to approve enrolment. |
| `payment_submissions.id`, `enrolment_id`, `user_id`, `course_id`, `amount`, `currency`, `transfer_reference`, `storage_key`, `content_type`, `file_name`, `status`, `admin_note`, timestamps | `PortalPaymentSubmission`: same UUID, FK enrolment/student/course, amount/currency/reference, private `storage_key`, MIME/name/status/note/timestamps | Map all FKs. Receipt objects must be copied separately from the old private store into a private Cloudflare R2 bucket, checked by file signature/size/ownership, and assigned a new key. Never copy a public URL or trust a legacy storage key without verifying the object. No submissions or receipt objects are currently recorded. |
| `student_certificates.id`, `certificate_code`, `user_id`, `course_id`, `student_name`, `course_title`, `issued_at` | `PortalCertificate`: same UUID, code, FK student/course, snapshot names and timestamp | Map user/course; preserve certificate code and UUID. Detect duplicate codes and verify each certificate before accepting it. |
| `practice_submissions.id`, `user_id`, `lab_key`, `title`, `submission_text`, `project_url`, `status`, `reviewer_notes`, `reviewed_by`, timestamps | `PortalPracticeSubmission`: same UUID, FK student, matching submission fields, FK `reviewed_by` | Map both user references. Validate URL/status and preserve review history. |
| `classroom_sessions.id`, `course_id`, `title`, `description`, `meeting_url`, `starts_at`, `ends_at`, `status`, `created_by`, timestamps | `PortalClassroomSession`: same UUID, FK course, content/time/status, nullable FK `created_by`, `created_by_handle` | Preserve source creator text in handle. Resolve FK only when creator text maps to a known identity. Validate meeting URL, time ordering and status. |
| `classroom_attendance.id`, `session_id`, `user_id`, `joined_at` | `PortalClassroomAttendance`: same UUID, FK session/student, timestamp | Map user/session; enforce unique session/student. |
| `classroom_messages.id`, `course_id`, `user_id`, `author_role`, `message`, `created_at` | `PortalClassroomMessage`: same UUID, FK course/student, author role, message, timestamp | Map user/course. Normalize legacy `teacher` to target `instructor` only after confirming that value is the source's intended role; preserve original value in reconciliation metadata. Reject unknown roles for review. |
| `classroom_announcements.id`, `course_id`, `title`, `body`, `published`, `created_by`, `created_at` | `PortalClassroomAnnouncement`: same UUID, nullable FK course/creator, title/body/published/timestamp, creator handle | Resolve nullable course/creator; preserve creator text in handle when no identity mapping exists. |
| `classroom_teacher_replies.id`, `course_id`, `created_by`, `message`, `created_at` | `PortalTeacherReply`: same UUID, FK course, nullable FK creator, creator handle, message/timestamp | Preserve legacy creator text; map to identity only if known. |
| `admin_audit_logs.id`, `actor_handle`, `action`, `target_type`, `target_id`, `details`, `created_at` | `PortalAuditLog`: `legacy_id`, `actor_handle`, nullable FK actor, `action`, `target_type`, `target_id`, `metadata`, timestamp | Preserve original numeric ID in `legacy_id`; map actor only when resolvable. Copy `details` JSON to `metadata` after redaction review; keep audit log read-only. |
| `site_settings.setting_key`, `setting_value`, `updated_at` | `PortalSiteSetting` in PostgreSQL `private` schema | Keep private; do not expose through public API. The current source row's value has deliberately not been read. Review each setting and redact secrets before import. |

## 3. Identity and security rules

1. Hatchable user IDs are text; destination portal identities use UUIDs. Every user-owned foreign key must resolve through `private.legacy_user_map`; never cast or guess IDs.
2. Source `users` has no password-hash column. Imported accounts require secure password-reset onboarding; mark them `must_reset_password=true`.
3. Source `users` has no role column. All imported users start as students. Admin/instructor roles require a separately reviewed trusted bootstrap/assignment.
4. Preserve original UUIDs for all source business rows wherever target IDs are UUIDs.
5. Do not import real records until the owner explicitly approves a separately described import, including the treatment of personal data and email delivery.
6. Do not copy Paystack secret keys or expose private settings/receipt storage. Never use a client-supplied amount or payment status as proof of payment.
7. Import in dependency order: identities/maps → courses → lessons/exams/questions → enrolments → progress/sessions/attempts → payments/receipts → certificates/practice/classroom → audit/settings.
8. Run an idempotent dry-run first. Produce per-table source/target counts, missing-FK counts, duplicate-key counts, orphan counts and quarantined rows. No writes in dry-run mode.

## 4. Current migration readiness

- Source schema and aggregate counts were read-only inspected on 2026-11-24.
- Django target models and migrations through `0016` are present on the preview branch.
- CI on commit `c0b53d396f9e55968134c8207eb3d0c138ab9411` passed: Django checks, migration drift checks, migrations on disposable PostgreSQL, API tests, and preview PostgreSQL-only guard.
- Neon target branch remains a separate empty development database; CI used a disposable PostgreSQL database, not Neon.
- No Hatchable data or files have been copied.
- No Render preview service has been created; no production routing or cutover has occurred.
- Hatchable remains active at version 53.

## 5. Outstanding blockers before a rehearsal with real source data

- Build and test a repeatable read-only Hatchable export and a dry-run importer that preserves UUIDs and reports unresolved mappings.
- Resolve the exam-attempt/session pairing rule against actual rows if those tables become non-empty.
- Configure and test private R2 credentials in a non-production environment; the code fails closed when they are absent.
- Configure secure password-reset email delivery before any account import.
- Reconcile every source/target table and receipt object with checksums/counts before considering a production cutover.


## Read-only export validation tool

The branch includes `python manage.py audit_hatchable_export --input /secure/path/hatchable-export.json`. This command requires all 21 source tables in a JSON object, validates duplicate keys, UUIDs, foreign keys and exam-session pairing, and emits a sanitized reconciliation summary. It is a dry-run validator only and never writes to Hatchable, Neon or any other database. It has been tested with synthetic fixtures in CI run [45352448601](https://github.com/hackeryoung34-netizen/yscmt-backend/actions/runs/45352448601).
