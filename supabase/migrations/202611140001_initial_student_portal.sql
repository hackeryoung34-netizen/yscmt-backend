-- YSCMT Student Portal initial schema
-- Source inventory: Hatchable schema inspected 2026-11-14.
-- No source data is imported by this migration.
-- Browser clients use Supabase Auth only. All business data access is server-side
-- through a trusted backend; anon/authenticated receive no table privileges.
create extension if not exists pgcrypto;

create schema if not exists private;
revoke all on schema private from public, anon, authenticated;

create table public.user_profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  full_name text not null default '',
  phone text not null default '',
  avatar_url text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table private.legacy_user_map (
  source_system text not null default 'hatchable',
  legacy_user_id text not null,
  auth_user_id uuid not null references auth.users(id) on delete restrict,
  migration_status text not null default 'pending'
    check (migration_status in ('pending','linked','verified','needs_review')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (source_system, legacy_user_id),
  unique (source_system, auth_user_id)
);

create table public.courses (
  id uuid primary key default gen_random_uuid(),
  title text not null unique,
  description text not null default '',
  level text not null default 'Beginner',
  active boolean not null default true,
  created_at timestamptz not null default now(),
  fee_amount numeric not null default 0,
  fee_currency text not null default 'NGN'
);

create table public.enrollments (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete restrict,
  course_id uuid not null references public.courses(id) on delete restrict,
  status text not null default 'pending'
    check (status in ('pending','approved','completed','rejected')),
  enrolled_at timestamptz not null default now(),
  unique (user_id, course_id)
);
create index enrollments_user_idx on public.enrollments(user_id);
create index enrollments_course_status_idx on public.enrollments(course_id,status);

create table public.course_lessons (
  id uuid primary key default gen_random_uuid(),
  course_id uuid not null references public.courses(id) on delete cascade,
  title text not null,
  content text not null default '',
  video_url text not null default '',
  sort_order integer not null default 1,
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index course_lessons_course_order_idx on public.course_lessons(course_id,sort_order,created_at);

create table public.lesson_progress (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  lesson_id uuid not null references public.course_lessons(id) on delete cascade,
  completed_at timestamptz not null default now(),
  unique(user_id,lesson_id)
);
create index lesson_progress_user_idx on public.lesson_progress(user_id,completed_at);

create table public.course_exams (
  id uuid primary key default gen_random_uuid(),
  course_id uuid not null references public.courses(id) on delete cascade,
  title text not null,
  instructions text not null default '',
  duration_minutes integer not null default 30 check(duration_minutes > 0),
  pass_mark integer not null default 50 check(pass_mark between 0 and 100),
  active boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index course_exams_course_idx on public.course_exams(course_id,active);

create table public.exam_questions (
  id uuid primary key default gen_random_uuid(),
  exam_id uuid not null references public.course_exams(id) on delete cascade,
  question_text text not null,
  options jsonb not null,
  correct_option integer not null check(correct_option between 0 and 3),
  sort_order integer not null default 1,
  created_at timestamptz not null default now()
);
create index exam_questions_exam_order_idx on public.exam_questions(exam_id,sort_order);

create table public.exam_sessions (
  id uuid primary key default gen_random_uuid(),
  exam_id uuid not null references public.course_exams(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  started_at timestamptz not null default now(),
  submitted_at timestamptz,
  unique(id,user_id)
);
create index exam_sessions_user_exam_idx on public.exam_sessions(user_id,exam_id,started_at);

create table public.exam_attempts (
  id uuid primary key default gen_random_uuid(),
  exam_id uuid not null references public.course_exams(id) on delete restrict,
  user_id uuid not null references auth.users(id) on delete cascade,
  answers jsonb not null default '{}'::jsonb,
  score integer not null default 0 check(score between 0 and 100),
  passed boolean not null default false,
  started_at timestamptz not null default now(),
  submitted_at timestamptz not null default now()
);
create index exam_attempts_user_exam_idx on public.exam_attempts(user_id,exam_id,submitted_at);

create table public.student_certificates (
  id uuid primary key default gen_random_uuid(),
  certificate_code text not null unique,
  user_id uuid not null references auth.users(id) on delete restrict,
  course_id uuid not null references public.courses(id) on delete restrict,
  student_name text not null,
  course_title text not null,
  issued_at timestamptz not null default now(),
  unique(user_id,course_id)
);
create index student_certificates_code_idx on public.student_certificates(certificate_code);

create table public.payment_submissions (
  id uuid primary key default gen_random_uuid(),
  enrolment_id uuid not null references public.enrollments(id) on delete restrict,
  user_id uuid not null references auth.users(id) on delete restrict,
  course_id uuid not null references public.courses(id) on delete restrict,
  amount numeric not null check(amount >= 0),
  currency text not null default 'NGN',
  transfer_reference text not null default '',
  storage_key text not null,
  content_type text not null,
  file_name text not null default '',
  status text not null default 'pending' check(status in ('pending','approved','rejected')),
  admin_note text not null default '',
  submitted_at timestamptz not null default now(),
  reviewed_at timestamptz
);
create index payment_submissions_status_idx on public.payment_submissions(status,submitted_at);
create index payment_submissions_enrolment_idx on public.payment_submissions(enrolment_id,submitted_at);

create table public.paystack_payments (
  id uuid primary key default gen_random_uuid(),
  enrolment_id uuid not null references public.enrollments(id) on delete restrict,
  user_id uuid not null references auth.users(id) on delete restrict,
  course_id uuid not null references public.courses(id) on delete restrict,
  reference text not null unique,
  amount_kobo bigint not null check(amount_kobo > 0),
  currency text not null default 'NGN',
  status text not null default 'pending' check(status in ('pending','success','failed','abandoned')),
  authorization_url text not null default '',
  gateway_response jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  verified_at timestamptz
);
create index paystack_payments_enrolment_idx on public.paystack_payments(enrolment_id,created_at);
create index paystack_payments_status_idx on public.paystack_payments(status,created_at);
create index paystack_payments_user_idx on public.paystack_payments(user_id,created_at);

create table public.practice_submissions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  lab_key text not null,
  title text not null,
  submission_text text not null default '',
  project_url text not null default '',
  status text not null default 'submitted' check(status in ('submitted','reviewing','approved','rejected')),
  reviewer_notes text not null default '',
  reviewed_by uuid references auth.users(id) on delete set null,
  submitted_at timestamptz not null default now(),
  reviewed_at timestamptz
);
create index practice_submissions_status_idx on public.practice_submissions(status,submitted_at);
create index practice_submissions_user_idx on public.practice_submissions(user_id,submitted_at);

create table public.classroom_sessions (
  id uuid primary key default gen_random_uuid(),
  course_id uuid not null references public.courses(id) on delete cascade,
  title text not null,
  description text not null default '',
  meeting_url text not null,
  starts_at timestamptz not null,
  ends_at timestamptz not null,
  status text not null default 'scheduled' check(status in ('scheduled','live','completed','cancelled')),
  created_by uuid references auth.users(id) on delete restrict,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check(ends_at > starts_at)
);
create index classroom_sessions_course_start_idx on public.classroom_sessions(course_id,starts_at);

create table public.classroom_attendance (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.classroom_sessions(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  joined_at timestamptz not null default now(),
  unique(user_id,session_id)
);
create index classroom_attendance_session_idx on public.classroom_attendance(session_id);

create table public.classroom_messages (
  id uuid primary key default gen_random_uuid(),
  course_id uuid not null references public.courses(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  author_role text not null default 'student' check(author_role in ('student','instructor','admin')),
  message text not null,
  created_at timestamptz not null default now()
);
create index classroom_messages_course_date_idx on public.classroom_messages(course_id,created_at);

create table public.classroom_announcements (
  id uuid primary key default gen_random_uuid(),
  course_id uuid references public.courses(id) on delete cascade,
  title text not null,
  body text not null,
  published boolean not null default true,
  created_by uuid references auth.users(id) on delete restrict,
  created_at timestamptz not null default now()
);
create index classroom_announcements_course_date_idx on public.classroom_announcements(course_id,created_at);

create table public.classroom_teacher_replies (
  id uuid primary key default gen_random_uuid(),
  course_id uuid not null references public.courses(id) on delete cascade,
  created_by uuid not null references auth.users(id) on delete restrict,
  message text not null,
  created_at timestamptz not null default now()
);
create index classroom_teacher_replies_course_date_idx on public.classroom_teacher_replies(course_id,created_at);

create table public.admin_audit_logs (
  id bigint generated by default as identity primary key,
  actor_user_id uuid references auth.users(id) on delete set null,
  actor_handle text not null,
  action text not null,
  target_type text not null,
  target_id text,
  details jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index admin_audit_logs_created_at_idx on public.admin_audit_logs(created_at desc);

create table private.site_settings (
  setting_key text primary key,
  setting_value jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

-- RLS on every exposed public application table.
do $$
declare t text;
begin
  foreach t in array array[
    'user_profiles','courses','enrollments','course_lessons','lesson_progress',
    'course_exams','exam_questions','exam_sessions','exam_attempts',
    'student_certificates','payment_submissions','paystack_payments',
    'practice_submissions','classroom_sessions','classroom_attendance',
    'classroom_messages','classroom_announcements','classroom_teacher_replies',
    'admin_audit_logs'
  ] loop
    execute format('alter table public.%I enable row level security',t);
  end loop;
end $$;

-- No direct browser access to business tables. The trusted backend will use
-- a server-side secret key and enforce student/instructor/admin authorization.
revoke all on all tables in schema public from anon, authenticated;
grant select, update on public.user_profiles to authenticated;
create policy "users_read_own_profile" on public.user_profiles
  for select to authenticated using (user_id = (select auth.uid()));
create policy "users_update_own_profile" on public.user_profiles
  for update to authenticated using (user_id = (select auth.uid()))
  with check (user_id = (select auth.uid()));

-- Internal mapping/settings are inaccessible to API roles.
revoke all on all tables in schema private from public, anon, authenticated;
