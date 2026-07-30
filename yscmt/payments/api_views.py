from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import Payment
from courses.models import Course


class CreatePaymentAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):

        course = Course.objects.get(
            id=request.data["course"]
        )

        payment = Payment.objects.create(
            student=request.user,
            course=course,
            amount=course.price,
            payment_method=request.data["payment_method"],
            status="pending",
        )

        return Response({
            "payment_id": payment.id,
            "amount": payment.amount,
            "status": payment.status,
        })
