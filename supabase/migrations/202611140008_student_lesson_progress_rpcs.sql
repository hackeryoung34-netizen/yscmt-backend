-- Self-scoped lesson completion and course progress for enrolled students.
create or replace function public.portal_mark_lesson_complete(p_lesson_id uuid)
returns table (
  lesson_id uuid,
  completed_at timestamptz
)
language plpgsql
security definer
set search_path = ''
as $function$
declare
  v_user_id uuid := auth.uid();
  v_completed_at timestamptz;
begin
  if v_user_id is null then
    raise exception using errcode = '42501',
      message = 'Authentication is required.';
  end if;

  if not exists (
    select 1 from private.user_roles as ur
    where ur.user_id = v_user_id and ur.role = 'student'
  ) then
    raise exception using errcode = '42501',
      message = 'Only student accounts may update lesson progress.';
  end if;

  if not exists (
    select 1
    from public.course_lessons as l
    join public.courses as c on c.id = l.course_id and c.active = true
    join public.enrollments as e on e.course_id = c.id
      and e.user_id = v_user_id
      and e.status in ('approved', 'completed')
    where l.id = p_lesson_id and l.active = true
  ) then
    raise exception using errcode = '42501',
      message = 'An approved course enrolment is required for this lesson.';
  end if;

  insert into public.lesson_progress (user_id, lesson_id, completed_at)
  values (v_user_id, p_lesson_id, now())
  on conflict (user_id, lesson_id) do nothing;

  select lp.completed_at into v_completed_at
  from public.lesson_progress as lp
  where lp.user_id = v_user_id and lp.lesson_id = p_lesson_id;

  return query select p_lesson_id, v_completed_at;
end;
$function$;

create or replace function public.portal_get_my_course_progress(p_course_id uuid)
returns table (
  total_lessons integer,
  completed_lessons integer,
  progress_percent integer
)
language sql
stable
security definer
set search_path = ''
as $function$
  select
    count(l.id)::integer as total_lessons,
    count(lp.lesson_id)::integer as completed_lessons,
    case
      when count(l.id) = 0 then 0
      else round((count(lp.lesson_id)::numeric * 100) / count(l.id))::integer
    end as progress_percent
  from public.courses as c
  join public.enrollments as e
    on e.course_id = c.id
   and e.user_id = auth.uid()
   and e.status in ('approved', 'completed')
  join private.user_roles as ur
    on ur.user_id = auth.uid()
   and ur.role = 'student'
  left join public.course_lessons as l
    on l.course_id = c.id and l.active = true
  left join public.lesson_progress as lp
    on lp.lesson_id = l.id and lp.user_id = auth.uid()
  where c.id = p_course_id
    and c.active = true
    and auth.uid() is not null
  group by c.id
$function$;

revoke all on function public.portal_mark_lesson_complete(uuid) from public, anon;
revoke all on function public.portal_get_my_course_progress(uuid) from public, anon;
grant execute on function public.portal_mark_lesson_complete(uuid) to authenticated;
grant execute on function public.portal_get_my_course_progress(uuid) to authenticated;

comment on function public.portal_mark_lesson_complete(uuid) is
  'Marks one active lesson complete for the authenticated student with an approved/completed enrolment; idempotent.';
comment on function public.portal_get_my_course_progress(uuid) is
  'Returns only the authenticated student lesson completion counts for one enrolled course.';
