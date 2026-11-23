from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.core.exceptions import ValidationError
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError
from .models import PortalIdentity

class PortalJWTAuthentication(BaseAuthentication):
    def authenticate(self, request):
        header = request.headers.get("Authorization", "")
        if not header:
            return None
        parts = header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise AuthenticationFailed("Use Authorization: Bearer <access-token>.")
        try:
            token = AccessToken(parts[1])
            identity_id = token.get("portal_identity_id")
            if not identity_id:
                raise AuthenticationFailed("This token is not a Student Portal token.")
            identity = PortalIdentity.objects.get(pk=identity_id, is_active=True)
        except (TokenError, PortalIdentity.DoesNotExist, ValidationError, ValueError, TypeError):
            raise AuthenticationFailed("Invalid or expired portal session.")
        return identity, token

    def authenticate_header(self, request):
        return "Bearer"
