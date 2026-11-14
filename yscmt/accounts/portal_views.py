"""Views reserved for the independent YSCMT Student Portal API."""
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .portal_auth import SupabasePortalAuthentication
from .portal_permissions import IsPortalStudent
from .portal_rpc import call_portal_rpc


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


class PortalStudentAPIView(APIView):
    authentication_classes = [SupabasePortalAuthentication]
    permission_classes = [IsAuthenticated, IsPortalStudent]


class PortalCourseListAPIView(PortalStudentAPIView):
    """List active courses and the current student's own enrollment state."""

    def get(self, request):
        rows = call_portal_rpc(request, "portal_list_courses")
        return Response({"results": rows})


class PortalCourseDetailAPIView(PortalStudentAPIView):
    """Return public course metadata; lesson content has a separate gate."""

    def get(self, request, course_id):
        rows = call_portal_rpc(
            request,
            "portal_get_course_detail",
            {"p_course_id": str(course_id)},
        )
        if not rows:
            raise NotFound("Course not found.")
        return Response(rows[0])


class PortalCourseLessonsAPIView(PortalStudentAPIView):
    """Return lessons only when the caller has approved/completed enrollment."""

    def get(self, request, course_id):
        rows = call_portal_rpc(
            request,
            "portal_get_course_lessons",
            {"p_course_id": str(course_id)},
        )
        return Response({"results": rows})
