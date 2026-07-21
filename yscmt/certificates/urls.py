from django.urls import path

from .views import (
    CertificateListCreateAPIView,
    CertificateDetailAPIView,
    CertificateDownloadAPIView,
    CertificateVerifyAPIView,
)

urlpatterns = [

    path(
        "",
        CertificateListCreateAPIView.as_view(),
        name="certificate-list"
    ),

    path(
        "<int:pk>/",
        CertificateDetailAPIView.as_view(),
        name="certificate-detail"
    ),

    path(
        "<int:pk>/download/",
        CertificateDownloadAPIView.as_view(),
        name="certificate-download"
    ),

    path(
        "verify/<str:certificate_number>/",
        CertificateVerifyAPIView.as_view(),
        name="certificate-verify"
    ),

]
