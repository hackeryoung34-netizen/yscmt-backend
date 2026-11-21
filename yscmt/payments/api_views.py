from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from rest_framework.exceptions import ValidationError
from django.shortcuts import get_object_or_404

from .models import Payment
from courses.models import Course


class CreatePaymentAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        course_id = request.data.get("course")
        payment_method = request.data.get("payment_method")

        if not course_id or not payment_method:
            raise ValidationError({
                "detail": "Both course and payment_method are required."
            })

        course = get_object_or_404(Course, pk=course_id)

        allowed_methods = {choice[0] for choice in Payment.PAYMENT_METHODS}
        if payment_method not in allowed_methods:
            raise ValidationError({
                "payment_method": "Choose a supported payment method."
            })

        if course.price <= 0:
            raise ValidationError({
                "course": "This course does not require a payment."
            })

        payment = Payment.objects.create(
            student=request.user,
            course=course,
            amount=course.price,
            payment_method=payment_method,
            status="pending",
        )

        return Response({
            "payment_id": payment.id,
            "amount": str(payment.amount),
            "status": payment.status,
            "message": "Payment request recorded. Access is granted only after payment is verified."
        }, status=status.HTTP_201_CREATED)
