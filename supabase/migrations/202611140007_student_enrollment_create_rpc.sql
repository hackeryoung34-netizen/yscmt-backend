-- Student self-service enrolment: create pending only, scoped to auth.uid().
-- Staff approval remains a separate trusted admin workflow.
create or replace function public.portal_create_enrollment(p_course_id uuid)
returns table (
  id uuid,
  course_id uuid,
  status text,
  enrolled_at timestamptz
)
language plpgsql
security definer
set search_path = ''
as $function$
declare
  v_user_id uuid := auth.uid();
begin
  if v_user_id is null then
    raise exception using errcode = '42501',
      message = 'Authentication is required.';
  end if;

  if not exists (
    select 1
    from private.user_roles as ur
    where ur.user_id = v_user_id
      and ur.role = 'student'
  ) then
    raise exception using errcode = '42501',
      message = 'Only student accounts may enrol.';
  end if;

  if not exists (
    select 1
    from public.courses as c
    where c.id = p_course_id
      and c.active = true
  ) then
    raise exception using errcode = 'P0002',
      message = 'Active course not found.';
  end if;

  return query
    insert into public.enrollments as e (user_id, course_id, status)
    values (v_user_id, p_course_id, 'pending')
    returning e.id, e.course_id, e.status, e.enrolled_at;
exception
  when unique_violation then
    raise exception using errcode = '23505',
      message = 'An enrolment already exists for this course.';
end;
$function$;

revoke all on function public.portal_create_enrollment(uuid) from public, anon;
grant execute on function public.portal_create_enrollment(uuid) to authenticated;

comment on function public.portal_create_enrollment(uuid) is
  'Creates only a pending enrolment for the authenticated student; never accepts a user ID or status.';
