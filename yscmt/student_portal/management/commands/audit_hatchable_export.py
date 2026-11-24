import json
import uuid
from collections import Counter
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError


SOURCE_TABLES = (
    "users", "student_profiles", "courses", "course_lessons", "enrollments",
    "lesson_progress", "course_exams", "exam_questions", "exam_sessions",
    "exam_attempts", "payment_submissions", "paystack_payments",
    "practice_submissions", "classroom_sessions", "classroom_attendance",
    "classroom_messages", "classroom_announcements",
    "classroom_teacher_replies", "student_certificates", "admin_audit_logs",
    "site_settings",
)


class SourceAudit:
    def __init__(self, data):
        self.data = data
        self.errors = []
        self.warnings = []
        self.counts = {}
        self.duplicates = Counter()
        self.orphans = Counter()
        self.quarantined = Counter()

    def rows(self, table):
        value = self.data.get(table, [])
        if not isinstance(value, list):
            self.errors.append(f"{table}: expected a JSON array")
            return []
        self.counts[table] = len(value)
        for index, row in enumerate(value):
            if not isinstance(row, dict):
                self.errors.append(f"{table}[{index}]: expected an object")
        return [row for row in value if isinstance(row, dict)]

    def ids(self, table, key="id", uuid_only=True):
        rows = self.rows(table)
        values = []
        for row in rows:
            value = row.get(key)
            if value is None or value == "":
                self.errors.append(f"{table}: missing {key}")
                continue
            if uuid_only:
                try:
                    uuid.UUID(str(value))
                except (ValueError, TypeError, AttributeError):
                    self.errors.append(f"{table}: invalid UUID in {key}")
            values.append(str(value))
        duplicates = [value for value, count in Counter(values).items() if count > 1]
        if duplicates:
            self.duplicates[table] += len(duplicates)
            self.errors.append(f"{table}: duplicate {key} values ({len(duplicates)})")
        return set(values)

    def fk(self, table, field, allowed, *, nullable=False):
        for row in self.rows(table):
            value = row.get(field)
            if nullable and value in (None, ""):
                continue
            if str(value) not in allowed:
                self.orphans[table] += 1
                self.errors.append(f"{table}: unresolved {field} reference ({self.orphans[table]})")

    def unique(self, table, fields, *, casefold_fields=()):
        seen = set()
        for row in self.rows(table):
            values = []
            skip = False
            for field in fields:
                value = row.get(field)
                if value in (None, ""):
                    skip = True
                    break
                if field in casefold_fields and isinstance(value, str):
                    value = value.strip().casefold()
                values.append(str(value))
            # Nullable unique columns permit multiple NULL/empty values in PostgreSQL.
            if skip:
                continue
            key = tuple(values)
            if key in seen:
                self.duplicates[table] += 1
                self.errors.append(
                    f"{table}: duplicate unique key ({', '.join(fields)})"
                )
            seen.add(key)

    def run(self):
        missing = sorted(set(SOURCE_TABLES) - set(self.data))
        extra = sorted(set(self.data) - set(SOURCE_TABLES))
        if missing:
            self.errors.append("Missing source tables: " + ", ".join(missing))
        if extra:
            self.warnings.append("Ignored unrecognized top-level keys: " + ", ".join(extra))

        users = self.ids("users", uuid_only=False)
        courses = self.ids("courses")
        lessons = self.ids("course_lessons")
        enrollments = self.ids("enrollments")
        exams = self.ids("course_exams")
        sessions = self.ids("exam_sessions")
        self.ids("student_profiles", key="user_id", uuid_only=False)
        self.ids("lesson_progress")
        self.ids("exam_questions")
        self.ids("exam_attempts")
        self.ids("payment_submissions")
        self.ids("paystack_payments")
        self.ids("practice_submissions")
        self.ids("classroom_sessions")
        self.ids("classroom_attendance")
        self.ids("classroom_messages")
        self.ids("classroom_announcements")
        self.ids("classroom_teacher_replies")
        self.ids("student_certificates")
        self.ids("admin_audit_logs", uuid_only=False)
        self.ids("site_settings", key="setting_key", uuid_only=False)

        # Mirror source unique indexes and target identity constraints before import.
        self.unique("users", ("email",), casefold_fields=("email",))
        self.unique("users", ("google_sub",))
        self.unique("users", ("hatchable_user_id",))
        self.unique("student_profiles", ("user_id",))
        self.unique("courses", ("title",), casefold_fields=("title",))
        self.unique("enrollments", ("user_id", "course_id"))
        self.unique("classroom_attendance", ("session_id", "user_id"))
        self.unique("paystack_payments", ("reference",))
        self.unique("student_certificates", ("certificate_code",))
        self.unique("student_certificates", ("user_id", "course_id"))
        self.unique("site_settings", ("setting_key",))

        for row in self.rows("users"):
            email = row.get("email")
            if not isinstance(email, str) or "@" not in email or email.strip() != email:
                self.errors.append("users: missing or malformed email address")

        for table, field, allowed, nullable in (
            ("student_profiles", "user_id", users, False),
            ("course_lessons", "course_id", courses, False),
            ("course_exams", "course_id", courses, False),
            ("enrollments", "user_id", users, False),
            ("enrollments", "course_id", courses, False),
            ("lesson_progress", "user_id", users, False),
            ("lesson_progress", "lesson_id", lessons, False),
            ("exam_questions", "exam_id", exams, False),
            ("exam_sessions", "exam_id", exams, False),
            ("exam_sessions", "user_id", users, False),
            ("exam_attempts", "exam_id", exams, False),
            ("exam_attempts", "user_id", users, False),
            ("paystack_payments", "enrolment_id", enrollments, False),
            ("paystack_payments", "user_id", users, False),
            ("paystack_payments", "course_id", courses, False),
            ("payment_submissions", "enrolment_id", enrollments, False),
            ("payment_submissions", "user_id", users, False),
            ("payment_submissions", "course_id", courses, False),
            ("student_certificates", "user_id", users, False),
            ("student_certificates", "course_id", courses, False),
            ("practice_submissions", "user_id", users, False),
            ("practice_submissions", "reviewed_by", users, True),
            ("classroom_sessions", "course_id", courses, False),
            ("classroom_attendance", "session_id", self.ids("classroom_sessions"), False),
            ("classroom_attendance", "user_id", users, False),
            ("classroom_messages", "course_id", courses, False),
            ("classroom_messages", "user_id", users, False),
            ("classroom_announcements", "course_id", courses, True),
            ("classroom_teacher_replies", "course_id", courses, False),
        ):
            self.fk(table, field, allowed, nullable=nullable)

        source_sessions = {}
        for row in self.rows("exam_sessions"):
            key = (str(row.get("exam_id")), str(row.get("user_id")), str(row.get("started_at")))
            source_sessions[key] = source_sessions.get(key, 0) + 1
        for row in self.rows("exam_attempts"):
            key = (str(row.get("exam_id")), str(row.get("user_id")), str(row.get("started_at")))
            matches = source_sessions.get(key, 0)
            if matches != 1:
                self.quarantined["exam_attempts"] += 1
        if self.quarantined["exam_attempts"]:
            self.warnings.append(
                f"exam_attempts: {self.quarantined['exam_attempts']} rows need quarantine "
                "because no unique source session matches exam_id/user_id/started_at"
            )

        self.warnings.extend([
            "Source users have no password hash field; imported accounts require password-reset onboarding.",
            "Source users have no role field; imported identities must default to student.",
            "Receipt objects must be exported and reconciled separately in private storage.",
        ])
        return {
            "mode": "dry_run_only",
            "source_tables": len(SOURCE_TABLES),
            "source_rows": sum(self.counts.values()),
            "counts": dict(sorted(self.counts.items())),
            "duplicates": dict(self.duplicates),
            "orphan_references": dict(self.orphans),
            "quarantined": dict(self.quarantined),
            "errors": self.errors,
            "warnings": self.warnings,
            "ready_for_import": not self.errors and not self.quarantined,
            "writes_performed": 0,
        }


class Command(BaseCommand):
    help = "Read and validate a Hatchable JSON export without writing to any database."

    def add_arguments(self, parser):
        parser.add_argument("--input", required=True, help="Path to a complete JSON export containing all 21 source tables.")

    def handle(self, *args, **options):
        path = Path(options["input"])
        if not path.is_file():
            raise CommandError("The specified source export file does not exist.")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CommandError("Could not read a valid UTF-8 JSON source export.") from exc
        if not isinstance(data, dict):
            raise CommandError("The source export must be a JSON object keyed by source table.")
        report = SourceAudit(data).run()
        self.stdout.write(json.dumps(report, indent=2, sort_keys=True))
        if report["errors"]:
            raise CommandError(f"Source dry-run found {len(report['errors'])} validation error(s). No database writes were performed.")
