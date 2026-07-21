from django.http import FileResponse
from .pdf import generate_certificate_pdf
from uuid import uuid4

from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Certificate
from .serializers import CertificateSerializer


class CertificateListCreateAPIView(generics.ListCreateAPIView):

    serializer_class = CertificateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Certificate.objects.filter(
            student=self.request.user
        )

    def perform_create(self, serializer):

        serializer.save(
            student=self.request.user,
            certificate_number=f"YSCMT-{uuid4().hex[:8].upper()}"
        )


class CertificateDetailAPIView(generics.RetrieveDestroyAPIView):

    serializer_class = CertificateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Certificate.objects.filter(
            student=self.request.user
        )

class CertificateDownloadAPIView(generics.RetrieveAPIView):

    permission_classes = [IsAuthenticated]

    queryset = Certificate.objects.all()


    def retrieve(self, request, *args, **kwargs):

        certificate = self.get_object()

        pdf = generate_certificate_pdf(
            certificate
        )

        return FileResponse(
            pdf,
            as_attachment=True,
            filename="YSCMT_certificate.pdf"
        )
from rest_framework.response import Response
from rest_framework.views import APIView


class CertificateVerifyAPIView(APIView):

    def get(self, request, certificate_number):

        try:
            certificate = Certificate.objects.get(
                certificate_number=certificate_number
            )

            return Response({
                "status": "VALID",
                "certificate_number": certificate.certificate_number,
                "student": certificate.student.username,
                "course": certificate.course.name,
                "issued_at": certificate.issued_at
            })

        except Certificate.DoesNotExist:

            return Response({
                "status": "INVALID",
                "message": "Certificate not found"
            }, status=404)


class CertificateVerifyAPIView(generics.RetrieveAPIView):

    queryset = Certificate.objects.all()

    def retrieve(self, request, *args, **kwargs):

        certificate_number = kwargs.get(
            "certificate_number"
        )

        try:
            certificate = Certificate.objects.get(
                certificate_number=certificate_number
            )

            return Response({
                "valid": True,
                "certificate_number": certificate.certificate_number,
                "student": certificate.student.username,
                "course": certificate.course.name,
                "issued_at": certificate.issued_at
            })

        except Certificate.DoesNotExist:

            return Response({
                "valid": False,
                "message": "Certificate not found"
            })
