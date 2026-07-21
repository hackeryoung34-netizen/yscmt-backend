from django.urls import path
from .views import (
    ProgressListCreateAPIView,
    ProgressDetailAPIView,
)

urlpatterns = [
    path(
        "",
        ProgressListCreateAPIView.as_view(),
        name="progress-list",
    ),
    path(
        "<int:pk>/",
        ProgressDetailAPIView.as_view(),
        name="progress-detail",
    ),
]
