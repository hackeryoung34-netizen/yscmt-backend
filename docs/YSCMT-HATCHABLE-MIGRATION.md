# YSCMT Independent Portal Migration Plan

Status: schema foundation and no-VPS portal preview implemented; data migration and production cutover remain gated.
Target working setup: Vercel static hosting + Supabase Auth/Postgres/RPC + GitHub CI. A privately purchased VPS is not required for the initial portal.
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

## 5. Current external service status (2026-11-14)

- Supabase organization `Community`; project `YSCMT-Student-Portal` is ACTIVE_HEALTHY in `eu-west-3` on the Free plan.
- Supabase migrations 001–004 are applied: 19 public tables and 3 private tables, all 22 with RLS enabled. Browser access to business tables remains denied by default.
- Supabase migrations 005–011 (identity, course reads, pending enrolment, lesson progress, timed exams, Paystack payment, classroom/practice/certificates) are committed to GitHub but not applied.
- Vercel project `yscmtenterprise` has the intended production domains. A separate preview branch `migration/student-portal-preview` has a READY deployment and GitHub static checks pass.
- Vercel SSO protection remains enabled for non-custom preview domains.
- No VPS has been purchased. No production DNS/routing, main website, Hatchable portal, Auth users, or source data have been changed/imported.

## 6. Next gated actions

- Review and explicitly approve the staged RPC migrations before applying them to Supabase.
- Test Auth profile creation only with a disposable account after approval.
- Complete payment activation/reconciliation and full admin workflows; classroom, practice and certificate student workflows are staged, then reconcile source data.
- Do not expose service-role keys, Paystack secret keys, passwords, or private keys in chat or frontend code.
- Keep all paid upgrades and production cutover behind explicit user approval.
