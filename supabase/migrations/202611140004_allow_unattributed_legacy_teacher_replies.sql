-- Legacy Hatchable classroom replies can use the literal creator "admin".
-- Preserve the historical reply without fabricating a Supabase Auth identity.
alter table public.classroom_teacher_replies
  alter column created_by drop not null;
