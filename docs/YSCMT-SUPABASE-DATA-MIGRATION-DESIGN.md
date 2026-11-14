# YSCMT Student Portal — Supabase data and identity migration design

Status: DESIGN ONLY — not applied to the Supabase database.

Project: `wzpkfjnymsxczbkiukrp` (YSCMT-Student-Portal, eu-west-3).
Source: Hatchable project `proj_wtjM5VcpGROw`, currently ACTIVE.
Target public URLs: `https://yscmtenterprise.ng/portal` and `https://yscmtenterprise.ng/portal/admin`.

## 1. Migration principles

- Keep Hatchable online and unchanged until the replacement passes acceptance tests and rollback is proven.
- Never migrate live data directly into an untested schema.
- Preserve source primary keys when they are valid UUIDs; preserve legacy user IDs as explicit mapping values.
- Do not assume a Hatchable user ID equals a Supabase Auth UUID.
- Do not migrate password hashes or claim users can keep old passwords until the authentication method and password portability are verified. Use a controlled password-reset/invitation flow if needed.
- Keep Paystack secrets, database credentials, and Supabase secret/service-role keys server-side only.
- Keep the main website and domain routing unchanged during preview work.

## 2. Destination identity model

Use Supabase Auth as the authentication authority. Add an application-owned `user_profiles` table keyed by `auth.users.id` (UUID), containing display name, phone, avatar, timestamps, and a trusted role value. The default role is `student`.

Use a separate `legacy_user_map` table in a non-exposed schema to map:
- source system identifier (`hatchable`)
- legacy user ID (TEXT)
- destination Supabase Auth user ID (UUID)
- migration status and timestamps

The legacy map must not be readable or writable from the browser. Only a trusted server-side migration/admin process may populate it.

Roles are `student`, `instructor`, and `admin`. A user must never be able to assign or update their own role. Role changes are performed only by a trusted server-side administrative process, with audit logging. Do not trust user-editable Auth metadata for authorization.

## 3. Source table inventory and destination mapping

The current Hatchable project has 21 tables. Preserve all functional areas:

| Hatchable source table | Destination table | Identity / access notes |
|---|---|---|
| users | Supabase Auth + user_profiles | Map source TEXT id through legacy_user_map; never copy password material blindly. |
| student_profiles | student_profiles or user_profiles extension | Key by destination auth UUID; student edits only approved profile fields. |
| courses | courses | Public may read active course catalogue; writes admin/instructor only. |
| enrollments | enrollments | Student reads own; privileged staff manage status. |
| course_lessons | course_lessons | Published lessons visible only to eligible enrolled students; staff manage. |
| lesson_progress | lesson_progress | Student reads/writes own progress only. |
| course_exams | course_exams | Students read active exams only when eligible; staff manage. |
| exam_questions | exam_questions | Never expose correct answers to the student client before submission; serve through trusted server logic. |
| exam_attempts | exam_attempts | Student reads own results; submission/scoring must be server-validated. |
| exam_sessions | exam_sessions | Student can access own active session; server controls start/submit and expiry. |
| student_certificates | student_certificates | Student reads own; issuance is trusted staff/server action; verification endpoint exposes only safe certificate fields. |
| payment_submissions | payment_submissions | Student creates/reads own; staff review; private receipt storage. |
| paystack_payments | paystack_payments | Server-only writes and gateway verification; never trust client-supplied paid status. |
| practice_submissions | practice_submissions | Student creates/reads own; staff review. |
| classroom_sessions | classroom_sessions | Enrolled students read relevant sessions; staff manage. |
| classroom_attendance | classroom_attendance | Student records own attendance through controlled endpoint; staff can review. |
| classroom_messages | classroom_messages | Enrolled course members read; authors create own messages; moderation is staff-only. |
| classroom_announcements | classroom_announcements | Published announcements readable by relevant users; staff manage. |
| classroom_teacher_replies | classroom_teacher_replies | Course members read; instructor/admin creates. |
| admin_audit_logs | admin_audit_logs | Not exposed to students; append-only trusted server writes; admin read. |
| site_settings | site_settings | Private settings; public site may read only an explicitly allow-listed safe subset. |

The destination may normalize `student_profiles` into `user_profiles`, but all existing profile fields and behavior must remain available to the app.

## 4. Required security controls

- Enable RLS on every table exposed to the Data API.
- Default-deny grants; grant only the operations actually required.
- Keep migration mapping, payment gateway payloads, audit internals, and other sensitive data in a non-exposed schema or server-only access path.
- Use table-specific policies based on `auth.uid()`, course enrolment, and trusted role checks.
- Never let a client set `role`, `passed`, payment `status`, certificate issuance, exam score, or reviewer identity.
- Keep exam answer keys out of client-readable rows; use server-side exam delivery/scoring.
- Keep Paystack initialize/verify/webhook logic server-side and verify webhook signatures.
- Store payment receipts in a private Storage bucket with per-user and staff access policies.
- Review SECURITY DEFINER functions, set a safe search_path, and restrict EXECUTE grants.
- Run Supabase security and performance advisors after every schema/policy migration.

## 5. Data migration sequence

1. Freeze and document source schema/API behavior; keep Hatchable running.
2. Build destination schema and RLS in a reviewable migration file.
3. Test schema and policies with anonymous, student, instructor, and admin identities.
4. Build a disposable export/import rehearsal; no production import yet.
5. Recount every source table immediately before the final export.
6. Create Auth users through a supported admin/server process and populate legacy_user_map.
7. Import parent rows before dependent rows, preserving UUIDs and mapping user references consistently.
8. Compare row counts, foreign-key integrity, payment references, course/exam relationships, and certificate codes.
9. Test all portal workflows on a private preview.
10. Obtain explicit approval before production routing or any cutover.
11. Keep Hatchable available as rollback until the replacement has been accepted.

## 6. Current state and next gate

- Supabase project is ACTIVE_HEALTHY; public schema currently has zero application tables.
- Hatchable is ACTIVE with 21 tables and 31 API routes.
- No user records, payments, passwords, or files have been exported or imported.
- No production domain routing, DNS, or Vercel production deployment has been changed.
- This document is a design record only. The next implementation artifact is a complete SQL migration with RLS policies and server-only boundaries, reviewed against every source API route before applying it.


## 7. API behavior review — critical server-side operations

A read-only review of representative Hatchable handlers confirms that the replacement must not rely on direct browser table writes for these workflows:

- Exams: `api/student/exam.js` returns question text/options but not correct options; submission calculates score from stored answer keys and checks an active exam session and elapsed time. The replacement must keep answer keys server-only and make session submission atomic/idempotent.
- Exam start: `api/student/exam-start.js` checks active exam, approved/completed enrolment, and presence of questions before creating a session. Enforce one-time session ownership and server-side expiry.
- Paystack initialization: `api/student/paystack/initialize.js` derives amount/currency from the stored course fee, validates enrolment ownership/status, creates a server-side reference, and uses secret credentials. Never accept amount or payment status from the browser.
- Paystack verification: `api/student/paystack/verify.js` checks exact reference, amount, currency, payment domain and status with Paystack before approving enrolment. Rebuild with idempotent transactions and server-only credentials.
- Paystack webhook: `api/paystack/webhook.js` verifies the signed raw body and confirms the payment with Paystack. Preserve signature verification, replay tolerance, idempotency, and reconciliation before granting course access.
- Admin payments: `api/admin/payments.js` includes bank-transfer account details, receipt links, and payment review. Keep account numbers and receipt files behind staff authorization; expose only explicitly intended public payment instructions.
- Student enrolment: `api/student/enrol.js` checks the active course and configured fee, then creates/reopens a pending enrolment. Enforce a unique user/course pair and do not let students set approved/completed status.
- Certificates: `api/student/certificates.js` checks approved enrolment, lesson completion, and a passing active exam before issuing a certificate. Make issuance server-side and idempotent; keep public verification limited to safe certificate details.
- Admin student list: `api/admin/students.js` reads contact details and enrolment counts. Restrict this endpoint to trusted admin role and audit access where appropriate.

These handlers were inspected as source code only. No API or database behavior was changed.
