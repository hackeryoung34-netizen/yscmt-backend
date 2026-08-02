from django.contrib import admin
from .models import Certificate


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = (
        "certificate_number",
        "student",
        "course",
        "issued_at",
    )

    list_filter = (
        "course",
        "issued_at",
    )

    search_fields = (
        "certificate_number",
        "student__username",
        "course__name",
    )

    ordering = ("-issued_at",)
