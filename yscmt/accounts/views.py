from django.contrib.auth.models import User

from rest_framework import generics
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import RegisterSerializer


class RegisterAPIView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer


class ProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response({
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
        })

    def patch(self, request):
        user = request.user
        user.first_name = request.data.get("first_name", user.first_name)
        user.last_name = request.data.get("last_name", user.last_name)
        if "email" in request.data:
            email = request.data.get("email", "")
            if not isinstance(email, str):
                return Response(
                    {"email": ["Enter a valid email address."]},
                    status=400,
                )
            email = email.strip().lower()
            if email and User.objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
                return Response(
                    {"email": ["This email address is already in use."]},
                    status=400,
                )
            user.email = email

        user.save()
        return Response({
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
        })


class AdminStudentListAPIView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        students = User.objects.filter(is_staff=False).order_by("-date_joined")
        return Response([
            {
                "id": student.id,
                "username": student.username,
                "email": student.email,
                "first_name": student.first_name,
                "last_name": student.last_name,
            }
            for student in students
        ])
