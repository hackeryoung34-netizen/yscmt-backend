from io import BytesIO

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape

import qrcode
from reportlab.lib.utils import ImageReader


def generate_certificate_pdf(certificate):

    buffer = BytesIO()

    pdf = canvas.Canvas(
        buffer,
        pagesize=landscape(A4)
    )

    width, height = landscape(A4)


    pdf.setFont("Helvetica-Bold", 30)
    pdf.drawCentredString(
        width / 2,
        height - 100,
        "YSCMT COMMUNITY"
    )


    pdf.setFont("Helvetica-Bold", 24)
    pdf.drawCentredString(
        width / 2,
        height - 160,
        "Certificate of Completion"
    )


    pdf.setFont("Helvetica", 18)

    pdf.drawCentredString(
        width / 2,
        height - 230,
        f"Student: {certificate.student.username}"
    )


    pdf.drawCentredString(
        width / 2,
        height - 270,
        f"Course: {certificate.course.name}"
    )


    pdf.drawCentredString(
        width / 2,
        height - 310,
        f"Certificate ID: {certificate.certificate_number}"
    )


    # QR CODE

    verify_url = (
        f"http://127.0.0.1:8000/api/certificates/verify/"
        f"{certificate.certificate_number}/"
    )


    qr = qrcode.make(verify_url)


    qr_buffer = BytesIO()

    qr.save(qr_buffer)

    qr_buffer.seek(0)


    pdf.drawImage(
        ImageReader(qr_buffer),
        width - 170,
        50,
        100,
        100
    )


    pdf.save()


    buffer.seek(0)


    return buffer
