import io
import os
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from .storage import (
    ReceiptStorageError,
    generate_receipt_download_url,
    generate_receipt_upload_form,
    verify_uploaded_receipt,
)


R2_ENV = {
    "PORTAL_R2_ENDPOINT_URL": "https://account-id.r2.cloudflarestorage.com",
    "PORTAL_R2_ACCESS_KEY_ID": "test-access-key",
    "PORTAL_R2_SECRET_ACCESS_KEY": "test-secret-key",
    "PORTAL_R2_BUCKET": "yscmt-private-receipts",
}


class PortalReceiptStorageTests(SimpleTestCase):
    def test_missing_private_storage_configuration_fails_closed(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ReceiptStorageError):
                generate_receipt_upload_form(
                    storage_key="student/receipt.pdf",
                    owner_id="student-uuid",
                    content_type="application/pdf",
                    max_bytes=5 * 1024 * 1024,
                )

    @patch("student_portal.storage.boto3.client")
    def test_upload_authorization_is_private_owner_scoped_and_size_limited(self, client_factory):
        client = Mock()
        client.generate_presigned_post.return_value = {
            "url": "https://private-storage.example.test",
            "fields": {"key": "student/receipt.pdf"},
        }
        client_factory.return_value = client
        with patch.dict(os.environ, R2_ENV, clear=True):
            result = generate_receipt_upload_form(
                storage_key="student/receipt.pdf",
                owner_id="student-uuid",
                content_type="application/pdf",
                max_bytes=5 * 1024 * 1024,
                expires_seconds=300,
            )
        self.assertEqual(result["url"], "https://private-storage.example.test")
        kwargs = client.generate_presigned_post.call_args.kwargs
        self.assertEqual(kwargs["Bucket"], "yscmt-private-receipts")
        self.assertEqual(kwargs["Key"], "student/receipt.pdf")
        self.assertEqual(kwargs["Fields"]["x-amz-meta-owner-id"], "student-uuid")
        self.assertIn(["content-length-range", 1, 5 * 1024 * 1024], kwargs["Conditions"])
        self.assertEqual(kwargs["ExpiresIn"], 300)

    @patch("student_portal.storage.boto3.client")
    def test_finalize_verifies_size_mime_owner_and_pdf_signature(self, client_factory):
        client = Mock()
        client.head_object.return_value = {
            "ContentLength": 1200,
            "ContentType": "application/pdf",
            "Metadata": {"owner-id": "student-uuid"},
        }
        client.get_object.return_value = {"Body": io.BytesIO(b"%PDF-1.7 test document")}
        client_factory.return_value = client
        with patch.dict(os.environ, R2_ENV, clear=True):
            result = verify_uploaded_receipt(
                storage_key="student/receipt.pdf",
                owner_id="student-uuid",
                expected_content_type="application/pdf",
                max_bytes=5 * 1024 * 1024,
            )
        self.assertEqual(result["ContentLength"], 1200)
        client.get_object.assert_called_once_with(
            Bucket="yscmt-private-receipts",
            Key="student/receipt.pdf",
            Range="bytes=0-15",
        )

    @patch("student_portal.storage.boto3.client")
    def test_finalize_rejects_wrong_owner_and_invalid_file_signature(self, client_factory):
        client = Mock()
        client.head_object.return_value = {
            "ContentLength": 1200,
            "ContentType": "application/pdf",
            "Metadata": {"owner-id": "somebody-else"},
        }
        client_factory.return_value = client
        with patch.dict(os.environ, R2_ENV, clear=True):
            with self.assertRaises(ReceiptStorageError):
                verify_uploaded_receipt(
                    storage_key="student/receipt.pdf",
                    owner_id="student-uuid",
                    expected_content_type="application/pdf",
                    max_bytes=5 * 1024 * 1024,
                )

        client.head_object.return_value["Metadata"]["owner-id"] = "student-uuid"
        client.get_object.return_value = {"Body": io.BytesIO(b"not a PDF file")}
        with patch.dict(os.environ, R2_ENV, clear=True):
            with self.assertRaises(ReceiptStorageError):
                verify_uploaded_receipt(
                    storage_key="student/receipt.pdf",
                    owner_id="student-uuid",
                    expected_content_type="application/pdf",
                    max_bytes=5 * 1024 * 1024,
                )

    @patch("student_portal.storage.boto3.client")
    def test_finalize_rejects_oversized_receipt(self, client_factory):
        client = Mock()
        client.head_object.return_value = {
            "ContentLength": 5 * 1024 * 1024 + 1,
            "ContentType": "application/pdf",
            "Metadata": {"owner-id": "student-uuid"},
        }
        client_factory.return_value = client
        with patch.dict(os.environ, R2_ENV, clear=True):
            with self.assertRaises(ReceiptStorageError):
                verify_uploaded_receipt(
                    storage_key="student/receipt.pdf",
                    owner_id="student-uuid",
                    expected_content_type="application/pdf",
                    max_bytes=5 * 1024 * 1024,
                )

    @patch("student_portal.storage.boto3.client")
    def test_download_link_is_short_lived_and_forced_attachment(self, client_factory):
        client = Mock()
        client.generate_presigned_url.return_value = "https://private-storage.example.test/signed"
        client_factory.return_value = client
        with patch.dict(os.environ, R2_ENV, clear=True):
            result = generate_receipt_download_url(
                storage_key="student/receipt.pdf",
                file_name="bank receipt.pdf",
                expires_seconds=120,
            )
        self.assertEqual(result, "https://private-storage.example.test/signed")
        kwargs = client.generate_presigned_url.call_args.kwargs
        self.assertEqual(kwargs["ExpiresIn"], 120)
        self.assertEqual(kwargs["Params"]["ResponseCacheControl"], "private, no-store")
        self.assertEqual(kwargs["Params"]["ResponseContentDisposition"], 'attachment; filename="bank%20receipt.pdf"')
