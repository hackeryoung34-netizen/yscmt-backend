# YSCMT Paystack Edge Function

This function replaces the need for a dedicated payment VPS. It runs on Supabase Edge Functions and keeps the Paystack secret and Supabase service-role key server-side.

## Required server-side secrets

Configure these in Supabase Edge Function secrets; never put them in the browser or Git:

- `PAYSTACK_SECRET_KEY` — Paystack secret key, either test or live.
- `PAYSTACK_EXPECTED_DOMAIN` — exactly `test` or `live`; must match the secret-key prefix.
- `PAYSTACK_CALLBACK_URL` — approved HTTPS portal callback URL.
- `PORTAL_ALLOWED_ORIGINS` — comma-separated exact HTTPS origins allowed to call the browser endpoints.

Supabase provides the function runtime with `SUPABASE_URL`, `SUPABASE_ANON_KEY`, and `SUPABASE_SERVICE_ROLE_KEY`. The service-role key is used only inside this Edge Function and must never be exposed to the client.

Do not send secret values through chat or commit them to GitHub.

## Actions

The function accepts POST requests:

- `{"action":"initialize","enrollment_id":"<uuid>"}` with a Supabase user access token. The server derives the exact NGN amount from the stored course fee and creates/reuses a pending Paystack reference.
- `{"action":"verify","reference":"<reference>"}` with the same user's access token. The function verifies the transaction directly with Paystack and confirms it only for the owning account.
- Paystack webhook: configure the provider to POST to `https://wzpkfjnymsxczbkiukrp.supabase.co/functions/v1/paystack-payment?action=webhook`. The handler validates the HMAC-SHA512 signature against the raw request body and re-verifies the transaction with Paystack before reconciliation.

Only `charge.success` webhook events are processed. Repeated notifications are safe because payment confirmation is idempotent.

## Deployment gate

The function is committed to the migration branch only. It has **not** been deployed. Do not deploy until:

1. Migration 010 is reviewed and explicitly approved/applied.
2. Paystack test secrets are configured in Supabase.
3. A disposable test enrolment and Paystack test transaction are approved.
4. The callback URL and allowed origins are confirmed.

Start with Paystack test mode. Do not configure live keys or process real payments during preview.
