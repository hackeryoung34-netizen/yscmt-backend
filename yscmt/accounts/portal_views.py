"""Views reserved for the independent YSCMT Student Portal API."""
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .portal_auth import SupabasePortalAuthentication


class PortalMeAPIView(APIView):
    """Return only the authenticated caller's own trusted portal identity."""

    authentication_classes = [SupabasePortalAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response({
            "id": str(user.id),
            "email": user.email,
            "role": user.role,
            "full_name": user.full_name,
            "phone": user.phone,
        })
