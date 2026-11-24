# YSCMT Student Portal — private receipt storage setup

The portal uses Cloudflare R2 through its S3-compatible API. Receipt objects must remain private.

## Preview environment variables

Set these only in the non-production preview service after the R2 bucket and scoped API token exist:

- `PORTAL_R2_ENDPOINT_URL`: `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`
- `PORTAL_R2_ACCESS_KEY_ID`: R2 access key ID
- `PORTAL_R2_SECRET_ACCESS_KEY`: R2 secret access key
- `PORTAL_R2_BUCKET`: private bucket name

Never commit credentials, put them in frontend environment variables, or paste secret values into GitHub issues or chat. Use an R2 token scoped only to the receipt bucket with object read/write permissions needed by the portal.

## Bucket controls

- Keep public access disabled. Do not attach an `r2.dev` public domain or public custom domain.
- Configure bucket CORS for the exact preview frontend origin(s) only. Allow browser `POST` uploads and required response headers. Do not use wildcard origins with credentials.
- Keep the bucket in the same Cloudflare account as the configured endpoint.
- Do not create or configure the production bucket as part of this preview task.

## Upload flow

1. Authenticated student requests `POST /api/portal/v1/student/payment-submissions/upload/` with their pending `enrollment_id`, allowed MIME type and file name.
2. Server checks enrolment ownership and the stored course fee, creates an `uploading` submission and returns a 5-minute presigned POST. Client must submit the returned fields and file directly to the private bucket.
3. Client calls `POST /api/portal/v1/student/payment-submissions/{submission_id}/complete-upload/`. Server checks the object owner metadata, size (1–5 MiB), MIME type and PDF/JPEG/PNG file signature before marking it pending.
4. Student or admin obtains a short-lived private download URL from `GET /api/portal/v1/payment-submissions/{submission_id}/receipt/`. Student ownership is enforced; admins can inspect receipts for review.
5. Admin approval rechecks the object and stored course amount/currency before approving the related pending enrolment.

Accepted files: PDF, JPEG and PNG. Maximum size: 5 MiB. Presigned upload expiry: 5 minutes. Download link expiry: 2 minutes.

## Current status

The application adapter and API routes are committed, but no R2 bucket or token has been provisioned. Until the four environment variables are configured in the preview service, storage operations fail closed with HTTP 503. Do not create a Render service or expose credentials merely to test this adapter. Use the disposable PostgreSQL CI and mocked storage tests until a private bucket is configured.
