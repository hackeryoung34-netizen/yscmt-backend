import os
import re

from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.db import transaction

from student_portal.models import PortalIdentity


class Command(BaseCommand):
    help = "Create or promote the explicitly configured YSCMT Student Portal administrator."

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Confirm that the configured email is authorized to become a portal administrator.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        email = os.environ.get("PORTAL_BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
        if not email:
            raise CommandError("Set PORTAL_BOOTSTRAP_ADMIN_EMAIL before running this command.")
        try:
            validate_email(email)
        except Exception as exc:
            raise CommandError("PORTAL_BOOTSTRAP_ADMIN_EMAIL is not a valid email address.") from exc
        if not options.get("confirm") or os.environ.get("PORTAL_BOOTSTRAP_ADMIN_CONFIRM") != "YES":
            raise CommandError(
                "For safety, pass --confirm and set PORTAL_BOOTSTRAP_ADMIN_CONFIRM=YES."
            )

        identity = PortalIdentity.objects.filter(email__iexact=email).first()
        if identity:
            identity.role = PortalIdentity.ROLE_ADMIN
            identity.is_active = True
            if not identity.has_usable_password():
                identity.must_reset_password = True
            identity.save(update_fields=["role", "is_active", "must_reset_password", "updated_at"])
            created = False
        else:
            requested = os.environ.get("PORTAL_BOOTSTRAP_ADMIN_USERNAME", "").strip()
            base = requested or email.split("@", 1)[0]
            base = re.sub(r"[^A-Za-z0-9_.-]", "-", base).strip("-.")[:130] or "portal-admin"
            username = base
            if PortalIdentity.objects.filter(username__iexact=username).exists():
                username = f"{base[:120]}-admin"
            if PortalIdentity.objects.filter(username__iexact=username).exists():
                raise CommandError("The bootstrap administrator username is already in use; set PORTAL_BOOTSTRAP_ADMIN_USERNAME.")
            identity = PortalIdentity(
                username=username,
                email=email,
                role=PortalIdentity.ROLE_ADMIN,
                is_active=True,
                must_reset_password=True,
            )
            identity.set_unusable_password()
            identity.save()
            created = True

        self.stdout.write(self.style.SUCCESS(
            f"Portal administrator {'created' if created else 'promoted'}: {identity.email}. "
            "No password was printed or generated. Configure SMTP, then use the password-reset email flow."
        ))
