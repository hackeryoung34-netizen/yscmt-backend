-- Internal-schema hardening and FK indexes (applied to YSCMT Supabase).
alter table private.legacy_user_map enable row level security;
alter table private.site_settings enable row level security;
create index legacy_user_map_auth_user_idx on private.legacy_user_map(auth_user_id);
create index admin_audit_logs_actor_user_idx on public.admin_audit_logs(actor_user_id);
create index classroom_announcements_created_by_idx on public.classroom_announcements(created_by);
create index classroom_messages_user_idx on public.classroom_messages(user_id);
create index classroom_sessions_created_by_idx on public.classroom_sessions(created_by);
create index classroom_teacher_replies_created_by_idx on public.classroom_teacher_replies(created_by);
create index exam_attempts_exam_id_idx on public.exam_attempts(exam_id);
create index exam_sessions_exam_id_idx on public.exam_sessions(exam_id);
create index lesson_progress_lesson_id_idx on public.lesson_progress(lesson_id);
create index payment_submissions_user_id_idx on public.payment_submissions(user_id);
create index payment_submissions_course_id_idx on public.payment_submissions(course_id);
create index paystack_payments_course_id_idx on public.paystack_payments(course_id);
create index practice_submissions_reviewed_by_idx on public.practice_submissions(reviewed_by);
create index student_certificates_course_id_idx on public.student_certificates(course_id);
