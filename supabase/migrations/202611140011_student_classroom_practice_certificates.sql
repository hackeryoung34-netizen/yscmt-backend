-- Student classroom, practice submission and certificate eligibility RPCs.
create or replace function public.portal_list_classroom_sessions(p_course_id uuid)
returns table (
  id uuid,
  title text,
  description text,
  meeting_url text,
  starts_at timestamptz,
  ends_at timestamptz,
  status text,
  joined_at timestamptz
)
language sql
stable
security definer
set search_path = ''
as $fn$
  select cs.id, cs.title, cs.description, cs.meeting_url,
    cs.starts_at, cs.ends_at, cs.status, ca.joined_at
  from public.classroom_sessions as cs
  join public.enrollments as e on e.course_id = cs.course_id
    and e.user_id = auth.uid()
    and e.status in ('approved','completed')
  join private.user_roles as ur on ur.user_id = auth.uid() and ur.role = 'student'
  left join public.classroom_attendance as ca
    on ca.session_id = cs.id and ca.user_id = auth.uid()
  where cs.course_id = p_course_id
    and cs.status <> 'cancelled'
    and auth.uid() is not null
  order by cs.starts_at desc
  limit 100
$fn$;

create or replace function public.portal_join_classroom_session(p_session_id uuid)
returns table (
  attendance_id uuid,
  joined_at timestamptz
)
language plpgsql
security definer
set search_path = ''
as $fn$
declare
  v_user_id uuid := auth.uid();
  v_attendance_id uuid;
  v_joined_at timestamptz;
begin
  if v_user_id is null then
    raise exception using errcode = '42501', message = 'Authentication is required.';
  end if;
  if not exists (
    select 1 from private.user_roles as ur
    where ur.user_id = v_user_id and ur.role = 'student'
  ) then
    raise exception using errcode = '42501', message = 'Only students may join classroom sessions.';
  end if;
  if not exists (
    select 1
    from public.classroom_sessions as cs
    join public.enrollments as e on e.course_id = cs.course_id
      and e.user_id = v_user_id
      and e.status in ('approved','completed')
    where cs.id = p_session_id
      and cs.status in ('scheduled','live')
      and now() >= cs.starts_at - interval '15 minutes'
      and now() <= cs.ends_at
  ) then
    raise exception using errcode = '42501', message = 'The session is not open to this student.';
  end if;

  insert into public.classroom_attendance (session_id,user_id)
  values (p_session_id,v_user_id)
  on conflict (user_id,session_id) do nothing;

  select ca.id, ca.joined_at into v_attendance_id, v_joined_at
  from public.classroom_attendance as ca
  where ca.session_id = p_session_id and ca.user_id = v_user_id;

  return query select v_attendance_id, v_joined_at;
end;
$fn$;

create or replace function public.portal_list_classroom_messages(p_course_id uuid)
returns table (
  id uuid,
  author_role text,
  message text,
  created_at timestamptz
)
language sql
stable
security definer
set search_path = ''
as $fn$
  select recent.id, recent.author_role, recent.message, recent.created_at
  from (
    select cm.id, cm.author_role, cm.message, cm.created_at
    from public.classroom_messages as cm
    join public.enrollments as e on e.course_id = cm.course_id
      and e.user_id = auth.uid()
      and e.status in ('approved','completed')
    join private.user_roles as ur on ur.user_id = auth.uid() and ur.role = 'student'
    where cm.course_id = p_course_id
      and auth.uid() is not null
    order by cm.created_at desc
    limit 100
  ) as recent
  order by recent.created_at asc
$fn$;

create or replace function public.portal_send_classroom_message(
  p_course_id uuid,
  p_message text
)
returns table (
  id uuid,
  message text,
  created_at timestamptz
)
language plpgsql
security definer
set search_path = ''
as $fn$
declare
  v_user_id uuid := auth.uid();
begin
  if v_user_id is null then
    raise exception using errcode = '42501', message = 'Authentication is required.';
  end if;
  if p_message is null or length(trim(p_message)) < 1 or length(p_message) > 2000 then
    raise exception using errcode = '22023', message = 'Message must contain 1 to 2000 characters.';
  end if;
  if not exists (
    select 1 from private.user_roles as ur
    where ur.user_id = v_user_id and ur.role = 'student'
  ) or not exists (
    select 1 from public.enrollments as e
    where e.course_id = p_course_id
      and e.user_id = v_user_id
      and e.status in ('approved','completed')
  ) then
    raise exception using errcode = '42501', message = 'Approved course enrolment is required.';
  end if;

  return query
  insert into public.classroom_messages (course_id,user_id,author_role,message)
  values (p_course_id,v_user_id,'student',trim(p_message))
  returning public.classroom_messages.id, public.classroom_messages.message,
    public.classroom_messages.created_at;
end;
$fn$;

create or replace function public.portal_list_classroom_announcements(p_course_id uuid)
returns table (
  id uuid,
  course_id uuid,
  title text,
  body text,
  created_at timestamptz
)
language sql
stable
security definer
set search_path = ''
as $fn$
  select ca.id, ca.course_id, ca.title, ca.body, ca.created_at
  from public.classroom_announcements as ca
  join private.user_roles as ur on ur.user_id = auth.uid() and ur.role = 'student'
  where ca.published = true
    and (ca.course_id is null or ca.course_id = p_course_id)
    and auth.uid() is not null
    and (
      ca.course_id is null
      or exists (
        select 1 from public.enrollments as e
        where e.course_id = p_course_id
          and e.user_id = auth.uid()
          and e.status in ('approved','completed')
      )
    )
  order by ca.created_at desc
  limit 100
$fn$;

create or replace function public.portal_list_teacher_replies(p_course_id uuid)
returns table (
  id uuid,
  message text,
  created_at timestamptz
)
language sql
stable
security definer
set search_path = ''
as $fn$
  select tr.id, tr.message, tr.created_at
  from public.classroom_teacher_replies as tr
  join private.user_roles as ur on ur.user_id = auth.uid() and ur.role = 'student'
  where tr.course_id = p_course_id
    and auth.uid() is not null
    and exists (
      select 1 from public.enrollments as e
      where e.course_id = p_course_id
        and e.user_id = auth.uid()
        and e.status in ('approved','completed')
    )
  order by tr.created_at asc
  limit 100
$fn$;

create or replace function public.portal_submit_practice(
  p_lab_key text,
  p_title text,
  p_submission_text text,
  p_project_url text
)
returns table (
  id uuid,
  status text,
  submitted_at timestamptz
)
language plpgsql
security definer
set search_path = ''
as $fn$
declare
  v_user_id uuid := auth.uid();
begin
  if v_user_id is null then
    raise exception using errcode = '42501', message = 'Authentication is required.';
  end if;
  if not exists (
    select 1 from private.user_roles as ur
    where ur.user_id = v_user_id and ur.role = 'student'
  ) then
    raise exception using errcode = '42501', message = 'Only students may submit practice work.';
  end if;
  if p_lab_key is null or length(trim(p_lab_key)) < 1 or length(p_lab_key) > 100
     or p_title is null or length(trim(p_title)) < 1 or length(p_title) > 200
     or coalesce(length(p_submission_text),0) > 5000
     or coalesce(length(p_project_url),0) > 2048
     or (coalesce(p_project_url,'') <> '' and p_project_url not like 'https://%') then
    raise exception using errcode = '22023', message = 'Practice submission fields are invalid.';
  end if;
  if not exists (
    select 1 from public.enrollments as e
    where e.user_id = v_user_id and e.status in ('approved','completed')
  ) then
    raise exception using errcode = '42501', message = 'An approved course enrolment is required.';
  end if;

  return query
  insert into public.practice_submissions (
    user_id,lab_key,title,submission_text,project_url,status
  )
  values (
    v_user_id,trim(p_lab_key),trim(p_title),coalesce(p_submission_text,''),coalesce(p_project_url,''),'submitted'
  )
  returning public.practice_submissions.id, public.practice_submissions.status,
    public.practice_submissions.submitted_at;
end;
$fn$;

create or replace function public.portal_list_my_practice_submissions()
returns table (
  id uuid,
  lab_key text,
  title text,
  submission_text text,
  project_url text,
  status text,
  reviewer_notes text,
  submitted_at timestamptz,
  reviewed_at timestamptz
)
language sql
stable
security definer
set search_path = ''
as $fn$
  select ps.id, ps.lab_key, ps.title, ps.submission_text, ps.project_url,
    ps.status, ps.reviewer_notes, ps.submitted_at, ps.reviewed_at
  from public.practice_submissions as ps
  join private.user_roles as ur on ur.user_id = auth.uid() and ur.role = 'student'
  where ps.user_id = auth.uid()
    and auth.uid() is not null
  order by ps.submitted_at desc
  limit 100
$fn$;

create or replace function public.portal_request_certificate(p_course_id uuid)
returns table (
  id uuid,
  certificate_code text,
  student_name text,
  course_title text,
  issued_at timestamptz
)
language plpgsql
security definer
set search_path = ''
as $fn$
declare
  v_user_id uuid := auth.uid();
  v_student_name text;
  v_course_title text;
  v_certificate public.student_certificates%rowtype;
  v_total_lessons integer;
  v_completed_lessons integer;
begin
  if v_user_id is null then
    raise exception using errcode = '42501', message = 'Authentication is required.';
  end if;
  if not exists (
    select 1 from private.user_roles as ur
    where ur.user_id = v_user_id and ur.role = 'student'
  ) then
    raise exception using errcode = '42501', message = 'Only students may request certificates.';
  end if;

  select c.title, up.full_name
    into v_course_title, v_student_name
  from public.courses as c
  join public.enrollments as e on e.course_id = c.id
    and e.user_id = v_user_id
    and e.status in ('approved','completed')
  join public.user_profiles as up on up.user_id = v_user_id
  where c.id = p_course_id and c.active = true;

  if not found then
    raise exception using errcode = '42501', message = 'Approved course enrolment is required.';
  end if;

  select count(*)::integer, count(lp.lesson_id)::integer
    into v_total_lessons, v_completed_lessons
  from public.course_lessons as l
  left join public.lesson_progress as lp
    on lp.lesson_id = l.id and lp.user_id = v_user_id
  where l.course_id = p_course_id and l.active = true;

  if v_total_lessons = 0 or v_completed_lessons <> v_total_lessons then
    raise exception using errcode = '22023', message = 'Complete all active lessons before requesting a certificate.';
  end if;

  if not exists (
    select 1
    from public.course_exams as ce
    join public.exam_attempts as ea on ea.exam_id = ce.id
      and ea.user_id = v_user_id
      and ea.passed = true
    where ce.course_id = p_course_id
  ) then
    raise exception using errcode = '22023', message = 'Pass a course exam before requesting a certificate.';
  end if;

  insert into public.student_certificates (
    certificate_code,user_id,course_id,student_name,course_title
  )
  values (
    'YSCMT-' || upper(substr(replace(pg_catalog.gen_random_uuid()::text,'-',''),1,12)),
    v_user_id,p_course_id,coalesce(nullif(trim(v_student_name),''),'YSCMT Student'),v_course_title
  )
  on conflict (user_id,course_id) do nothing;

  select sc.* into v_certificate
  from public.student_certificates as sc
  where sc.user_id = v_user_id and sc.course_id = p_course_id;

  return query select v_certificate.id, v_certificate.certificate_code,
    v_certificate.student_name, v_certificate.course_title, v_certificate.issued_at;
end;
$fn$;

create or replace function public.portal_list_my_certificates()
returns table (
  id uuid,
  certificate_code text,
  student_name text,
  course_title text,
  issued_at timestamptz
)
language sql
stable
security definer
set search_path = ''
as $fn$
  select sc.id, sc.certificate_code, sc.student_name, sc.course_title, sc.issued_at
  from public.student_certificates as sc
  join private.user_roles as ur on ur.user_id = auth.uid() and ur.role = 'student'
  where sc.user_id = auth.uid()
    and auth.uid() is not null
  order by sc.issued_at desc
  limit 100
$fn$;

revoke all on function public.portal_list_classroom_sessions(uuid) from public, anon;
revoke all on function public.portal_join_classroom_session(uuid) from public, anon;
revoke all on function public.portal_list_classroom_messages(uuid) from public, anon;
revoke all on function public.portal_send_classroom_message(uuid,text) from public, anon;
revoke all on function public.portal_list_classroom_announcements(uuid) from public, anon;
revoke all on function public.portal_list_teacher_replies(uuid) from public, anon;
revoke all on function public.portal_submit_practice(text,text,text,text) from public, anon;
revoke all on function public.portal_list_my_practice_submissions() from public, anon;
revoke all on function public.portal_request_certificate(uuid) from public, anon;
revoke all on function public.portal_list_my_certificates() from public, anon;

grant execute on function public.portal_list_classroom_sessions(uuid) to authenticated;
grant execute on function public.portal_join_classroom_session(uuid) to authenticated;
grant execute on function public.portal_list_classroom_messages(uuid) to authenticated;
grant execute on function public.portal_send_classroom_message(uuid,text) to authenticated;
grant execute on function public.portal_list_classroom_announcements(uuid) to authenticated;
grant execute on function public.portal_list_teacher_replies(uuid) to authenticated;
grant execute on function public.portal_submit_practice(text,text,text,text) to authenticated;
grant execute on function public.portal_list_my_practice_submissions() to authenticated;
grant execute on function public.portal_request_certificate(uuid) to authenticated;
grant execute on function public.portal_list_my_certificates() to authenticated;
