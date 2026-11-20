"""Small, bounded client for self-scoped Supabase portal RPCs."""
import json

import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    NotFound,
    PermissionDenied,
    ValidationError,
)


class PortalDataUnavailable(APIException):
    status_code = 503
    default_detail = "Portal data service is temporarily unavailable."
    default_code = "portal_data_unavailable"


class EnrollmentConflict(APIException):
    status_code = 409
    default_detail = "An enrolment already exists for this course."
    default_code = "enrollment_conflict"


def call_portal_rpc(request, function_name, payload=None, max_response_bytes=1048576):
    """Call an allow-listed RPC using only the caller's Supabase access token."""
    allowed = {
        "portal_list_courses",
        "portal_get_course_detail",
        "portal_get_course_lessons",
        "portal_create_enrollment",
    }
    if function_name not in allowed:
        raise ValueError("Unsupported portal RPC.")

    parts = request.headers.get("Authorization", "").split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise AuthenticationFailed("A valid Supabase bearer token is required.")
    token = parts[1]
    if not token or len(token) > 16384:
        raise AuthenticationFailed("Invalid access token.")

    project_url = getattr(settings, "SUPABASE_URL", "").rstrip("/")
    publishable_key = getattr(settings, "SUPABASE_PUBLISHABLE_KEY", "")
    if not project_url.startswith("https://") or not publishable_key:
        raise ImproperlyConfigured(
            "SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY must be configured."
        )

    response = None
    try:
        response = requests.post(
            f"{project_url}/rest/v1/rpc/{function_name}",
            headers={
                "apikey": publishable_key,
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json=payload or {},
            timeout=(3.05, 8),
            allow_redirects=False,
            stream=True,
        )
        body = response.raw.read(max_response_bytes + 1, decode_content=True)
        status_code = response.status_code
    except requests.RequestException as exc:
        raise PortalDataUnavailable() from exc
    finally:
        if response is not None:
            response.close()

    if len(body) > max_response_bytes:
        raise PortalDataUnavailable("Portal data service returned an oversized response.")
    if status_code == 401:
        raise AuthenticationFailed("Invalid or expired Supabase session.")
    if status_code == 403:
        raise PermissionDenied("This account cannot access the requested portal data.")
    if status_code == 404:
        raise NotFound("The requested portal resource was not found.")
    if status_code == 409:
        raise EnrollmentConflict()
    if status_code == 400:
        raise ValidationError("The portal request could not be processed.")
    if status_code != 200:
        raise PortalDataUnavailable()

    try:
        result = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise PortalDataUnavailable("Portal data service returned invalid data.") from exc

    if not isinstance(result, list) or any(not isinstance(row, dict) for row in result):
        raise PortalDataUnavailable("Portal data service returned an unexpected response.")
    return result
