from io import BytesIO

import qrcode

from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


def generate_certificate_pdf(certificate):
    buffer = BytesIO()

    page_width, page_height = landscape(A4)

    pdf = canvas.Canvas(
        buffer,
        pagesize=(page_width, page_height),
    )

    # ==========================================================
    # Background
    # ==========================================================

    pdf.setFillColor(colors.HexColor("#f8fafc"))
    pdf.rect(
        0,
        0,
        page_width,
        page_height,
        fill=1,
        stroke=0,
    )

    # ==========================================================
    # Decorative borders
    # ==========================================================

    pdf.setStrokeColor(colors.HexColor("#1d4ed8"))
    pdf.setLineWidth(5)

    pdf.rect(
        25,
        25,
        page_width - 50,
        page_height - 50,
        fill=0,
        stroke=1,
    )

    pdf.setStrokeColor(colors.HexColor("#93c5fd"))
    pdf.setLineWidth(1)

    pdf.rect(
        38,
        38,
        page_width - 76,
        page_height - 76,
        fill=0,
        stroke=1,
    )

    # ==========================================================
    # Header
    # ==========================================================

    pdf.setFillColor(colors.HexColor("#1e3a8a"))
    pdf.setFont("Helvetica-Bold", 28)

    pdf.drawCentredString(
        page_width / 2,
        page_height - 85,
        "YSCMT COMMUNITY",
    )

    pdf.setFillColor(colors.HexColor("#475569"))
    pdf.setFont("Helvetica", 11)

    pdf.drawCentredString(
        page_width / 2,
        page_height - 108,
        "LEARN • BUILD • INNOVATE",
    )

    # ==========================================================
    # Certificate title
    # ==========================================================

    pdf.setFillColor(colors.HexColor("#111827"))
    pdf.setFont("Helvetica-Bold", 25)

    pdf.drawCentredString(
        page_width / 2,
        page_height - 155,
        "CERTIFICATE OF COMPLETION",
    )

    pdf.setFillColor(colors.HexColor("#64748b"))
    pdf.setFont("Helvetica", 11)

    pdf.drawCentredString(
        page_width / 2,
        page_height - 178,
        "This certificate is proudly presented to",
    )

    # ==========================================================
    # Student
    # ==========================================================

    student_name = certificate.student.get_full_name().strip()

    if not student_name:
        student_name = certificate.student.username

    pdf.setFillColor(colors.HexColor("#1d4ed8"))
    pdf.setFont("Helvetica-Bold", 25)

    pdf.drawCentredString(
        page_width / 2,
        page_height - 225,
        student_name,
    )

    # underline
    pdf.setStrokeColor(colors.HexColor("#93c5fd"))
    pdf.setLineWidth(1)

    pdf.line(
        page_width / 2 - 170,
        page_height - 235,
        page_width / 2 + 170,
        page_height - 235,
    )

    # ==========================================================
    # Completion text
    # ==========================================================

    pdf.setFillColor(colors.HexColor("#475569"))
    pdf.setFont("Helvetica", 12)

    pdf.drawCentredString(
        page_width / 2,
        page_height - 270,
        "has successfully completed the course",
    )

    # ==========================================================
    # Course name
    # ==========================================================

    pdf.setFillColor(colors.HexColor("#111827"))
    pdf.setFont("Helvetica-Bold", 22)

    pdf.drawCentredString(
        page_width / 2,
        page_height - 310,
        certificate.course.name,
    )

    # ==========================================================
    # Certificate details
    # ==========================================================

    issued_date = certificate.issued_at.strftime("%d %B %Y")

    pdf.setFillColor(colors.HexColor("#64748b"))
    pdf.setFont("Helvetica", 10)

    pdf.drawString(
        80,
        95,
        f"Issued: {issued_date}",
    )

    pdf.drawString(
        80,
        77,
        f"Certificate ID: {certificate.certificate_number}",
    )

    # ==========================================================
    # Verification QR
    # ==========================================================

    frontend_url = getattr(
        settings,
        "FRONTEND_URL",
        "http://localhost:5175",
    ).rstrip("/")

    verify_url = (
        f"{frontend_url}/certificate/verify/"
        f"{certificate.certificate_number}"
    )

    qr = qrcode.make(verify_url)

    qr_buffer = BytesIO()
    qr.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)

    pdf.drawImage(
        ImageReader(qr_buffer),
        page_width - 165,
        55,
        width=95,
        height=95,
        preserveAspectRatio=True,
        mask="auto",
    )

    pdf.setFillColor(colors.HexColor("#64748b"))
    pdf.setFont("Helvetica", 8)

    pdf.drawCentredString(
        page_width - 117,
        43,
        "Scan to verify",
    )

    # ==========================================================
    # Signature
    # ==========================================================

    pdf.setStrokeColor(colors.HexColor("#94a3b8"))
    pdf.setLineWidth(1)

    pdf.line(
        page_width / 2 - 80,
        85,
        page_width / 2 + 80,
        85,
    )

    pdf.setFillColor(colors.HexColor("#475569"))
    pdf.setFont("Helvetica", 9)

    pdf.drawCentredString(
        page_width / 2,
        70,
        "YSCMT Community",
    )

    pdf.setFont("Helvetica", 8)

    pdf.drawCentredString(
        page_width / 2,
        56,
        "Authorized Certificate",
    )

    # ==========================================================
    # Finish
    # ==========================================================

    pdf.showPage()
    pdf.save()

    buffer.seek(0)

    return buffer
