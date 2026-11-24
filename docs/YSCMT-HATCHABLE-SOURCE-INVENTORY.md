# YSCMT Student Portal — Hatchable source inventory

Read-only inspection of the active Hatchable project was performed on 2026-11-24. No Hatchable files, rows, settings or deployment versions were changed.

## Source project

- Hatchable project: `YSCMT Student Portal`
- Project ID: `proj_wtjM5VcpGROw`
- Slug: `yscmt-student-portal`
- State: active
- Last inspected version: 53
- Source app remains live and is the fallback during migration.

## Current row counts

Counts are from aggregate SQL only; no student emails, names, bank account details, receipts or other personal data were exported.

| Table | Rows |
|---|---:|
| users | 5 |
| student_profiles | 0 |
| courses | 4 |
| course_lessons | 16 |
| enrollments | 0 |
| lesson_progress | 0 |
| course_exams | 4 |
| exam_questions | 40 |
| exam_sessions | 0 |
| exam_attempts | 0 |
| payment_submissions | 0 |
| paystack_payments | 0 |
| practice_submissions | 0 |
| classroom_sessions | 0 |
| classroom_attendance | 0 |
| classroom_messages | 0 |
| classroom_announcements | 0 |
| classroom_teacher_replies | 0 |
| student_certificates | 0 |
| admin_audit_logs | 20 |
| site_settings | 1 |

## Course inventory

| Course | Lessons | Exams | Exam questions |
|---|---:|---:|---:|
| Computer Fundamentals | 4 | 1 | 10 |
| Cybersecurity Fundamentals | 4 | 1 | 10 |
| Python Programming | 4 | 1 | 10 |
| Web Development | 4 | 1 | 10 |

## Account migration findings

- The Hatchable `users` table has text IDs, email, name, email verification timestamp, image, `hatchable_user_id` and `google_sub` columns.
- There are 5 user rows; all 5 have `email_verified_at`, 1 has a non-empty name, and none has `google_sub` or `hatchable_user_id`.
- The Hatchable `users` table has no password hash column. A direct password-hash migration is therefore not possible from this source schema.
- `student_profiles` is empty. Profile name fallback must use `users.name`; phone values are not currently present in the profile table.
- The Hatchable source schema has no user role column. Imported users must default to student; administrator privileges must be explicitly bootstrapped by the owner, not inferred from ordinary user rows.
- The portal includes one-time email password reset for imported accounts. Existing imported accounts must be marked `must_reset_password=true`; the email provider must be configured before user import/cutover.
- Legacy Hatchable text IDs are mapped to portal UUID identities through `private.legacy_user_map`. No user records have been copied.

## Data handling and reconciliation rules

1. Do not copy user records, audit log contents, site-setting values, payment data or files until the owner explicitly authorizes a real-data import.
2. Keep bank transfer settings private. This inventory records only that one settings row exists; its value was not read.
3. Keep the existing Hatchable project and version 53 intact. Do not deploy changes to it as part of this migration.
4. Before any future import, compare source and destination row counts by table, check all foreign-key mappings, and produce a reconciliation report with no email addresses or other unnecessary personal data.
5. Use synthetic records for preview tests. The new Neon database remains empty until an explicit, separately approved import.
