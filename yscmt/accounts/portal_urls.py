"""URL namespace for the independent portal API only."""
from django.urls import path

from .portal_views import PortalMeAPIView

app_name = "portal_api"

urlpatterns = [
    path("me/", PortalMeAPIView.as_view(), name="me"),
]
