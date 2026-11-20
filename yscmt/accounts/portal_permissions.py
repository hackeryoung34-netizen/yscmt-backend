"""Role permissions for the independent YSCMT portal API."""
from rest_framework.permissions import BasePermission


class IsPortalRole(BasePermission):
    allowed_roles = frozenset()

    def has_permission(self, request, view):
        user = request.user
        return bool(
            getattr(user, "is_authenticated", False)
            and getattr(user, "role", None) in self.allowed_roles
        )


class IsPortalStudent(IsPortalRole):
    allowed_roles = frozenset({"student"})


class IsPortalInstructor(IsPortalRole):
    allowed_roles = frozenset({"instructor"})


class IsPortalAdmin(IsPortalRole):
    allowed_roles = frozenset({"admin"})


class IsPortalStaff(IsPortalRole):
    allowed_roles = frozenset({"instructor", "admin"})
