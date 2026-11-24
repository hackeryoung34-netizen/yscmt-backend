import json
import tempfile
import uuid
from pathlib import Path

from django.core.management import call_command, CommandError
from django.test import SimpleTestCase
from io import StringIO


def source_fixture():
    uid, cid, lid, eid = [str(uuid.uuid4()) for _ in range(4)]
    sid, aid = [str(uuid.uuid4()) for _ in range(2)]
    started = "2026-01-01T10:00:00Z"
    return {
        "users": [{"id": "hatchable-user-1", "email": "student@example.test", "name": "Student"}],
        "student_profiles": [],
        "courses": [{"id": cid}],
        "course_lessons": [{"id": lid, "course_id": cid}],
        "enrollments": [{"id": uid, "user_id": "hatchable-user-1", "course_id": cid}],
        "lesson_progress": [{"id": str(uuid.uuid4()), "user_id": "hatchable-user-1", "lesson_id": lid}],
        "course_exams": [{"id": eid, "course_id": cid}],
        "exam_questions": [{"id": str(uuid.uuid4()), "exam_id": eid}],
        "exam_sessions": [{"id": sid, "exam_id": eid, "user_id": "hatchable-user-1", "started_at": started}],
        "exam_attempts": [{"id": aid, "exam_id": eid, "user_id": "hatchable-user-1", "started_at": started}],
        "payment_submissions": [],
        "paystack_payments": [],
        "practice_submissions": [],
        "classroom_sessions": [],
        "classroom_attendance": [],
        "classroom_messages": [],
        "classroom_announcements": [],
        "classroom_teacher_replies": [],
        "student_certificates": [],
        "admin_audit_logs": [{"id": 1}],
        "site_settings": [{"setting_key": "portal"}],
    }


class HatchableExportAuditTests(SimpleTestCase):
    def run_audit(self, payload):
        handle = tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".json", delete=False)
        try:
            json.dump(payload, handle)
            handle.close()
            output = StringIO()
            call_command("audit_hatchable_export", input=handle.name, stdout=output)
            return json.loads(output.getvalue())
        finally:
            Path(handle.name).unlink(missing_ok=True)

    def test_valid_synthetic_export_is_read_only_and_ready(self):
        report = self.run_audit(source_fixture())
        self.assertTrue(report["ready_for_import"])
        self.assertEqual(report["source_tables"], 21)
        self.assertEqual(report["writes_performed"], 0)
        self.assertEqual(report["quarantined"], {})

    def test_missing_foreign_key_is_reported_without_writes(self):
        payload = source_fixture()
        payload["course_lessons"][0]["course_id"] = str(uuid.uuid4())
        report = self.run_audit(payload)
        self.assertFalse(report["ready_for_import"])
        self.assertEqual(report["orphan_references"]["course_lessons"], 1)
        self.assertEqual(report["writes_performed"], 0)

    def test_attempt_without_unique_session_is_quarantined(self):
        payload = source_fixture()
        payload["exam_sessions"] = []
        report = self.run_audit(payload)
        self.assertFalse(report["ready_for_import"])
        self.assertEqual(report["quarantined"]["exam_attempts"], 1)
        self.assertEqual(report["writes_performed"], 0)

    def test_duplicate_source_ids_are_rejected(self):
        payload = source_fixture()
        payload["courses"].append(dict(payload["courses"][0]))
        report = self.run_audit(payload)
        self.assertFalse(report["ready_for_import"])
        self.assertEqual(report["duplicates"]["courses"], 1)

    def test_invalid_json_export_is_rejected(self):
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".json", delete=False) as handle:
            handle.write("{not-json")
            path = handle.name
        try:
            with self.assertRaises(CommandError):
                call_command("audit_hatchable_export", input=path, stdout=StringIO())
        finally:
            Path(path).unlink(missing_ok=True)
