-- Expose only the caller's trusted portal identity through a narrow RPC.
-- This avoids exposing the private schema through the Supabase Data API.
create or replace function public.portal_get_my_identity()
returns table (
  user_id uuid,
  role text,
  email text,
  full_name text,
  phone text
)
language sql
stable
security definer
set search_path = ''
as $$
  select
    auth.uid(),
    ur.role,
    au.email,
    coalesce(up.full_name, ''),
    coalesce(up.phone, '')
  from private.user_roles as ur
  join auth.users as au
    on au.id = ur.user_id
  left join public.user_profiles as up
    on up.user_id = ur.user_id
  where ur.user_id = auth.uid()
$$;

-- SECURITY DEFINER functions in public must not inherit PUBLIC execution.
revoke all on function public.portal_get_my_identity() from public, anon;
grant execute on function public.portal_get_my_identity() to authenticated;

comment on function public.portal_get_my_identity() is
  'Returns only the current authenticated user profile and trusted portal role; never accepts a caller-supplied user ID.';
