# Password-reset email setup (preview only)

The Student Portal password-reset flow is implemented with one-time, hashed reset tokens, 30-minute expiry, invalidation of older tokens, a per-account 60-second resend cooldown, and a generic response that does not reveal whether an email address exists.

## Preview environment variables

Configure these only in the non-production preview service's secret environment:

| Variable | Recommended preview value |
|---|---|
| EMAIL_BACKEND | django.core.mail.backends.smtp.EmailBackend |
| EMAIL_HOST | SMTP provider hostname |
| EMAIL_PORT | 587 for STARTTLS, if supported |
| EMAIL_HOST_USER | SMTP account username |
| EMAIL_HOST_PASSWORD | SMTP credential or provider app password |
| EMAIL_USE_TLS | true when using STARTTLS |
| EMAIL_USE_SSL | false when using STARTTLS; do not enable TLS and SSL together |
| DEFAULT_FROM_EMAIL | Verified sender address on the configured domain |
| FRONTEND_URL | HTTPS preview frontend origin, with no trailing slash |

Never commit SMTP credentials, place them in frontend variables, or send reset tokens to logs. Use a dedicated transactional email credential with least privilege and a verified sender domain. Use a disposable preview account and inbox for the end-to-end test.

## Verification checklist

1. Configure SMTP secrets only in preview.
2. Request reset for an existing disposable account; confirm the generic API response and receipt of email.
3. Confirm the link targets the preview frontend, expires after 30 minutes, and succeeds once only.
4. Confirm requesting another link invalidates previous unused tokens and the resend cooldown is enforced.
5. Confirm unknown email addresses receive the same public response and no email is sent.
6. Confirm missing or failing SMTP configuration fails closed and no reset token remains usable.

Do not configure production SMTP or change the live frontend as part of this preview task. Hatchable remains the production service until an explicitly approved cutover.