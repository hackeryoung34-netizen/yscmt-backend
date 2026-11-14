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

insert into auth.users (id,email,phone,raw_user_meta_data)
values (
  '10000000-0000-4000-8000-000000000003',
  'student2@example.test',
  '',
  '{"full_name":"Second Student"}'::jsonb
);

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

insert into public.enrollments (user_id,course_id,status)
values ('10000000-0000-4000-8000-000000000003','20000000-0000-4000-8000-000000000001','pending');

insert into public.enrollments (user_id,course_id,status)
values ('10000000-0000-4000-8000-000000000002','20000000-0000-4000-8000-000000000001','pending');

insert into public.classroom_sessions (
  id,course_id,title,description,meeting_url,starts_at,ends_at,status,created_by
) values (
  '60000000-0000-4000-8000-000000000001',
  '20000000-0000-4000-8000-000000000001',
  'Test live classroom',
  'Integration test session',
  'https://meet.example.test/yscmt',
  now() - interval '1 minute',
  now() + interval '1 hour',
  'live',
  '10000000-0000-4000-8000-000000000002'
);

insert into public.classroom_announcements (
  id,course_id,title,body,published,created_by
) values (
  '61000000-0000-4000-8000-000000000001',
  '20000000-0000-4000-8000-000000000001',
  'Test announcement',
  'Classroom test announcement',
  true,
  '10000000-0000-4000-8000-000000000002'
);

insert into public.classroom_teacher_replies (
  id,course_id,created_by,message
) values (
  '62000000-0000-4000-8000-000000000001',
  '20000000-0000-4000-8000-000000000001',
  '10000000-0000-4000-8000-000000000002',
  'Test teacher reply'
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
  v_classroom_session_id uuid;
  v_attendance_id uuid;
  v_certificate_id uuid;
  v_practice_id uuid;
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

  select * into v_payment
  from public.portal_get_my_course_enrollment('20000000-0000-4000-8000-000000000001');
  if v_payment.enrollment_id <> v_enrollment_id
     or v_payment.status <> 'pending'
     or v_payment.fee_amount <> 1000
     or v_payment.fee_currency <> 'NGN' then
    raise exception 'Student enrolment lookup must return only the current user's stored fee and status.';
  end if;

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
      '10000000-0000-4000-8000-000000000002',
      v_reference,100000,'NGN',v_gateway
    );
    raise exception 'A different account must not confirm this payment.';
  exception when insufficient_privilege then
    null;
  end;

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
  from public.portal_confirm_paystack_payment(null,v_reference,100000,'NGN',v_gateway);
  if v_payment.status <> 'success' then
    raise exception 'Repeated webhook confirmation must be idempotent.';
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

  begin
    perform * from public.portal_request_certificate('20000000-0000-4000-8000-000000000001');
    raise exception 'Certificate must not be issued before an exam is passed.';
  exception when sqlstate '22023' then
    null;
  end;

  select id into v_classroom_session_id
  from public.portal_list_classroom_sessions('20000000-0000-4000-8000-000000000001')
  limit 1;
  if v_classroom_session_id <> '60000000-0000-4000-8000-000000000001' then
    raise exception 'Approved student should see the classroom session.';
  end if;

  select attendance_id into v_attendance_id
  from public.portal_join_classroom_session(v_classroom_session_id);
  if v_attendance_id is null then raise exception 'Classroom attendance was not created.'; end if;

  if (select count(*) from public.portal_list_classroom_announcements('20000000-0000-4000-8000-000000000001')) <> 1 then
    raise exception 'Course announcement should be visible to the enrolled student.';
  end if;
  if (select count(*) from public.portal_list_teacher_replies('20000000-0000-4000-8000-000000000001')) <> 1 then
    raise exception 'Teacher reply should be visible to the enrolled student.';
  end if;

  perform * from public.portal_send_classroom_message(
    '20000000-0000-4000-8000-000000000001',
    'Hello from the integration test'
  );
  if (select count(*) from public.portal_list_classroom_messages('20000000-0000-4000-8000-000000000001')) <> 1 then
    raise exception 'Student classroom message was not returned.';
  end if;

  select id into v_practice_id
  from public.portal_submit_practice(
    'lab-001','Practice test','Submitted practice content','https://example.test/project'
  );
  if v_practice_id is null then raise exception 'Practice submission was not created.'; end if;
  if (select count(*) from public.portal_list_my_practice_submissions()) <> 1 then
    raise exception 'Student practice submission was not returned.';
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

  select id into v_certificate_id
  from public.portal_request_certificate('20000000-0000-4000-8000-000000000001');
  if v_certificate_id is null then raise exception 'Eligible student certificate was not issued.'; end if;
  if (select count(*) from public.portal_list_my_certificates()) <> 1 then
    raise exception 'Student certificate was not returned.';
  end if;
  if (select id from public.portal_request_certificate('20000000-0000-4000-8000-000000000001')) <> v_certificate_id then
    raise exception 'Certificate request must be idempotent.';
  end if;


  -- Verify the trusted admin management surface and audit trail.
  perform set_config('request.jwt.claim.sub','10000000-0000-4000-8000-000000000002',false);

  select * into v_admin_result from public.portal_admin_review_practice_submission(
    v_practice_id,'approved','Practice accepted in integration test'
  );
  if v_admin_result.status <> 'approved' then
    raise exception 'Admin practice review did not update the submission.';
  end if;

  select e.id into v_second_enrollment_id
  from public.enrollments as e
  where e.user_id='10000000-0000-4000-8000-000000000003'
    and e.course_id='20000000-0000-4000-8000-000000000001';
  select e.id into v_admin_enrollment_id
  from public.enrollments as e
  where e.user_id='10000000-0000-4000-8000-000000000002'
    and e.course_id='20000000-0000-4000-8000-000000000001';

  begin
    perform * from public.portal_admin_review_enrollment(v_admin_enrollment_id,'approved','');
    raise exception 'Admin must not approve their own enrolment.';
  exception when insufficient_privilege then
    null;
  end;
  delete from public.enrollments where id=v_admin_enrollment_id;

  select * into v_admin_result
  from public.portal_admin_review_enrollment(v_second_enrollment_id,'approved','Verified by admin test');
  if v_admin_result.status <> 'approved' then
    raise exception 'Admin enrolment approval failed.';
  end if;

  if (select count(*) from public.portal_admin_list_students(50)) <> 2 then
    raise exception 'Admin student list should include both student accounts.';
  end if;
  if (select count(*) from public.portal_admin_list_enrollments(null,100)) <> 2 then
    raise exception 'Admin enrolment list should include both student enrolments.';
  end if;
  if (select count(*) from public.portal_admin_list_paystack_payments()) <> 1 then
    raise exception 'Admin Paystack payment list should contain the verified payment.';
  end if;
  if (select count(*) from public.portal_admin_list_payment_submissions()) <> 0 then
    raise exception 'No manual payment submissions should exist in this fixture.';
  end if;
  if (select count(*) from public.portal_admin_list_practice_submissions()) <> 1 then
    raise exception 'Admin practice list should contain the student submission.';
  end if;
  if (select count(*) from public.portal_admin_list_certificates()) <> 1 then
    raise exception 'Admin certificate list should contain the issued certificate.';
  end if;
  if (select count(*) from public.portal_admin_list_exam_questions('40000000-0000-4000-8000-000000000001')) <> 2 then
    raise exception 'Admin should be able to read exam answer keys.';
  end if;

  select id into v_new_course_id
  from public.portal_admin_create_course('Admin Test Course','Admin-created course','Beginner',0,'NGN');
  select id into v_new_lesson_id
  from public.portal_admin_create_lesson(v_new_course_id,'Admin Lesson','Lesson content','',1);
  select id into v_new_exam_id
  from public.portal_admin_create_exam(v_new_course_id,'Admin Exam','Exam instructions',30,60);
  select id into v_new_question_id
  from public.portal_admin_create_exam_question(
    v_new_exam_id,'Admin question?','["One","Two","Three","Four"]'::jsonb,2,1
  );
  if v_new_course_id is null or v_new_lesson_id is null or v_new_exam_id is null or v_new_question_id is null then
    raise exception 'Admin course, lesson and exam creation failed.';
  end if;
  perform * from public.portal_admin_update_course(
    v_new_course_id,'Updated Admin Course','Updated description','Intermediate',0,'NGN',false
  );

  if (select count(*) from public.portal_admin_list_courses()) <> 2 then
    raise exception 'Admin course list should include active and inactive courses.';
  end if;
  if (select count(*) from public.admin_audit_logs) < 6 then
    raise exception 'Admin mutations must write audit log entries.';
  end if;

  -- A student must not receive any admin overview rows.
  perform set_config('request.jwt.claim.sub','10000000-0000-4000-8000-000000000001',false);
  if (select count(*) from public.portal_admin_overview()) <> 0 then
    raise exception 'Student account unexpectedly received admin overview data.';
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
