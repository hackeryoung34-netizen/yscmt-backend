"""Supabase-backed authentication for the independent YSCMT portal API.

This adapter is opt-in per view. It does not create Django users or accept
roles from client-controlled JWT metadata.
"""
from dataclasses import dataclass
from uuid import UUID

import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import APIException, AuthenticationFailed


class IdentityServiceUnavailable(APIException):
    status_code = 503
    default_detail = "Identity service is temporarily unavailable."
    default_code = "identity_service_unavailable"


@dataclass(frozen=True)
class PortalPrincipal:
    id: UUID
    email: str
    role: str
    full_name: str
    phone: str

    @property
    def pk(self):
        return self.id

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    @property
    def is_active(self):
        return True


class SupabasePortalAuthentication(BaseAuthentication):
    """Validate a Supabase access token and resolve its trusted role via RPC."""

    allowed_roles = {"student", "instructor", "admin"}
    timeout = (3.05, 8)
    max_response_bytes = 8192

    def authenticate(self, request):
        header = request.headers.get("Authorization", "")
        if not header:
            return None

        parts = header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise AuthenticationFailed("Use Authorization: Bearer <access-token>.")

        token = parts[1]
        if not token or len(token) > 16384:
            raise AuthenticationFailed("Invalid access token.")

        project_url = getattr(settings, "SUPABASE_URL", "").rstrip("/")
        publishable_key = getattr(settings, "SUPABASE_PUBLISHABLE_KEY", "")
        if not project_url.startswith("https://") or not publishable_key:
            raise ImproperlyConfigured(
                "SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY must be configured."
            )

        endpoint = f"{project_url}/rest/v1/rpc/portal_get_my_identity"
        try:
            response = requests.post(
                endpoint,
                headers={
                    "apikey": publishable_key,
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json={},
                timeout=self.timeout,
                allow_redirects=False,
                stream=True,
            )
            try:
                body = response.raw.read(self.max_response_bytes + 1, decode_content=True)
            finally:
                response.close()
        except requests.RequestException as exc:
            raise IdentityServiceUnavailable() from exc

        if len(body) > self.max_response_bytes:
            raise IdentityServiceUnavailable("Identity service returned an oversized response.")

        if response.status_code in (401, 403):
            raise AuthenticationFailed("Invalid or expired Supabase session.")
        if response.status_code != 200:
            raise IdentityServiceUnavailable()

        try:
            # Streaming responses are intentionally bounded above. Decode only
            # the bounded body rather than reading an unbounded cached response.
            import json
            rows = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            raise IdentityServiceUnavailable("Identity service returned invalid data.")

        if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
            raise AuthenticationFailed("No portal identity is assigned to this account.")

        row = rows[0]
        try:
            user_id = UUID(row["user_id"])
        except (KeyError, TypeError, ValueError):
            raise IdentityServiceUnavailable("Identity service returned an invalid user ID.")

        role = row.get("role")
        if role not in self.allowed_roles:
            raise AuthenticationFailed("This account has no valid portal role.")

        principal = PortalPrincipal(
            id=user_id,
            email=str(row.get("email") or ""),
            role=role,
            full_name=str(row.get("full_name") or ""),
            phone=str(row.get("phone") or ""),
        )
        return principal, {"provider": "supabase"}

    def authenticate_header(self, request):
        return "Bearer"
