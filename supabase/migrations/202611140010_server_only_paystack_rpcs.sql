-- Server-only Paystack payment preparation and confirmation.
-- Student can read only their own current enrolment status and stored course fee.
create or replace function public.portal_get_my_course_enrollment(p_course_id uuid)
returns table (
  enrollment_id uuid,
  status text,
  fee_amount numeric,
  fee_currency text
)
language sql
stable
security definer
set search_path = ''
as $fn$
  select e.id, e.status, c.fee_amount, c.fee_currency
  from public.enrollments as e
  join public.courses as c on c.id = e.course_id and c.active = true
  join private.user_roles as ur on ur.user_id = auth.uid() and ur.role = 'student'
  where e.course_id = p_course_id
    and e.user_id = auth.uid()
    and auth.uid() is not null
  limit 1
$fn$;

revoke all on function public.portal_get_my_course_enrollment(uuid) from public, anon;
grant execute on function public.portal_get_my_course_enrollment(uuid) to authenticated;

comment on function public.portal_get_my_course_enrollment(uuid) is
  'Returns only the authenticated student enrolment ID/status and stored course fee, for secure payment initialization.';


-- Only a trusted Edge Function using service_role may execute these RPCs.
create unique index if not exists paystack_one_pending_per_enrollment
  on public.paystack_payments(enrolment_id)
  where status = 'pending';

create or replace function public.portal_prepare_paystack_payment(
  p_user_id uuid,
  p_enrollment_id uuid
)
returns table (
  reference text,
  amount_kobo bigint,
  currency text,
  email text,
  authorization_url text
)
language plpgsql
security definer
set search_path = ''
as $fn$
declare
  v_amount_kobo bigint;
  v_email text;
  v_reference text;
  v_payment public.paystack_payments%rowtype;
begin
  if p_user_id is null or p_enrollment_id is null then
    raise exception using errcode = '22023', message = 'User and enrolment are required.';
  end if;

  if not exists (
    select 1 from private.user_roles as ur
    where ur.user_id = p_user_id and ur.role = 'student'
  ) then
    raise exception using errcode = '42501', message = 'Only student accounts may pay course fees.';
  end if;

  select round(c.fee_amount * 100)::bigint, au.email
    into v_amount_kobo, v_email
  from public.enrollments as e
  join public.courses as c on c.id = e.course_id and c.active = true
  join auth.users as au on au.id = e.user_id
  where e.id = p_enrollment_id
    and e.user_id = p_user_id
    and e.status = 'pending'
    and c.fee_currency = 'NGN';

  if not found then
    raise exception using errcode = 'P0002',
      message = 'A pending enrolment for an active NGN course is required.';
  end if;

  if v_amount_kobo is null or v_amount_kobo <= 0 then
    raise exception using errcode = '22023', message = 'The course fee must be greater than zero.';
  end if;
  if v_email is null or length(trim(v_email)) = 0 then
    raise exception using errcode = '22023', message = 'A verified account email is required for payment.';
  end if;

  select pp.* into v_payment
  from public.paystack_payments as pp
  where pp.enrolment_id = p_enrollment_id
    and pp.user_id = p_user_id
    and pp.status = 'pending'
  order by pp.created_at desc
  limit 1
  for update;

  if found and v_payment.amount_kobo = v_amount_kobo
     and v_payment.currency = 'NGN'
     and v_payment.created_at > now() - interval '30 minutes' then
    return query select v_payment.reference, v_payment.amount_kobo,
      v_payment.currency, v_email, v_payment.authorization_url;
    return;
  end if;

  if found then
    update public.paystack_payments
    set status = 'abandoned'
    where id = v_payment.id and status = 'pending';
  end if;

  v_reference := 'YSCMT_' || upper(replace(pg_catalog.gen_random_uuid()::text, '-', ''));

  begin
    insert into public.paystack_payments (
      enrolment_id, user_id, course_id, reference, amount_kobo, currency, status
    )
    select e.id, e.user_id, e.course_id, v_reference, v_amount_kobo, 'NGN', 'pending'
    from public.enrollments as e
    where e.id = p_enrollment_id and e.user_id = p_user_id;
  exception when unique_violation then
    select pp.* into v_payment
    from public.paystack_payments as pp
    where pp.enrolment_id = p_enrollment_id
      and pp.user_id = p_user_id
      and pp.status = 'pending'
    order by pp.created_at desc
    limit 1
    for update;
    if found then
      return query select v_payment.reference, v_payment.amount_kobo,
        v_payment.currency, v_email, v_payment.authorization_url;
      return;
    end if;
    raise;
  end;

  return query select v_reference, v_amount_kobo, 'NGN'::text, v_email, ''::text;
end;
$fn$;

create or replace function public.portal_set_paystack_authorization_url(
  p_reference text,
  p_authorization_url text
)
returns boolean
language plpgsql
security definer
set search_path = ''
as $fn$
declare
  v_updated integer;
begin
  if p_reference is null or length(p_reference) > 100
     or p_authorization_url is null
     or length(p_authorization_url) > 2048
     or p_authorization_url not like 'https://checkout.paystack.com/%' then
    raise exception using errcode = '22023', message = 'Invalid Paystack checkout details.';
  end if;

  update public.paystack_payments
  set authorization_url = p_authorization_url
  where reference = p_reference and status = 'pending';

  get diagnostics v_updated = row_count;
  if v_updated <> 1 then
    raise exception using errcode = 'P0002', message = 'Pending payment reference not found.';
  end if;
  return true;
end;
$fn$;

create or replace function public.portal_confirm_paystack_payment(
  p_user_id uuid,
  p_reference text,
  p_amount_kobo bigint,
  p_currency text,
  p_gateway_response jsonb
)
returns table (
  payment_id uuid,
  enrollment_id uuid,
  status text,
  verified_at timestamptz
)
language plpgsql
security definer
set search_path = ''
as $fn$
declare
  v_payment public.paystack_payments%rowtype;
  v_gateway_amount bigint;
  v_verified_at timestamptz := now();
begin
  if p_reference is null or p_amount_kobo is null or p_amount_kobo <= 0
     or p_currency is null
     or p_gateway_response is null
     or octet_length(p_gateway_response::text) > 65536 then
    raise exception using errcode = '22023', message = 'Invalid verified payment details.';
  end if;

  if jsonb_typeof(p_gateway_response) is distinct from 'object'
     or (p_gateway_response ->> 'status') is distinct from 'success'
     or (p_gateway_response ->> 'reference') is distinct from p_reference
     or (p_gateway_response ->> 'currency') is distinct from p_currency
     or coalesce(p_gateway_response ->> 'amount', '') !~ '^[0-9]{1,18}$' then
    raise exception using errcode = '22023', message = 'Paystack verification payload does not match the payment.';
  end if;

  v_gateway_amount := (p_gateway_response ->> 'amount')::bigint;
  if v_gateway_amount <> p_amount_kobo then
    raise exception using errcode = '22023', message = 'Paystack amount does not match the verified payment.';
  end if;

  select pp.* into v_payment
  from public.paystack_payments as pp
  where pp.reference = p_reference
  for update;

  if not found then
    raise exception using errcode = 'P0002', message = 'Payment reference not found.';
  end if;

  if p_user_id is not null and v_payment.user_id <> p_user_id then
    raise exception using errcode = '42501', message = 'This payment does not belong to the authenticated account.';
  end if;

  if v_payment.amount_kobo <> p_amount_kobo or v_payment.currency <> p_currency then
    raise exception using errcode = '22023', message = 'Verified amount or currency does not match the stored payment.';
  end if;

  if v_payment.status = 'success' then
    return query select v_payment.id, v_payment.enrolment_id,
      v_payment.status, v_payment.verified_at;
    return;
  end if;

  if v_payment.status <> 'pending' then
    raise exception using errcode = '22023', message = 'This payment is no longer pending.';
  end if;

  update public.paystack_payments
  set status = 'success',
      gateway_response = p_gateway_response,
      verified_at = v_verified_at
  where id = v_payment.id;

  update public.enrollments
  set status = 'approved'
  where id = v_payment.enrolment_id
    and user_id = v_payment.user_id
    and status = 'pending';

  if not found and not exists (
    select 1 from public.enrollments as e
    where e.id = v_payment.enrolment_id
      and e.user_id = v_payment.user_id
      and e.status in ('approved','completed')
  ) then
    raise exception using errcode = '22023', message = 'Enrolment is not eligible for payment approval.';
  end if;

  return query select v_payment.id, v_payment.enrolment_id,
    'success'::text, v_verified_at;
end;
$fn$;

revoke all on function public.portal_prepare_paystack_payment(uuid, uuid) from public, anon, authenticated;
revoke all on function public.portal_set_paystack_authorization_url(text, text) from public, anon, authenticated;
revoke all on function public.portal_confirm_paystack_payment(uuid, text, bigint, text, jsonb) from public, anon, authenticated;
grant execute on function public.portal_prepare_paystack_payment(uuid, uuid) to service_role;
grant execute on function public.portal_set_paystack_authorization_url(text, text) to service_role;
grant execute on function public.portal_confirm_paystack_payment(uuid, text, bigint, text, jsonb) to service_role;

comment on function public.portal_prepare_paystack_payment(uuid, uuid) is
  'Server-only: validates a pending student enrolment and derives the exact NGN amount from the stored course fee.';
comment on function public.portal_set_paystack_authorization_url(text, text) is
  'Server-only: stores a validated Paystack checkout URL for a pending payment reference.';
comment on function public.portal_confirm_paystack_payment(uuid, text, bigint, text, jsonb) is
  'Server-only: confirms an exact Paystack-verified amount/currency/reference and idempotently approves the enrolment.';
