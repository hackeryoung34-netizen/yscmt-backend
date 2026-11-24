import os
from urllib.parse import quote

import boto3
from botocore.config import Config


class ReceiptStorageError(Exception):
    pass


def _client():
    # Generic S3-compatible settings are preferred. Legacy R2 names remain
    # supported so an existing preview configuration does not break.
    endpoint = (
        os.environ.get("PORTAL_STORAGE_ENDPOINT_URL")
        or os.environ.get("PORTAL_R2_ENDPOINT_URL")
        or ""
    ).strip()
    access_key = (
        os.environ.get("PORTAL_STORAGE_ACCESS_KEY_ID")
        or os.environ.get("PORTAL_R2_ACCESS_KEY_ID")
        or ""
    ).strip()
    secret_key = (
        os.environ.get("PORTAL_STORAGE_SECRET_ACCESS_KEY")
        or os.environ.get("PORTAL_R2_SECRET_ACCESS_KEY")
        or ""
    ).strip()
    bucket = (
        os.environ.get("PORTAL_STORAGE_BUCKET")
        or os.environ.get("PORTAL_R2_BUCKET")
        or ""
    ).strip()
    region = (
        os.environ.get("PORTAL_STORAGE_REGION")
        or ("auto" if os.environ.get("PORTAL_R2_ENDPOINT_URL") else "us-east-1")
    ).strip()
    if not all([endpoint, access_key, secret_key, bucket, region]):
        raise ReceiptStorageError("Private S3-compatible storage credentials are not configured.")
    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
        config=Config(signature_version="s3v4", connect_timeout=5, read_timeout=10, retries={"max_attempts": 2}),
    )
    return client, bucket


def generate_receipt_upload_form(*, storage_key, owner_id, content_type, max_bytes, expires_seconds=300):
    try:
        client, bucket = _client()
        return client.generate_presigned_post(
            Bucket=bucket,
            Key=storage_key,
            Fields={"Content-Type": content_type, "x-amz-meta-owner-id": owner_id},
            Conditions=[
                {"Content-Type": content_type},
                {"x-amz-meta-owner-id": owner_id},
                ["content-length-range", 1, max_bytes],
            ],
            ExpiresIn=expires_seconds,
        )
    except ReceiptStorageError:
        raise
    except Exception as exc:
        raise ReceiptStorageError("Could not create a private receipt upload authorization.") from exc


def verify_uploaded_receipt(*, storage_key, owner_id, expected_content_type, max_bytes):
    try:
        client, bucket = _client()
        head = client.head_object(Bucket=bucket, Key=storage_key)
        size = head.get("ContentLength", 0)
        if size < 1 or size > max_bytes:
            raise ReceiptStorageError("Receipt file size is outside the permitted range.")
        if head.get("ContentType") != expected_content_type:
            raise ReceiptStorageError("Receipt content type does not match the authorized upload.")
        metadata = {str(k).lower(): str(v) for k, v in head.get("Metadata", {}).items()}
        if metadata.get("owner-id") != owner_id:
            raise ReceiptStorageError("Receipt object ownership metadata is invalid.")
        sample = client.get_object(Bucket=bucket, Key=storage_key, Range="bytes=0-15")["Body"].read(16)
        signatures = {
            "application/pdf": lambda b: b.startswith(b"%PDF-"),
            "image/jpeg": lambda b: b.startswith(bytes([255, 216, 255])),
            "image/png": lambda b: b.startswith(bytes([137, 80, 78, 71, 13, 10, 26, 10])),
        }
        checker = signatures.get(expected_content_type)
        if not checker or not checker(sample):
            raise ReceiptStorageError("Receipt file signature does not match its declared content type.")
        return head
    except ReceiptStorageError:
        raise
    except Exception as exc:
        raise ReceiptStorageError("Could not verify the uploaded private receipt.") from exc


def generate_receipt_download_url(*, storage_key, file_name, expires_seconds=120):
    try:
        client, bucket = _client()
        safe_name = quote((file_name or "receipt").replace('"', ""), safe="")
        return client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": bucket,
                "Key": storage_key,
                "ResponseContentDisposition": f'attachment; filename="{safe_name}"',
                "ResponseCacheControl": "private, no-store",
            },
            ExpiresIn=expires_seconds,
        )
    except ReceiptStorageError:
        raise
    except Exception as exc:
        raise ReceiptStorageError("Could not create a private receipt download link.") from exc
