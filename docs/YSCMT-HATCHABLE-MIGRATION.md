# YSCMT Independent Portal Migration Plan

Status: discovery completed; migration not yet performed.
Target working setup: GitHub Codespaces (phone-accessible development), Supabase (database/auth), Vercel (web hosting).
The Hatchable portal remains live as the rollback source until the replacement is verified.

## 1. Current source inventory

- Hatchable project: YSCMT Student Portal
- Project ID: proj_wtjM5VcpGROw
- Current deployment version observed: 47
- Files observed: 72
- API routes observed: 31
- PostgreSQL tables observed: 21

### Live row-count snapshot (read-only query)

| Table | Rows |
|---|---:|
| users | 4 |
| student_profiles | 0 |
| courses | 4 |
| enrollments | 0 |
| course_lessons | 16 |
| lesson_progress | 0 |
| course_exams | 4 |
| exam_questions | 40 |
| exam_attempts | 0 |
| exam_sessions | 0 |
| student_certificates | 0 |
| payment_submissions | 0 |
| paystack_payments | 2 |
| practice_submissions | 0 |
| classroom_sessions | 0 |
| classroom_attendance | 0 |
| classroom_messages | 0 |
| classroom_announcements | 0 |
| classroom_teacher_replies | 0 |
| admin_audit_logs | 20 |
| site_settings | 1 |

These are a point-in-time counts only; re-check immediately before export/import.

## 2. Existing code that may be reused

- Frontend repository: hackeryoung34-netizen/yscmt-react (React 19 + Vite 6 + TypeScript).
- Backend repository: hackeryoung34-netizen/yscmt-backend (Django 6 + DRF + SimpleJWT).
- The frontend already contains LMS and admin route components.
- The backend already has Django apps for accounts, courses, lessons, enrolments, certificates, payments, quizzes, quiz attempts, dashboard and progress.

Do not assume the existing generic LMS frontend/backend already reproduces every Hatchable Student Portal workflow. Map each feature and test it before switching traffic.

## 3. Security blockers found in existing Django settings

The inspected settings file currently:
- Falls back to a hard-coded SECRET_KEY if the environment variable is absent.
- Defaults DEBUG to True.
- Sets DRF's global default permission class to AllowAny.
- Falls back to SQLite if DATABASE_URL is not configured.

Before any public deployment:
1. Require a strong SECRET_KEY from server environment; fail startup if missing.
2. Set DEBUG=False in production.
3. Make authentication/permissions explicit per API endpoint; do not rely on AllowAny defaults for private student/admin data.
4. Require PostgreSQL in production and configure allowed hosts, CORS and CSRF for the actual domains.
5. Keep all Paystack secret keys server-side; never place them in frontend environment variables.

## 4. Migration sequence

1. Preserve Hatchable and take a verified export/backup of its database and uploaded files.
2. Map all 21 source tables and 31 routes to the destination schema and Django endpoints.
3. Decide whether Supabase Auth or Django JWT is the single identity provider. Avoid running two competing auth systems.
4. Create destination schema with row-level access controls / server-side authorization.
5. Import data in dependency order, preserving source IDs and timestamps where possible.
6. Migrate authentication carefully. Never copy password hashes unless compatibility is proven; otherwise require secure password reset / account re-verification.
7. Rebuild and test student login, admin login, courses, lessons, enrolments, exams, payments, certificates, practice and classroom.
8. Compare row counts and representative records; verify payment reconciliation and certificate verification.
9. Test on a preview domain first. Switch the production domain only after explicit approval.
10. Keep Hatchable available for rollback until the new system has passed acceptance testing.

## 5. Current external service status observed

- Supabase connector currently lists no projects.
- Vercel project "yscmtenterprise" exists and has the intended domain names attached.
- The Vercel project reports SSO protection enabled for non-custom domains; verify access settings before preview testing.
- No DNS changes, production deploys, Hatchable edits, or data writes were made during discovery.

## 6. Next gated actions

- Confirm the Supabase organization and accept any quoted project cost before creating a database project.
- Create a separate migration/staging branch and preview environment.
- Do not expose service-role keys, Paystack secret keys, passwords, or private keys in chat or frontend code.
