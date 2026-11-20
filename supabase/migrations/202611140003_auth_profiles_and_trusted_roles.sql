-- YSCMT Auth profile bootstrap and trusted role registry.
-- Authorization roles are never read from user-editable auth metadata.
create table private.user_roles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  role text not null default 'student'
    check (role in ('student','instructor','admin')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
alter table private.user_roles enable row level security;
revoke all on table private.user_roles from public, anon, authenticated;

create or replace function private.handle_new_auth_user()
returns trigger language plpgsql security definer set search_path = ''
as $$
begin
  insert into public.user_profiles (user_id, full_name, phone)
  values (new.id, coalesce(new.raw_user_meta_data ->> 'full_name', ''), coalesce(new.phone, ''))
  on conflict (user_id) do nothing;
  insert into private.user_roles (user_id, role)
  values (new.id, 'student')
  on conflict (user_id) do nothing;
  return new;
end;
$$;
revoke all on function private.handle_new_auth_user() from public, anon, authenticated;
drop trigger if exists on_auth_user_created_yscmt on auth.users;
create trigger on_auth_user_created_yscmt after insert on auth.users
for each row execute function private.handle_new_auth_user();

create or replace function private.set_updated_at()
returns trigger language plpgsql set search_path = ''
as $$
begin
  new.updated_at = pg_catalog.now();
  return new;
end;
$$;
revoke all on function private.set_updated_at() from public, anon, authenticated;
drop trigger if exists user_profiles_set_updated_at on public.user_profiles;
create trigger user_profiles_set_updated_at before update on public.user_profiles
for each row execute function private.set_updated_at();
drop trigger if exists user_roles_set_updated_at on private.user_roles;
create trigger user_roles_set_updated_at before update on private.user_roles
for each row execute function private.set_updated_at();

grant usage on schema private to service_role;
grant select, insert, update, delete on all tables in schema private to service_role;
grant usage, select on all sequences in schema private to service_role;
