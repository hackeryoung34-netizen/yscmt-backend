# YSCMT Student Portal — implementation status

Branch: `migration/neon-django-preview`

## Implemented in the isolated branch

A Django-native portal foundation exists under `yscmt/student_portal/`:

- UUID-based portal identity, independent of legacy Django `auth.User`, with Django password hashing. Supabase Auth bcrypt hashes can be verified on first login and upgraded in place to Django's current password hash.
- Public registration always creates a student; clients cannot self-assign instructor/admin roles.
- Portal JWT access/refresh; each request resolves identity and trusted role from the database.
- Active course catalogue, course details, enrolment, lesson access gating and progress tracking.
- Duplicate enrolments and duplicate lesson progress are prevented by database constraints.
- Timed exams, resumable sessions, student-scoped question delivery, server-side scoring, timeouts recorded as failed attempts, and one attempt per session.
- Correct answer keys are never included in student question responses.
- Paystack payment initialization uses the stored course fee, never a client-supplied amount. Server-side verification checks success, reference, amount, currency and expected test/live gateway domain before approving enrolment.
- Bank-transfer receipt metadata model and migrations `0008_portal_payment_submission` and `0009_receipt_upload_state` are implemented. A unique constraint permits only one uploading/pending receipt per enrolment.
- Source schema alignment migration `0010` preserves course title uniqueness/defaults, lesson defaults/update timestamp, classroom creator fields, practice reviewer, nullable legacy teacher-reply creator, and audit actor/handle/nullable target. Audit rows have a `legacy_id` field for source ID reconciliation.
- Migration `0011` adds `avatar_url`, maps `private.legacy_user_map` into the private PostgreSQL schema with source-system/user uniqueness and migration status, and maps `private.site_settings` into the private schema. These private tables have no student-facing routes.
- Private receipt upload uses a server-issued, 5-minute S3-compatible presigned POST for Cloudflare R2. The object key is generated server-side under the student's UUID prefix; the POST policy pins content type, owner metadata and a 5 MB maximum. A separate finalize API verifies object ownership metadata, size, content type and PDF/JPEG/PNG file signature before the receipt enters the admin queue.
- Student/admin receipt access uses 2-minute presigned GET links; students can access only their own receipts. Admin approval re-checks the private object before approving the related pending enrolment. All upload/review actions are audited.
- Bank-transfer routes: `POST /api/portal/v1/student/payment-submissions/upload/`, `POST /api/portal/v1/student/payment-submissions/{submission_id}/complete-upload/`, `GET /api/portal/v1/payment-submissions/{submission_id}/receipt/`, `GET /api/portal/v1/admin/payment-submissions/`, and `POST /api/portal/v1/admin/payment-submissions/{submission_id}/review/`. The admin overview includes pending bank submissions.
- Admin Paystack history is available at `GET /api/portal/v1/admin/paystack-payments/`; dashboard bank payment count matches the source RPC field `pending_bank_payments_count`.
- Student profile read/update is self-scoped at `GET/PATCH/POST /api/portal/v1/me/`; the patch accepts name, phone and HTTPS avatar URL only, never role changes.
- Admin APIs now cover course/lesson/exam creation and publishing, classroom sessions/announcements/replies, bank-transfer settings and payment review, Paystack history, student directory, enrollment review, practice review, and audit logs.
- Student enrollment listing reports bank/Paystack payment status; lesson and exam lists include progress and latest exam result fields; the unified classroom feed combines student messages and teacher replies.
- R2 credentials are read only from environment variables: `PORTAL_R2_ENDPOINT_URL`, `PORTAL_R2_ACCESS_KEY_ID`, `PORTAL_R2_SECRET_ACCESS_KEY`, and `PORTAL_R2_BUCKET`. Missing credentials fail closed with HTTP 503; no public bucket URLs are used.
- Certificate issuance requires approved/completed enrolment, completion of all active lessons and a passed exam; issuance is idempotent and certificates are verifiable.
- Classroom sessions, attendance, student messages, announcements, teacher replies and practice submissions have student-side APIs with enrolment/ownership checks.
- Admin dashboard counts and student directory are available only to database-authorized admins.
- Admins can assign and unassign active instructors to active courses; each assignment is audited.
- Instructors can list only courses assigned to them and see only approved/completed students within those assigned courses.
- Assigned instructors can create classroom sessions with validated time ranges and HTTPS meeting links, publish course-specific announcements, and post teacher replies. Each action creates an audit event.
- Instructor classroom endpoints reject instructors who are not assigned to the target course; tests cover role, assignment and HTTPS validation.
- Instructor assignment model and migration `0007_course_instructor_assignment` have been added, with API permission tests.
- Admin-only enrolment review (approve/reject/complete) and practice review APIs are implemented.
- Enrolment completion is blocked unless every active lesson is complete and at least one course exam has been passed.
- Admins cannot review their own enrolment. Completed enrolments cannot be downgraded.
- Admin review actions create audit events; audit-log listing is admin-only.
- Preview setting `PORTAL_REQUIRE_POSTGRES=true` now fails closed if `DATABASE_URL` is missing or points to SQLite. The temporary SQLite fallback remains only for legacy/local initialization when the flag is not enabled.

## Admin API routes

- `GET /api/portal/v1/admin/overview/`
- `GET /api/portal/v1/admin/students/`
- `GET /api/portal/v1/admin/enrollments/?status=pending`
- `POST /api/portal/v1/admin/enrollments/{enrollment_id}/review/`
- `GET /api/portal/v1/admin/practice/submissions/?status=submitted`
- `POST /api/portal/v1/admin/practice/submissions/{submission_id}/review/`
- `GET /api/portal/v1/admin/audit-logs/`

## CI verification

- Private receipt upload/download code and migration `0009` passed full CI on run [45346716577](https://github.com/hackeryoung34-netizen/yscmt-backend/actions/runs/45346716577). Additional dedicated storage-helper tests were added in `student_portal/test_storage.py` and passed with the complete preview workflow on [45350714485](https://github.com/hackeryoung34-netizen/yscmt-backend/actions/runs/45350714485).
- Source-schema parity migration `0010` and API changes passed full CI on run [45346987425](https://github.com/hackeryoung34-netizen/yscmt-backend/actions/runs/45346987425).
- A subsequent Paystack list endpoint test exposed and fixed an incorrect ORM relation; the corrected run is [45347520533](https://github.com/hackeryoung34-netizen/yscmt-backend/actions/runs/45347520533) and was still running when the status page was updated.
- The latest dedicated preview CI run [45350714485](https://github.com/hackeryoung34-netizen/yscmt-backend/actions/runs/45350714485) passed on branch commit `b013bb2c51a9a40a506075de533efc6a02e038c3`. This includes the isolated storage-helper tests added in commit `c192e94dc497539567e7ca1381f58dd507edf543`.
- Verified checks include rejection of missing `DATABASE_URL` and SQLite, Django system checks, migration-file consistency, all portal migrations against disposable PostgreSQL, and the complete Student Portal API test suite including the new instructor classroom tests.
- The separate legacy workflow `portal-api-tests.yml` reports failure with zero jobs returned for this migration branch. Its configured branch filters target the legacy independent branch, so it is not the authoritative check for this new preview branch. The dedicated preview workflow is the required gate.

## Remaining work before preview deployment

- Reconcile instructor permissions and the full classroom workflow against all source behavior and the frontend contract.
- Configure a private Cloudflare R2 bucket and its restricted CORS policy for the approved preview frontend, then add R2 secrets only to the preview service environment. The receipt size limit follows Hatchable's existing 5 MB cap. No bucket has been created/configured and no R2 credentials are present in this repository or chat; receipt upload therefore returns HTTP 503 until the owner configures these secrets.
- Finish a field-by-field schema and Hatchable data reconciliation, including source account/profile mapping and password-hash coverage. The source user mapping/settings tables are now represented, but no source records have been copied.
- Add a safe, repeatable synthetic-data migration rehearsal and reconciliation report.
- Review certificate asset handling and storage migration.
- Only after these gates pass, consider a Free Render preview using the selected workspace and Neon development branch.

## Not yet done

- No migration has been run against Neon; migrations so far were applied only to disposable PostgreSQL 16 in CI.
- The explicit administrator bootstrap command is available: set `PORTAL_BOOTSTRAP_ADMIN_EMAIL`, `PORTAL_BOOTSTRAP_ADMIN_CONFIRM=YES`, optionally `PORTAL_BOOTSTRAP_ADMIN_USERNAME`, then run `python manage.py bootstrap_portal_admin --confirm`. It is not run automatically. An account without a usable password is marked for email password reset.
- SMTP reset delivery must be configured through `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, and `DEFAULT_FROM_EMAIL` before importing real Hatchable users.
- No real student records, password hashes, payment data, receipts or certificates have been copied.
- No Render service has been created.
- No production frontend, Vercel settings, DNS or Hatchable settings have been changed.

## Deployment gate and safety

Keep Hatchable active as the production service and fallback. Do not perform production cutover, disable Hatchable, change production DNS/Vercel configuration, or import real student data without explicit approval and a verified backup/mapping. Use synthetic data for preview tests. Do not introduce paid services or upgrades without explicit approval.

## Latest migration work — 2026-11-24

- Added `docs/YSCMT-HATCHABLE-NEON-DJANGO-FIELD-MAPPING.md`: all 21 live Hatchable source tables are mapped to their Django target models, including field transformations, foreign-key mapping, identity reset rules, payment/receipt handling, and exam attempt/session reconciliation.
- Rechecked Hatchable with read-only aggregate queries. Current snapshot: 5 users, 4 courses, 16 lessons, 4 exams, 40 questions, 20 audit logs and 1 site-setting row; all other listed portal tables are empty. No user names, emails, setting values, audit details, payment details or file contents were exported.
- Verified the exact Neon development database tree using a read-only catalog inspection: database `yscmt_student_portal` currently contains only the `public` schema and no application tables. Neon has not received migrations or source records.
- Private receipt-storage integration is implemented against Cloudflare R2 S3-compatible storage using short-lived presigned upload/download links, owner metadata, size/MIME/signature checks, and fail-closed behavior when credentials are absent. It is not operational until non-production R2 credentials and a private bucket are configured and tested.
- CI run `45350021055` for branch commit `c0b53d396f9e55968134c8207eb3d0c138ab9411` completed successfully: PostgreSQL-only preview guard, Django checks, migration drift checks, migrations against disposable PostgreSQL, and Student Portal API tests.
- The separate legacy `.github/workflows/portal-api-tests.yml` workflow continues to show a failed invocation with no job records returned by GitHub's jobs endpoint. The dedicated Student Portal preview workflow passes. The legacy workflow is not the authoritative Neon/Django preview check and still needs cleanup/diagnosis.
- No real data has been exported/imported; no Render preview service has been created; Hatchable version 53 remains active; no production cutover or DNS changes have occurred.

### Remaining safe sequence

1. Diagnose the duplicate legacy CI workflow failure and make the intended preview workflow the authoritative check.
2. Add and test a repeatable, idempotent import dry-run using synthetic fixtures only; output source/target counts, orphan and duplicate-FK reports, and quarantine rows for ambiguous exam-session matches.
3. Configure a private non-production R2 bucket and credentials, then test upload/finalize/download with synthetic files only.
4. Configure password-reset email delivery and test with a disposable account.
5. Only after those checks, prepare a separately reviewed real-data export/import plan. No source rows or receipt files are to be imported without the owner's explicit approval.
6. Keep Hatchable running. Do not perform production cutover, production DNS changes, or disable Hatchable.



## Read-only export validator — 2026-11-24

- Added `student_portal/management/commands/audit_hatchable_export.py`. It accepts a complete JSON export of the 21 source tables and performs **no database writes**.
- It checks source-table coverage, row shapes, duplicate IDs, UUID validity, foreign-key orphans and ambiguous exam-attempt/session pairing. It emits only aggregate counts and issue counts, not source email addresses or row contents.
- Synthetic tests cover a valid snapshot, orphan foreign keys, ambiguous exam sessions, duplicate IDs and malformed JSON.
- CI run [45352742552](https://github.com/hackeryoung34-netizen/yscmt-backend/actions/runs/45352742552) passed on commit `ae4eef9db67ecbd3cabeade0219997de5b0b20f3`, including PostgreSQL migrations, portal API/storage tests, and all synthetic export-audit tests. A test-harness issue in the first export-audit test commit was corrected before this passing run.
- Usage after a separately approved source export is available: `python manage.py audit_hatchable_export --input /secure/path/hatchable-export.json`. The command is intentionally audit-only; it does not import records.
