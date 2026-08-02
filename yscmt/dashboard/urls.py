from django.urls import path

from .views import DashboardAPIView
from .admin_views import AdminDashboardAPIView

urlpatterns = [
    path("", DashboardAPIView.as_view(), name="dashboard"),
    path("admin/", AdminDashboardAPIView.as_view(), name="admin-dashboard"),
]
