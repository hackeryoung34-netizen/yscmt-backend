-- Secure student exam catalogue, timed sessions, question delivery and scoring.
-- Correct answer keys never leave Postgres.
alter table public.exam_attempts
  add column if not exists exam_session_id uuid
  references public.exam_sessions(id) on delete restrict;

create unique index if not exists exam_attempts_session_unique
  on public.exam_attempts(exam_session_id)
  where exam_session_id is not null;

create unique index if not exists exam_sessions_one_active_per_student_exam
  on public.exam_sessions(exam_id, user_id)
  where submitted_at is null;

create or replace function public.portal_list_course_exams(p_course_id uuid)
returns table (
  id uuid,
  title text,
  instructions text,
  duration_minutes integer,
  pass_mark integer
)
language sql
stable
security definer
set search_path = ''
as $function$
  select ce.id, ce.title, ce.instructions, ce.duration_minutes, ce.pass_mark
  from public.course_exams as ce
  join public.courses as c on c.id = ce.course_id and c.active = true
  join public.enrollments as e on e.course_id = c.id
    and e.user_id = auth.uid()
    and e.status in ('approved', 'completed')
  join private.user_roles as ur on ur.user_id = auth.uid() and ur.role = 'student'
  where ce.course_id = p_course_id
    and ce.active = true
    and auth.uid() is not null
  order by ce.created_at asc, ce.title asc
  limit 50
$function$;

create or replace function public.portal_start_exam(p_exam_id uuid)
returns table (
  session_id uuid,
  started_at timestamptz,
  expires_at timestamptz
)
language plpgsql
security definer
set search_path = ''
as $function$
declare
  v_user_id uuid := auth.uid();
  v_duration integer;
  v_session_id uuid;
  v_started_at timestamptz;
begin
  if v_user_id is null then
    raise exception using errcode = '42501', message = 'Authentication is required.';
  end if;

  if not exists (
    select 1 from private.user_roles as ur
    where ur.user_id = v_user_id and ur.role = 'student'
  ) then
    raise exception using errcode = '42501', message = 'Only students may start exams.';
  end if;

  select ce.duration_minutes into v_duration
  from public.course_exams as ce
  join public.courses as c on c.id = ce.course_id and c.active = true
  join public.enrollments as e on e.course_id = c.id
    and e.user_id = v_user_id
    and e.status in ('approved', 'completed')
  where ce.id = p_exam_id
    and ce.active = true
    and (select count(*) from public.exam_questions as q where q.exam_id = ce.id) between 1 and 100;

  if not found then
    raise exception using errcode = 'P0002', message = 'Active exam not found for an approved enrolment.';
  end if;

  select es.id, es.started_at
    into v_session_id, v_started_at
  from public.exam_sessions as es
  where es.exam_id = p_exam_id
    and es.user_id = v_user_id
    and es.submitted_at is null
  for update;

  if found and now() < v_started_at + make_interval(mins => v_duration) then
    return query select v_session_id, v_started_at,
      v_started_at + make_interval(mins => v_duration);
    return;
  end if;

  if found then
    update public.exam_sessions
    set submitted_at = now()
    where id = v_session_id and user_id = v_user_id and submitted_at is null;
  end if;

  begin
    insert into public.exam_sessions as es (exam_id, user_id, started_at)
    values (p_exam_id, v_user_id, now())
    returning es.id, es.started_at
      into v_session_id, v_started_at;
  exception when unique_violation then
    select es.id, es.started_at
      into v_session_id, v_started_at
    from public.exam_sessions as es
    where es.exam_id = p_exam_id
      and es.user_id = v_user_id
      and es.submitted_at is null;
  end;

  return query select v_session_id, v_started_at,
    v_started_at + make_interval(mins => v_duration);
end;
$function$;

create or replace function public.portal_get_exam_questions(p_session_id uuid)
returns table (
  id uuid,
  question_text text,
  options jsonb,
  sort_order integer
)
language sql
stable
security definer
set search_path = ''
as $function$
  select q.id, q.question_text, q.options, q.sort_order
  from public.exam_sessions as es
  join public.course_exams as ce on ce.id = es.exam_id
  join public.courses as c on c.id = ce.course_id and c.active = true
  join public.enrollments as e on e.course_id = c.id
    and e.user_id = auth.uid()
    and e.status in ('approved', 'completed')
  join private.user_roles as ur on ur.user_id = auth.uid() and ur.role = 'student'
  join public.exam_questions as q on q.exam_id = ce.id
  where es.id = p_session_id
    and es.user_id = auth.uid()
    and es.submitted_at is null
    and now() < es.started_at + make_interval(mins => ce.duration_minutes)
    and ce.active = true
    and auth.uid() is not null
  order by q.sort_order asc, q.created_at asc
  limit 100
$function$;

create or replace function public.portal_submit_exam(
  p_session_id uuid,
  p_answers jsonb
)
returns table (
  attempt_id uuid,
  score integer,
  passed boolean,
  submitted_at timestamptz
)
language plpgsql
security definer
set search_path = ''
as $function$
declare
  v_user_id uuid := auth.uid();
  v_session public.exam_sessions%rowtype;
  v_duration integer;
  v_pass_mark integer;
  v_question_count integer;
  v_answer_count integer;
  v_correct_count integer;
  v_score integer;
  v_passed boolean;
  v_attempt_id uuid;
  v_submitted_at timestamptz := now();
begin
  if v_user_id is null then
    raise exception using errcode = '42501', message = 'Authentication is required.';
  end if;

  if p_answers is null or jsonb_typeof(p_answers) <> 'object'
     or octet_length(p_answers::text) > 65536 then
    raise exception using errcode = '22023', message = 'Answers must be a JSON object.';
  end if;

  if not exists (
    select 1 from private.user_roles as ur
    where ur.user_id = v_user_id and ur.role = 'student'
  ) then
    raise exception using errcode = '42501', message = 'Only students may submit exams.';
  end if;

  select es.* into v_session
  from public.exam_sessions as es
  where es.id = p_session_id and es.user_id = v_user_id
  for update;

  if not found then
    raise exception using errcode = '42501', message = 'Exam session not found for this account.';
  end if;

  if v_session.submitted_at is not null then
    select ea.id, ea.score, ea.passed, ea.submitted_at
      into v_attempt_id, v_score, v_passed, v_submitted_at
    from public.exam_attempts as ea
    where ea.exam_session_id = v_session.id;
    if found then
      return query select v_attempt_id, v_score, v_passed, v_submitted_at;
      return;
    end if;
    raise exception using errcode = '22023', message = 'This exam session is already closed.';
  end if;

  select ce.duration_minutes, ce.pass_mark
    into v_duration, v_pass_mark
  from public.course_exams as ce
  where ce.id = v_session.exam_id;

  if not found then
    raise exception using errcode = 'P0002', message = 'Exam not found.';
  end if;

  if now() >= v_session.started_at + make_interval(mins => v_duration) then
    -- A timeout is a completed failed attempt, not an exception: raising here
    -- would roll back the session update and leave the session open.
    insert into public.exam_attempts (
      exam_session_id, exam_id, user_id, answers, score, passed, started_at, submitted_at
    )
    values (
      v_session.id, v_session.exam_id, v_user_id, '{}'::jsonb,
      0, false, v_session.started_at, v_submitted_at
    )
    returning id into v_attempt_id;

    update public.exam_sessions
    set submitted_at = v_submitted_at
    where id = v_session.id and user_id = v_user_id;

    return query select v_attempt_id, 0, false, v_submitted_at;
    return;
  end if;

  if not exists (
    select 1
    from public.course_exams as ce
    join public.courses as c on c.id = ce.course_id and c.active = true
    join public.enrollments as e on e.course_id = ce.course_id
      and e.user_id = v_user_id
      and e.status in ('approved', 'completed')
    where ce.id = v_session.exam_id
  ) then
    raise exception using errcode = '42501', message = 'Approved course enrolment is required.';
  end if;

  select count(*)::integer into v_question_count
  from public.exam_questions as q
  where q.exam_id = v_session.exam_id;

  select count(*)::integer into v_answer_count
  from jsonb_object_keys(p_answers);

  if v_question_count = 0 or v_question_count > 100 or v_answer_count <> v_question_count then
    raise exception using errcode = '22023', message = 'Submit one answer for every exam question.';
  end if;

  if exists (
    select 1 from jsonb_each(p_answers) as a(key, value)
    where jsonb_typeof(a.value) <> 'number'
       or (a.value #>> '{}') !~ '^[0-3]$'
  ) then
    raise exception using errcode = '22023', message = 'Each answer must be an option number from 0 to 3.';
  end if;

  if exists (
    select 1
    from jsonb_object_keys(p_answers) as a(question_id)
    where not exists (
      select 1 from public.exam_questions as q
      where q.exam_id = v_session.exam_id and q.id::text = a.question_id
    )
  ) then
    raise exception using errcode = '22023', message = 'Answers contain a question outside this exam.';
  end if;

  select count(*)::integer into v_correct_count
  from public.exam_questions as q
  join jsonb_each_text(p_answers) as a(key, value)
    on a.key = q.id::text
  where q.exam_id = v_session.exam_id
    and a.value::integer = q.correct_option;

  v_score := round((v_correct_count::numeric * 100) / v_question_count)::integer;
  v_passed := v_score >= v_pass_mark;

  insert into public.exam_attempts (
    exam_session_id, exam_id, user_id, answers, score, passed, started_at, submitted_at
  )
  values (
    v_session.id, v_session.exam_id, v_user_id, p_answers,
    v_score, v_passed, v_session.started_at, v_submitted_at
  )
  returning id into v_attempt_id;

  update public.exam_sessions
  set submitted_at = v_submitted_at
  where id = v_session.id and user_id = v_user_id;

  return query select v_attempt_id, v_score, v_passed, v_submitted_at;
end;
$function$;

revoke all on function public.portal_list_course_exams(uuid) from public, anon;
revoke all on function public.portal_start_exam(uuid) from public, anon;
revoke all on function public.portal_get_exam_questions(uuid) from public, anon;
revoke all on function public.portal_submit_exam(uuid, jsonb) from public, anon;
grant execute on function public.portal_list_course_exams(uuid) to authenticated;
grant execute on function public.portal_start_exam(uuid) to authenticated;
grant execute on function public.portal_get_exam_questions(uuid) to authenticated;
grant execute on function public.portal_submit_exam(uuid, jsonb) to authenticated;

comment on function public.portal_list_course_exams(uuid) is
  'Lists active exam metadata only for an authenticated student enrolled in the course.';
comment on function public.portal_start_exam(uuid) is
  'Creates or resumes one timed exam session for the authenticated enrolled student.';
comment on function public.portal_get_exam_questions(uuid) is
  'Returns question text and options only; correct_option is never returned.';
comment on function public.portal_submit_exam(uuid, jsonb) is
  'Scores answers in Postgres, persists one idempotent attempt per session, and never exposes answer keys.';
