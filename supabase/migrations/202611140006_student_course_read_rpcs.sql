-- Student course catalogue and lesson access through narrow, self-scoped RPCs.
-- No table grants are added for browser roles; business tables remain server-only.

create or replace function public.portal_list_courses()
returns table (
  id uuid,
  title text,
  description text,
  level text,
  fee_amount numeric,
  fee_currency text,
  enrollment_status text
)
language sql
stable
security definer
set search_path = ''
as $$
  select
    c.id,
    c.title,
    c.description,
    c.level,
    c.fee_amount,
    c.fee_currency,
    e.status
  from public.courses as c
  left join public.enrollments as e
    on e.course_id = c.id
   and e.user_id = auth.uid()
  where c.active = true
    and auth.uid() is not null
    and exists (
      select 1
      from private.user_roles as ur
      where ur.user_id = auth.uid()
        and ur.role = 'student'
    )
  order by c.created_at desc, c.title asc
$$;

create or replace function public.portal_get_course_detail(p_course_id uuid)
returns table (
  id uuid,
  title text,
  description text,
  level text,
  fee_amount numeric,
  fee_currency text,
  enrollment_status text
)
language sql
stable
security definer
set search_path = ''
as $$
  select
    c.id,
    c.title,
    c.description,
    c.level,
    c.fee_amount,
    c.fee_currency,
    e.status
  from public.courses as c
  left join public.enrollments as e
    on e.course_id = c.id
   and e.user_id = auth.uid()
  where c.id = p_course_id
    and c.active = true
    and auth.uid() is not null
    and exists (
      select 1
      from private.user_roles as ur
      where ur.user_id = auth.uid()
        and ur.role = 'student'
    )
$$;

create or replace function public.portal_get_course_lessons(p_course_id uuid)
returns table (
  id uuid,
  title text,
  content text,
  video_url text,
  sort_order integer,
  completed_at timestamptz
)
language sql
stable
security definer
set search_path = ''
as $$
  select
    l.id,
    l.title,
    l.content,
    l.video_url,
    l.sort_order,
    lp.completed_at
  from public.course_lessons as l
  join public.courses as c
    on c.id = l.course_id
   and c.active = true
  join public.enrollments as e
    on e.course_id = c.id
   and e.user_id = auth.uid()
   and e.status in ('approved', 'completed')
  join private.user_roles as ur
    on ur.user_id = auth.uid()
   and ur.role = 'student'
  left join public.lesson_progress as lp
    on lp.lesson_id = l.id
   and lp.user_id = auth.uid()
  where l.course_id = p_course_id
    and l.active = true
    and auth.uid() is not null
  order by l.sort_order asc, l.created_at asc
$$;

revoke all on function public.portal_list_courses() from public, anon;
revoke all on function public.portal_get_course_detail(uuid) from public, anon;
revoke all on function public.portal_get_course_lessons(uuid) from public, anon;
grant execute on function public.portal_list_courses() to authenticated;
grant execute on function public.portal_get_course_detail(uuid) to authenticated;
grant execute on function public.portal_get_course_lessons(uuid) to authenticated;

comment on function public.portal_list_courses() is
  'Lists active courses for the authenticated student and only that student enrollment status.';
comment on function public.portal_get_course_detail(uuid) is
  'Returns one active course and the caller enrollment status for authenticated students.';
comment on function public.portal_get_course_lessons(uuid) is
  'Returns active lesson content only for the authenticated student with approved or completed enrollment.';
