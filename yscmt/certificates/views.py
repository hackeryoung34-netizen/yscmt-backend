from django.http import FileResponse
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Certificate
from .pdf import generate_certificate_pdf
from .serializers import CertificateSerializer


class CertificateListCreateAPIView(generics.ListAPIView):
    serializer_class = CertificateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Certificate.objects.select_related("student", "course")
        if self.request.user.is_staff:
            return queryset
        return queryset.filter(student=self.request.user)


class CertificateDetailAPIView(generics.RetrieveAPIView):
    serializer_class = CertificateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Certificate.objects.select_related("student", "course")
        if self.request.user.is_staff:
            return queryset
        return queryset.filter(student=self.request.user)


class CertificateDownloadAPIView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Certificate.objects.select_related("student", "course")
        if self.request.user.is_staff:
            return queryset
        return queryset.filter(student=self.request.user)

    def retrieve(self, request, *args, **kwargs):
        certificate = self.get_object()
        pdf = generate_certificate_pdf(certificate)
        return FileResponse(
            pdf,
            as_attachment=True,
            filename="YSCMT_certificate.pdf",
        )


class CertificateVerifyAPIView(APIView):
    permission_classes = []

    def get(self, request, certificate_number):
        try:
            certificate = Certificate.objects.select_related(
                "student", "course"
            ).get(certificate_number=certificate_number)
        except Certificate.DoesNotExist:
            return Response(
                {"valid": False, "message": "Certificate not found"},
                status=404,
            )

        return Response({
            "valid": True,
            "certificate_number": certificate.certificate_number,
            "student": certificate.student.username,
            "course": certificate.course.name,
            "issued_at": certificate.issued_at,
        })
