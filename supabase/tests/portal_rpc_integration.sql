-- Integration tests for migrations 001–009 on an isolated PostgreSQL instance.
insert into auth.users (id,email,phone,raw_user_meta_data)
values (
  '10000000-0000-4000-8000-000000000001',
  'student@example.test',
  '',
  '{"role":"admin","full_name":"Test Student"}'::jsonb
);
insert into auth.users (id,email,phone,raw_user_meta_data)
values (
  '10000000-0000-4000-8000-000000000002',
  'admin@example.test',
  '',
  '{"full_name":"Test Admin"}'::jsonb
);
update private.user_roles
set role = 'admin'
where user_id = '10000000-0000-4000-8000-000000000002';

insert into public.courses (id,title,description,level,active,fee_amount,fee_currency)
values (
  '20000000-0000-4000-8000-000000000001',
  'Portal RPC Test Course',
  'Isolated integration test course',
  'Beginner',
  true,
  1000,
  'NGN'
);

insert into public.course_lessons (id,course_id,title,content,sort_order,active)
values (
  '30000000-0000-4000-8000-000000000001',
  '20000000-0000-4000-8000-000000000001',
  'Test lesson',
  'Lesson content',
  1,
  true
);

insert into public.course_exams (id,course_id,title,instructions,duration_minutes,pass_mark,active)
values (
  '40000000-0000-4000-8000-000000000001',
  '20000000-0000-4000-8000-000000000001',
  'Test exam',
  'Choose the correct options',
  20,
  50,
  true
);

insert into public.exam_questions (id,exam_id,question_text,options,correct_option,sort_order)
values
(
  '50000000-0000-4000-8000-000000000001',
  '40000000-0000-4000-8000-000000000001',
  'Question one?',
  '["A","B","C","D"]'::jsonb,
  2,
  1
),
(
  '50000000-0000-4000-8000-000000000002',
  '40000000-0000-4000-8000-000000000001',
  'Question two?',
  '["A","B","C","D"]'::jsonb,
  1,
  2
);

select set_config('request.jwt.claim.sub','10000000-0000-4000-8000-000000000001',false);

do $tests$
declare
  v_role text;
  v_status text;
  v_enrollment_id uuid;
  v_count integer;
  v_progress record;
  v_session uuid;
  v_questions integer;
  v_answers jsonb;
  v_attempt record;
  v_attempt_again record;
  v_payment record;
  v_reference text;
  v_gateway jsonb;
begin
  select role into v_role from private.user_roles
  where user_id = auth.uid();
  if v_role <> 'student' then
    raise exception 'Auth metadata must not assign privileged roles.';
  end if;

  select count(*) into v_count from public.portal_list_courses();
  if v_count <> 1 then raise exception 'Expected one active course for the student.'; end if;

  select id, status into v_enrollment_id, v_status
  from public.portal_create_enrollment('20000000-0000-4000-8000-000000000001');
  if v_status <> 'pending' then raise exception 'Student enrolment must be pending.'; end if;

  select count(*) into v_count
  from public.portal_get_course_lessons('20000000-0000-4000-8000-000000000001');
  if v_count <> 0 then raise exception 'Pending enrolment must not unlock lessons.'; end if;

  begin
    perform * from public.portal_mark_lesson_complete('30000000-0000-4000-8000-000000000001');
    raise exception 'Pending student must not complete lessons.';
  exception when insufficient_privilege then
    null;
  end;

  select count(*) into v_count
  from public.portal_list_course_exams('20000000-0000-4000-8000-000000000001');
  if v_count <> 0 then raise exception 'Pending enrolment must not reveal exams.'; end if;

  if has_function_privilege('authenticated','public.portal_prepare_paystack_payment(uuid,uuid)','EXECUTE') then
    raise exception 'Browser roles must not execute server-only payment preparation.';
  end if;
  if not has_function_privilege('service_role','public.portal_prepare_paystack_payment(uuid,uuid)','EXECUTE') then
    raise exception 'Service role must be able to prepare payments.';
  end if;
  if has_function_privilege('authenticated','public.portal_confirm_paystack_payment(uuid,text,bigint,text,jsonb)','EXECUTE') then
    raise exception 'Browser roles must not confirm Paystack payments.';
  end if;

  select * into v_payment
  from public.portal_prepare_paystack_payment(
    auth.uid(),
    v_enrollment_id
  );
  v_reference := v_payment.reference;
  if v_payment.amount_kobo <> 100000 or v_payment.currency <> 'NGN'
     or v_payment.email <> 'student@example.test' then
    raise exception 'Paystack amount, currency or account email was not derived correctly.';
  end if;

  perform public.portal_set_paystack_authorization_url(
    v_reference,
    'https://checkout.paystack.com/test-reference'
  );

  v_gateway := jsonb_build_object(
    'status','success',
    'reference',v_reference,
    'currency','NGN',
    'amount',100000
  );

  begin
    perform * from public.portal_confirm_paystack_payment(
      auth.uid(),v_reference,100001,'NGN',
      jsonb_build_object('status','success','reference',v_reference,'currency','NGN','amount',100001)
    );
    raise exception 'Payment with a mismatched amount must not be confirmed.';
  exception when sqlstate '22023' then
    null;
  end;

  select * into v_payment
  from public.portal_confirm_paystack_payment(auth.uid(),v_reference,100000,'NGN',v_gateway);
  if v_payment.status <> 'success' then
    raise exception 'Verified Paystack payment should be marked successful.';
  end if;

  select * into v_payment
  from public.portal_confirm_paystack_payment(auth.uid(),v_reference,100000,'NGN',v_gateway);
  if v_payment.status <> 'success' then
    raise exception 'Repeated Paystack confirmation must be idempotent.';
  end if;

  select count(*) into v_count
  from public.portal_get_course_lessons('20000000-0000-4000-8000-000000000001');
  if v_count <> 1 then raise exception 'Approved student should see course lessons.'; end if;

  perform * from public.portal_mark_lesson_complete('30000000-0000-4000-8000-000000000001');
  select * into v_progress
  from public.portal_get_my_course_progress('20000000-0000-4000-8000-000000000001');
  if v_progress.total_lessons <> 1 or v_progress.completed_lessons <> 1
     or v_progress.progress_percent <> 100 then
    raise exception 'Lesson progress summary is incorrect.';
  end if;

  select count(*) into v_count
  from public.portal_list_course_exams('20000000-0000-4000-8000-000000000001');
  if v_count <> 1 then raise exception 'Approved student should see the active exam.'; end if;

  select session_id into v_session
  from public.portal_start_exam('40000000-0000-4000-8000-000000000001');
  if v_session is null then raise exception 'Exam session was not created.'; end if;

  select count(*) into v_questions
  from public.portal_get_exam_questions(v_session);
  if v_questions <> 2 then raise exception 'Student should receive both exam questions.'; end if;

  if pg_get_function_result('public.portal_get_exam_questions(uuid)'::regprocedure) ilike '%correct_option%' then
    raise exception 'Exam question API must not expose correct_option.';
  end if;

  select jsonb_object_agg(id::text, correct_option)
  into v_answers
  from public.exam_questions
  where exam_id = '40000000-0000-4000-8000-000000000001';

  select * into v_attempt
  from public.portal_submit_exam(v_session,v_answers);
  if v_attempt.score <> 100 or not v_attempt.passed then
    raise exception 'Correct answers should produce a passing score of 100.';
  end if;

  select * into v_attempt_again
  from public.portal_submit_exam(v_session,'{}'::jsonb);
  if v_attempt_again.attempt_id <> v_attempt.attempt_id then
    raise exception 'Repeated submission must return the same attempt.';
  end if;

  -- A trusted admin must not use student-only enrolment functions.
  perform set_config('request.jwt.claim.sub','10000000-0000-4000-8000-000000000002',false);
  begin
    perform * from public.portal_create_enrollment('20000000-0000-4000-8000-000000000001');
    raise exception 'Admin must not create a student enrolment.';
  exception when insufficient_privilege then
    null;
  end;
end;
$tests$;

-- Browser roles can execute narrow RPCs, but cannot directly read or mutate business tables.
select set_config('request.jwt.claim.sub','10000000-0000-4000-8000-000000000001',false);
set role authenticated;
do $permissions$
begin
  begin
    perform 1 from public.courses;
    raise exception 'Authenticated browser role unexpectedly read courses directly.';
  exception when insufficient_privilege then
    null;
  end;
  begin
    update public.enrollments set status = 'approved'
    where user_id = auth.uid()
      and course_id = '20000000-0000-4000-8000-000000000001';
    raise exception 'Student browser role unexpectedly approved its own enrolment.';
  exception when insufficient_privilege then
    null;
  end;
end;
$permissions$;
reset role;

select 'YSCMT Supabase RPC integration tests passed.' as result;
