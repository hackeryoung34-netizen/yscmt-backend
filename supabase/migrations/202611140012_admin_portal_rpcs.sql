-- Admin-only management RPCs. Authorization comes only from private.user_roles.
create or replace function public.portal_admin_overview()
returns table (
  students_count bigint,
  active_courses_count bigint,
  enrollments_count bigint,
  pending_enrollments_count bigint,
  pending_bank_payments_count bigint,
  pending_paystack_count bigint,
  submitted_practice_count bigint,
  certificates_count bigint
)
language sql
stable
security definer
set search_path = ''
as $fn$
  select
    (select count(*) from private.user_roles as r where r.role = 'student'),
    (select count(*) from public.courses as c where c.active = true),
    (select count(*) from public.enrollments),
    (select count(*) from public.enrollments as e where e.status = 'pending'),
    (select count(*) from public.payment_submissions as p where p.status = 'pending'),
    (select count(*) from public.paystack_payments as p where p.status = 'pending'),
    (select count(*) from public.practice_submissions as p where p.status = 'submitted'),
    (select count(*) from public.student_certificates)
  where exists (
    select 1 from private.user_roles as ur
    where ur.user_id = auth.uid() and ur.role = 'admin'
  )
$fn$;

create or replace function public.portal_admin_list_students(p_limit integer default 50)
returns table (
  user_id uuid,
  email text,
  full_name text,
  phone text,
  role text,
  created_at timestamptz,
  enrollment_count bigint
)
language sql
stable
security definer
set search_path = ''
as $fn$
  select au.id, au.email, up.full_name, up.phone, ur.role,
    up.created_at, count(e.id)::bigint
  from auth.users as au
  join private.user_roles as ur on ur.user_id = au.id and ur.role = 'student'
  left join public.user_profiles as up on up.user_id = au.id
  left join public.enrollments as e on e.user_id = au.id
  where exists (
    select 1 from private.user_roles as admin_role
    where admin_role.user_id = auth.uid() and admin_role.role = 'admin'
  )
  group by au.id, au.email, up.full_name, up.phone, ur.role, up.created_at
  order by up.created_at desc
  limit greatest(1, least(coalesce(p_limit,50),100))
$fn$;

create or replace function public.portal_admin_list_enrollments(
  p_status text default null,
  p_limit integer default 100
)
returns table (
  enrollment_id uuid,
  user_id uuid,
  email text,
  student_name text,
  course_id uuid,
  course_title text,
  status text,
  enrolled_at timestamptz
)
language sql
stable
security definer
set search_path = ''
as $fn$
  select e.id, e.user_id, au.email, up.full_name,
    e.course_id, c.title, e.status, e.enrolled_at
  from public.enrollments as e
  join auth.users as au on au.id = e.user_id
  left join public.user_profiles as up on up.user_id = e.user_id
  join public.courses as c on c.id = e.course_id
  where (p_status is null or e.status = p_status)
    and exists (
      select 1 from private.user_roles as ur
      where ur.user_id = auth.uid() and ur.role = 'admin'
    )
  order by e.enrolled_at desc
  limit greatest(1, least(coalesce(p_limit,100),200))
$fn$;

create or replace function public.portal_admin_review_enrollment(
  p_enrollment_id uuid,
  p_status text,
  p_note text default ''
)
returns table (
  enrollment_id uuid,
  status text,
  updated_at timestamptz
)
language plpgsql
security definer
set search_path = ''
as $fn$
declare
  v_admin_id uuid := auth.uid();
  v_enrollment public.enrollments%rowtype;
  v_actor_handle text;
  v_total integer;
  v_completed integer;
begin
  if v_admin_id is null or not exists (
    select 1 from private.user_roles as ur
    where ur.user_id = v_admin_id and ur.role = 'admin'
  ) then
    raise exception using errcode = '42501', message = 'Administrator access is required.';
  end if;
  if p_status not in ('approved','rejected','completed')
     or coalesce(length(p_note),0) > 2000 then
    raise exception using errcode = '22023', message = 'Invalid enrolment review details.';
  end if;

  select e.* into v_enrollment
  from public.enrollments as e
  where e.id = p_enrollment_id
  for update;
  if not found then
    raise exception using errcode = 'P0002', message = 'Enrolment not found.';
  end if;
  if v_enrollment.user_id = v_admin_id then
    raise exception using errcode = '42501', message = 'An administrator cannot review their own enrolment.';
  end if;
  if v_enrollment.status = 'completed' and p_status <> 'completed' then
    raise exception using errcode = '22023', message = 'A completed enrolment cannot be downgraded.';
  end if;

  if p_status = 'completed' then
    select count(*)::integer, count(lp.lesson_id)::integer
      into v_total, v_completed
    from public.course_lessons as l
    left join public.lesson_progress as lp
      on lp.lesson_id = l.id and lp.user_id = v_enrollment.user_id
    where l.course_id = v_enrollment.course_id and l.active = true;
    if v_total = 0 or v_completed <> v_total or not exists (
      select 1 from public.course_exams as ce
      join public.exam_attempts as ea on ea.exam_id = ce.id
        and ea.user_id = v_enrollment.user_id and ea.passed = true
      where ce.course_id = v_enrollment.course_id
    ) then
      raise exception using errcode = '22023',
        message = 'The student must complete all active lessons and pass an exam before completion.';
    end if;
  end if;

  select coalesce(nullif(trim(up.full_name),''),au.email,'YSCMT Admin')
    into v_actor_handle
  from auth.users as au
  left join public.user_profiles as up on up.user_id = au.id
  where au.id = v_admin_id;

  update public.enrollments
  set status = p_status
  where id = p_enrollment_id;

  insert into public.admin_audit_logs (
    actor_user_id,actor_handle,action,target_type,target_id,details
  ) values (
    v_admin_id,coalesce(v_actor_handle,'YSCMT Admin'),'enrollment.review','enrollment',
    p_enrollment_id::text,
    jsonb_build_object('from',v_enrollment.status,'to',p_status,'note',coalesce(p_note,''))
  );

  return query select p_enrollment_id,p_status,now();
end;
$fn$;

create or replace function public.portal_admin_list_paystack_payments()
returns table (
  id uuid,
  reference text,
  student_email text,
  student_name text,
  course_title text,
  amount_kobo bigint,
  currency text,
  status text,
  created_at timestamptz,
  verified_at timestamptz
)
language sql
stable
security definer
set search_path = ''
as $fn$
  select pp.id,pp.reference,au.email,up.full_name,c.title,
    pp.amount_kobo,pp.currency,pp.status,pp.created_at,pp.verified_at
  from public.paystack_payments as pp
  join auth.users as au on au.id = pp.user_id
  left join public.user_profiles as up on up.user_id = pp.user_id
  join public.courses as c on c.id = pp.course_id
  where exists (
    select 1 from private.user_roles as ur
    where ur.user_id = auth.uid() and ur.role = 'admin'
  )
  order by pp.created_at desc
  limit 200
$fn$;

create or replace function public.portal_admin_list_payment_submissions()
returns table (
  id uuid,
  enrollment_id uuid,
  user_id uuid,
  student_email text,
  student_name text,
  course_title text,
  amount numeric,
  currency text,
  transfer_reference text,
  storage_key text,
  content_type text,
  file_name text,
  status text,
  admin_note text,
  submitted_at timestamptz,
  reviewed_at timestamptz
)
language sql
stable
security definer
set search_path = ''
as $fn$
  select ps.id,ps.enrolment_id,ps.user_id,au.email,up.full_name,c.title,
    ps.amount,ps.currency,ps.transfer_reference,ps.storage_key,ps.content_type,
    ps.file_name,ps.status,ps.admin_note,ps.submitted_at,ps.reviewed_at
  from public.payment_submissions as ps
  join auth.users as au on au.id = ps.user_id
  left join public.user_profiles as up on up.user_id = ps.user_id
  join public.courses as c on c.id = ps.course_id
  where exists (
    select 1 from private.user_roles as ur
    where ur.user_id = auth.uid() and ur.role = 'admin'
  )
  order by ps.submitted_at desc
  limit 200
$fn$;

create or replace function public.portal_admin_review_payment_submission(
  p_submission_id uuid,
  p_status text,
  p_note text default ''
)
returns table (
  submission_id uuid,
  status text,
  reviewed_at timestamptz
)
language plpgsql
security definer
set search_path = ''
as $fn$
declare
  v_admin_id uuid := auth.uid();
  v_submission public.payment_submissions%rowtype;
  v_course_fee numeric;
  v_course_currency text;
  v_actor_handle text;
  v_reviewed_at timestamptz := now();
begin
  if v_admin_id is null or not exists (
    select 1 from private.user_roles as ur
    where ur.user_id = v_admin_id and ur.role = 'admin'
  ) then
    raise exception using errcode = '42501', message = 'Administrator access is required.';
  end if;
  if p_status not in ('approved','rejected') or coalesce(length(p_note),0) > 2000 then
    raise exception using errcode = '22023', message = 'Invalid payment review details.';
  end if;

  select ps.* into v_submission
  from public.payment_submissions as ps
  where ps.id = p_submission_id
  for update;
  if not found then
    raise exception using errcode = 'P0002', message = 'Payment submission not found.';
  end if;
  if v_submission.user_id = v_admin_id then
    raise exception using errcode = '42501', message = 'An administrator cannot approve their own payment.';
  end if;
  if v_submission.status <> 'pending' then
    raise exception using errcode = '22023', message = 'Only pending payment submissions can be reviewed.';
  end if;

  select c.fee_amount,c.fee_currency into v_course_fee,v_course_currency
  from public.courses as c where c.id = v_submission.course_id;

  if p_status = 'approved' and (
    v_submission.amount <> v_course_fee
    or v_submission.currency <> v_course_currency
    or v_submission.storage_key = ''
  ) then
    raise exception using errcode = '22023', message = 'Receipt amount or currency does not match the stored course fee.';
  end if;

  select coalesce(nullif(trim(up.full_name),''),au.email,'YSCMT Admin')
    into v_actor_handle
  from auth.users as au
  left join public.user_profiles as up on up.user_id = au.id
  where au.id = v_admin_id;

  update public.payment_submissions
  set status = p_status,
      admin_note = coalesce(p_note,''),
      reviewed_at = v_reviewed_at
  where id = p_submission_id;

  if p_status = 'approved' then
    update public.enrollments
    set status = 'approved'
    where id = v_submission.enrolment_id
      and user_id = v_submission.user_id
      and status = 'pending';
  end if;

  insert into public.admin_audit_logs (
    actor_user_id,actor_handle,action,target_type,target_id,details
  ) values (
    v_admin_id,coalesce(v_actor_handle,'YSCMT Admin'),'payment_submission.review',
    'payment_submission',p_submission_id::text,
    jsonb_build_object('from','pending','to',p_status,'note',coalesce(p_note,''))
  );

  return query select p_submission_id,p_status,v_reviewed_at;
end;
$fn$;

create or replace function public.portal_admin_list_practice_submissions()
returns table (
  id uuid,
  user_id uuid,
  student_email text,
  student_name text,
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
  select ps.id,ps.user_id,au.email,up.full_name,ps.lab_key,ps.title,
    ps.submission_text,ps.project_url,ps.status,ps.reviewer_notes,
    ps.submitted_at,ps.reviewed_at
  from public.practice_submissions as ps
  join auth.users as au on au.id = ps.user_id
  left join public.user_profiles as up on up.user_id = ps.user_id
  where exists (
    select 1 from private.user_roles as ur
    where ur.user_id = auth.uid() and ur.role = 'admin'
  )
  order by ps.submitted_at desc
  limit 200
$fn$;

create or replace function public.portal_admin_review_practice_submission(
  p_submission_id uuid,
  p_status text,
  p_notes text default ''
)
returns table (
  submission_id uuid,
  status text,
  reviewed_at timestamptz
)
language plpgsql
security definer
set search_path = ''
as $fn$
declare
  v_admin_id uuid := auth.uid();
  v_submission public.practice_submissions%rowtype;
  v_actor_handle text;
  v_reviewed_at timestamptz := now();
begin
  if v_admin_id is null or not exists (
    select 1 from private.user_roles as ur
    where ur.user_id = v_admin_id and ur.role = 'admin'
  ) then
    raise exception using errcode = '42501', message = 'Administrator access is required.';
  end if;
  if p_status not in ('reviewing','approved','rejected')
     or coalesce(length(p_notes),0) > 2000 then
    raise exception using errcode = '22023', message = 'Invalid practice review details.';
  end if;

  select ps.* into v_submission
  from public.practice_submissions as ps
  where ps.id = p_submission_id
  for update;
  if not found then
    raise exception using errcode = 'P0002', message = 'Practice submission not found.';
  end if;
  if v_submission.user_id = v_admin_id then
    raise exception using errcode = '42501', message = 'An administrator cannot review their own submission.';
  end if;

  select coalesce(nullif(trim(up.full_name),''),au.email,'YSCMT Admin')
    into v_actor_handle
  from auth.users as au
  left join public.user_profiles as up on up.user_id = au.id
  where au.id = v_admin_id;

  update public.practice_submissions
  set status = p_status,
      reviewer_notes = coalesce(p_notes,''),
      reviewed_by = v_admin_id,
      reviewed_at = v_reviewed_at
  where id = p_submission_id;

  insert into public.admin_audit_logs (
    actor_user_id,actor_handle,action,target_type,target_id,details
  ) values (
    v_admin_id,coalesce(v_actor_handle,'YSCMT Admin'),'practice_submission.review',
    'practice_submission',p_submission_id::text,
    jsonb_build_object('from',v_submission.status,'to',p_status,'notes',coalesce(p_notes,''))
  );

  return query select p_submission_id,p_status,v_reviewed_at;
end;
$fn$;

create or replace function public.portal_admin_list_certificates()
returns table (
  id uuid,
  certificate_code text,
  user_id uuid,
  student_email text,
  student_name text,
  course_id uuid,
  course_title text,
  issued_at timestamptz
)
language sql
stable
security definer
set search_path = ''
as $fn$
  select sc.id,sc.certificate_code,sc.user_id,au.email,sc.student_name,
    sc.course_id,sc.course_title,sc.issued_at
  from public.student_certificates as sc
  join auth.users as au on au.id = sc.user_id
  where exists (
    select 1 from private.user_roles as ur
    where ur.user_id = auth.uid() and ur.role = 'admin'
  )
  order by sc.issued_at desc
  limit 200
$fn$;

create or replace function public.portal_admin_list_courses()
returns table (
  id uuid,
  title text,
  description text,
  level text,
  active boolean,
  fee_amount numeric,
  fee_currency text,
  created_at timestamptz
)
language sql
stable
security definer
set search_path = ''
as $fn$
  select c.id,c.title,c.description,c.level,c.active,c.fee_amount,c.fee_currency,c.created_at
  from public.courses as c
  where exists (
    select 1 from private.user_roles as ur
    where ur.user_id = auth.uid() and ur.role = 'admin'
  )
  order by c.created_at desc
  limit 200
$fn$;

create or replace function public.portal_admin_create_course(
  p_title text,
  p_description text,
  p_level text,
  p_fee_amount numeric,
  p_fee_currency text
)
returns table (id uuid, created_at timestamptz)
language plpgsql
security definer
set search_path = ''
as $fn$
declare
  v_admin_id uuid := auth.uid();
  v_actor_handle text;
  v_id uuid;
  v_created_at timestamptz;
begin
  if v_admin_id is null or not exists (
    select 1 from private.user_roles as ur where ur.user_id=v_admin_id and ur.role='admin'
  ) then
    raise exception using errcode='42501',message='Administrator access is required.';
  end if;
  if p_title is null or length(trim(p_title)) not between 1 and 150
     or p_description is null or length(p_description) > 10000
     or p_level is null or length(trim(p_level)) not between 1 and 50
     or p_fee_amount is null or p_fee_amount < 0
     or p_fee_currency is null or p_fee_currency !~ '^[A-Z]{3}$' then
    raise exception using errcode='22023',message='Course details are invalid.';
  end if;

  insert into public.courses as c (title,description,level,fee_amount,fee_currency,active)
  values (trim(p_title),p_description,trim(p_level),p_fee_amount,p_fee_currency,true)
  returning c.id,c.created_at into v_id,v_created_at;

  select coalesce(nullif(trim(up.full_name),''),au.email,'YSCMT Admin')
    into v_actor_handle
  from auth.users as au left join public.user_profiles as up on up.user_id=au.id
  where au.id=v_admin_id;

  insert into public.admin_audit_logs(actor_user_id,actor_handle,action,target_type,target_id,details)
  values(v_admin_id,coalesce(v_actor_handle,'YSCMT Admin'),'course.create','course',v_id::text,
    jsonb_build_object('title',p_title,'fee_amount',p_fee_amount,'fee_currency',p_fee_currency));
  return query select v_id,v_created_at;
end;
$fn$;

create or replace function public.portal_admin_update_course(
  p_course_id uuid,
  p_title text,
  p_description text,
  p_level text,
  p_fee_amount numeric,
  p_fee_currency text,
  p_active boolean
)
returns table (id uuid, updated_at timestamptz)
language plpgsql
security definer
set search_path = ''
as $fn$
declare
  v_admin_id uuid := auth.uid();
  v_before public.courses%rowtype;
  v_actor_handle text;
  v_updated_at timestamptz;
begin
  if v_admin_id is null or not exists (
    select 1 from private.user_roles as ur where ur.user_id=v_admin_id and ur.role='admin'
  ) then
    raise exception using errcode='42501',message='Administrator access is required.';
  end if;
  if p_title is null or length(trim(p_title)) not between 1 and 150
     or p_description is null or length(p_description) > 10000
     or p_level is null or length(trim(p_level)) not between 1 and 50
     or p_fee_amount is null or p_fee_amount < 0
     or p_fee_currency is null or p_fee_currency !~ '^[A-Z]{3}$'
     or p_active is null then
    raise exception using errcode='22023',message='Course details are invalid.';
  end if;

  select c.* into v_before from public.courses as c where c.id=p_course_id for update;
  if not found then raise exception using errcode='P0002',message='Course not found.'; end if;

  update public.courses
  set title=trim(p_title),description=p_description,level=trim(p_level),
      fee_amount=p_fee_amount,fee_currency=p_fee_currency,active=p_active
  where id=p_course_id;
  v_updated_at := now();

  select coalesce(nullif(trim(up.full_name),''),au.email,'YSCMT Admin')
    into v_actor_handle
  from auth.users as au left join public.user_profiles as up on up.user_id=au.id
  where au.id=v_admin_id;

  insert into public.admin_audit_logs(actor_user_id,actor_handle,action,target_type,target_id,details)
  values(v_admin_id,coalesce(v_actor_handle,'YSCMT Admin'),'course.update','course',p_course_id::text,
    jsonb_build_object('before',jsonb_build_object('title',v_before.title,'active',v_before.active,
      'fee_amount',v_before.fee_amount,'fee_currency',v_before.fee_currency),
      'after',jsonb_build_object('title',p_title,'active',p_active,
      'fee_amount',p_fee_amount,'fee_currency',p_fee_currency)));
  return query select p_course_id,v_updated_at;
end;
$fn$;

create or replace function public.portal_admin_create_lesson(
  p_course_id uuid,
  p_title text,
  p_content text,
  p_video_url text,
  p_sort_order integer
)
returns table (id uuid, created_at timestamptz)
language plpgsql
security definer
set search_path = ''
as $fn$
declare
  v_admin_id uuid := auth.uid();
  v_id uuid;
  v_created_at timestamptz;
  v_actor_handle text;
begin
  if v_admin_id is null or not exists (
    select 1 from private.user_roles as ur where ur.user_id=v_admin_id and ur.role='admin'
  ) then raise exception using errcode='42501',message='Administrator access is required.'; end if;
  if not exists(select 1 from public.courses as c where c.id=p_course_id)
     or p_title is null or length(trim(p_title)) not between 1 and 200
     or p_content is null or length(p_content)>50000
     or coalesce(p_video_url,'') not in ('') and p_video_url not like 'https://%'
     or p_sort_order is null or p_sort_order<0 then
    raise exception using errcode='22023',message='Lesson details are invalid.';
  end if;

  insert into public.course_lessons as l(course_id,title,content,video_url,sort_order,active)
  values(p_course_id,trim(p_title),p_content,coalesce(p_video_url,''),p_sort_order,true)
  returning l.id,l.created_at into v_id,v_created_at;

  select coalesce(nullif(trim(up.full_name),''),au.email,'YSCMT Admin')
    into v_actor_handle
  from auth.users as au left join public.user_profiles as up on up.user_id=au.id
  where au.id=v_admin_id;
  insert into public.admin_audit_logs(actor_user_id,actor_handle,action,target_type,target_id,details)
  values(v_admin_id,coalesce(v_actor_handle,'YSCMT Admin'),'lesson.create','course_lesson',v_id::text,
    jsonb_build_object('course_id',p_course_id,'title',p_title));
  return query select v_id,v_created_at;
end;
$fn$;

create or replace function public.portal_admin_create_exam(
  p_course_id uuid,
  p_title text,
  p_instructions text,
  p_duration_minutes integer,
  p_pass_mark integer
)
returns table (id uuid, created_at timestamptz)
language plpgsql
security definer
set search_path = ''
as $fn$
declare
  v_admin_id uuid := auth.uid();
  v_id uuid;
  v_created_at timestamptz;
  v_actor_handle text;
begin
  if v_admin_id is null or not exists (
    select 1 from private.user_roles as ur where ur.user_id=v_admin_id and ur.role='admin'
  ) then raise exception using errcode='42501',message='Administrator access is required.'; end if;
  if not exists(select 1 from public.courses as c where c.id=p_course_id)
     or p_title is null or length(trim(p_title)) not between 1 and 200
     or p_instructions is null or length(p_instructions)>5000
     or p_duration_minutes is null or p_duration_minutes not between 1 and 300
     or p_pass_mark is null or p_pass_mark not between 0 and 100 then
    raise exception using errcode='22023',message='Exam details are invalid.';
  end if;

  insert into public.course_exams as ce(course_id,title,instructions,duration_minutes,pass_mark,active)
  values(p_course_id,trim(p_title),p_instructions,p_duration_minutes,p_pass_mark,true)
  returning ce.id,ce.created_at into v_id,v_created_at;

  select coalesce(nullif(trim(up.full_name),''),au.email,'YSCMT Admin')
    into v_actor_handle
  from auth.users as au left join public.user_profiles as up on up.user_id=au.id
  where au.id=v_admin_id;
  insert into public.admin_audit_logs(actor_user_id,actor_handle,action,target_type,target_id,details)
  values(v_admin_id,coalesce(v_actor_handle,'YSCMT Admin'),'exam.create','course_exam',v_id::text,
    jsonb_build_object('course_id',p_course_id,'title',p_title));
  return query select v_id,v_created_at;
end;
$fn$;

create or replace function public.portal_admin_create_exam_question(
  p_exam_id uuid,
  p_question_text text,
  p_options jsonb,
  p_correct_option integer,
  p_sort_order integer
)
returns table (id uuid, sort_order integer)
language plpgsql
security definer
set search_path = ''
as $fn$
declare
  v_admin_id uuid := auth.uid();
  v_id uuid;
  v_actor_handle text;
begin
  if v_admin_id is null or not exists (
    select 1 from private.user_roles as ur where ur.user_id=v_admin_id and ur.role='admin'
  ) then raise exception using errcode='42501',message='Administrator access is required.'; end if;
  if not exists(select 1 from public.course_exams as ce where ce.id=p_exam_id)
     or p_question_text is null or length(trim(p_question_text)) not between 1 and 2000
     or p_correct_option is null or p_correct_option not between 0 and 3
     or p_sort_order is null or p_sort_order<0 then
    raise exception using errcode='22023',message='Exam question details are invalid.';
  end if;
  if p_options is null or jsonb_typeof(p_options) <> 'array' then
    raise exception using errcode='22023',message='Exam options must be a four-item array.';
  end if;
  if jsonb_array_length(p_options) <> 4 or exists (
    select 1 from jsonb_array_elements(p_options) as option(value)
    where jsonb_typeof(option.value) <> 'string'
       or length(trim(option.value #>> '{}')) not between 1 and 500
  ) then
    raise exception using errcode='22023',message='Exam options must contain four non-empty text choices.';
  end if;

  insert into public.exam_questions as q(exam_id,question_text,options,correct_option,sort_order)
  values(p_exam_id,trim(p_question_text),p_options,p_correct_option,p_sort_order)
  returning q.id into v_id;

  select coalesce(nullif(trim(up.full_name),''),au.email,'YSCMT Admin')
    into v_actor_handle
  from auth.users as au left join public.user_profiles as up on up.user_id=au.id
  where au.id=v_admin_id;
  insert into public.admin_audit_logs(actor_user_id,actor_handle,action,target_type,target_id,details)
  values(v_admin_id,coalesce(v_actor_handle,'YSCMT Admin'),'exam_question.create','exam_question',v_id::text,
    jsonb_build_object('exam_id',p_exam_id,'sort_order',p_sort_order));
  return query select v_id,p_sort_order;
end;
$fn$;

create or replace function public.portal_admin_list_exam_questions(p_exam_id uuid)
returns table (
  id uuid,
  question_text text,
  options jsonb,
  correct_option integer,
  sort_order integer
)
language sql
stable
security definer
set search_path = ''
as $fn$
  select q.id,q.question_text,q.options,q.correct_option,q.sort_order
  from public.exam_questions as q
  where q.exam_id=p_exam_id
    and exists (
      select 1 from private.user_roles as ur
      where ur.user_id=auth.uid() and ur.role='admin'
    )
  order by q.sort_order asc,q.created_at asc
  limit 200
$fn$;

revoke all on function public.portal_admin_overview() from public,anon;
revoke all on function public.portal_admin_list_students(integer) from public,anon;
revoke all on function public.portal_admin_list_enrollments(text,integer) from public,anon;
revoke all on function public.portal_admin_review_enrollment(uuid,text,text) from public,anon;
revoke all on function public.portal_admin_list_paystack_payments() from public,anon;
revoke all on function public.portal_admin_list_payment_submissions() from public,anon;
revoke all on function public.portal_admin_review_payment_submission(uuid,text,text) from public,anon;
revoke all on function public.portal_admin_list_practice_submissions() from public,anon;
revoke all on function public.portal_admin_review_practice_submission(uuid,text,text) from public,anon;
revoke all on function public.portal_admin_list_certificates() from public,anon;
revoke all on function public.portal_admin_list_courses() from public,anon;
revoke all on function public.portal_admin_create_course(text,text,text,numeric,text) from public,anon;
revoke all on function public.portal_admin_update_course(uuid,text,text,text,numeric,text,boolean) from public,anon;
revoke all on function public.portal_admin_create_lesson(uuid,text,text,text,integer) from public,anon;
revoke all on function public.portal_admin_create_exam(uuid,text,text,integer,integer) from public,anon;
revoke all on function public.portal_admin_create_exam_question(uuid,text,jsonb,integer,integer) from public,anon;
revoke all on function public.portal_admin_list_exam_questions(uuid) from public,anon;

grant execute on function public.portal_admin_overview() to authenticated;
grant execute on function public.portal_admin_list_students(integer) to authenticated;
grant execute on function public.portal_admin_list_enrollments(text,integer) to authenticated;
grant execute on function public.portal_admin_review_enrollment(uuid,text,text) to authenticated;
grant execute on function public.portal_admin_list_paystack_payments() to authenticated;
grant execute on function public.portal_admin_list_payment_submissions() to authenticated;
grant execute on function public.portal_admin_review_payment_submission(uuid,text,text) to authenticated;
grant execute on function public.portal_admin_list_practice_submissions() to authenticated;
grant execute on function public.portal_admin_review_practice_submission(uuid,text,text) to authenticated;
grant execute on function public.portal_admin_list_certificates() to authenticated;
grant execute on function public.portal_admin_list_courses() to authenticated;
grant execute on function public.portal_admin_create_course(text,text,text,numeric,text) to authenticated;
grant execute on function public.portal_admin_update_course(uuid,text,text,text,numeric,text,boolean) to authenticated;
grant execute on function public.portal_admin_create_lesson(uuid,text,text,text,integer) to authenticated;
grant execute on function public.portal_admin_create_exam(uuid,text,text,integer,integer) to authenticated;
grant execute on function public.portal_admin_create_exam_question(uuid,text,jsonb,integer,integer) to authenticated;
grant execute on function public.portal_admin_list_exam_questions(uuid) to authenticated;
