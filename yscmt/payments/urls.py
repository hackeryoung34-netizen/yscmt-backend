from django.urls import path
from .api_views import CreatePaymentAPIView

urlpatterns = [
    path(
        "create/",
        CreatePaymentAPIView.as_view()
    ),
]
