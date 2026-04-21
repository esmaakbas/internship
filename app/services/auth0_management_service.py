"""Auth0 Management API service for admin user management.

This module is intentionally isolated from route handlers to keep admin
management logic testable and production-ready.
"""

import threading
import time
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote

import requests

from config import (
    AUTH0_DOMAIN,
    AUTH0_ALLOWED_ROLES,
    AUTH0_MANAGEMENT_AUDIENCE,
    AUTH0_MANAGEMENT_CLIENT_ID,
    AUTH0_MANAGEMENT_CLIENT_SECRET,
    AUTH0_DB_CONNECTION,
)


AUTH0_BASE_URL = f"https://{AUTH0_DOMAIN}"
AUTH0_MGMT_TOKEN_URL = f"{AUTH0_BASE_URL}/oauth/token"
AUTH0_MGMT_API_BASE = f"{AUTH0_BASE_URL}/api/v2"


class Auth0ManagementError(Exception):
    """Raised when Auth0 Management API operation fails."""


class Auth0ManagementService:
    """Minimal Auth0 Management API client with token caching."""

    def __init__(self) -> None:
        self._token: Optional[str] = None
        self._token_expires_at: float = 0.0
        self._token_lock = threading.RLock()
        self._role_ids_cache: Dict[str, str] = {}
        self._role_ids_cache_expires_at: float = 0.0
        self._user_role_cache: Dict[str, Tuple[str, float]] = {}
        self._role_ids_cache_ttl_seconds = 600
        self._user_role_cache_ttl_seconds = 120

    def _get_access_token(self) -> str:
        """Get or refresh Management API token using client credentials."""
        now = time.time()
        with self._token_lock:
            if self._token and now < self._token_expires_at:
                return self._token

            if not AUTH0_MANAGEMENT_CLIENT_ID or not AUTH0_MANAGEMENT_CLIENT_SECRET:
                raise Auth0ManagementError(
                    "Auth0 Management client credentials are not configured"
                )

            payload = {
                "grant_type": "client_credentials",
                "client_id": AUTH0_MANAGEMENT_CLIENT_ID,
                "client_secret": AUTH0_MANAGEMENT_CLIENT_SECRET,
                "audience": AUTH0_MANAGEMENT_AUDIENCE,
            }
            try:
                response = requests.post(AUTH0_MGMT_TOKEN_URL, json=payload, timeout=10)
                response.raise_for_status()
                data = response.json()
            except requests.RequestException as exc:
                raise Auth0ManagementError(
                    f"Failed to get Auth0 Management API token: {exc}"
                ) from exc

            token = data.get("access_token")
            expires_in = data.get("expires_in", 3600)
            if not token:
                raise Auth0ManagementError("Auth0 Management API token missing in response")

            # Refresh 30s early to reduce token-expiry race conditions.
            self._token = token
            self._token_expires_at = now + max(int(expires_in) - 30, 60)
            return self._token

    def _request(self, method: str, path: str, **kwargs):
        """Send authenticated request to Auth0 Management API."""
        token = self._get_access_token()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"
        headers.setdefault("Content-Type", "application/json")

        url = f"{AUTH0_MGMT_API_BASE}{path}"
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                timeout=15,
                **kwargs,
            )
            response.raise_for_status()
        except requests.HTTPError as exc:
            detail = ""
            try:
                detail = response.text
            except Exception:
                detail = str(exc)
            raise Auth0ManagementError(
                f"Auth0 Management API error ({method} {path}): {detail}"
            ) from exc
        except requests.RequestException as exc:
            raise Auth0ManagementError(
                f"Auth0 Management API request failed ({method} {path}): {exc}"
            ) from exc

        if response.status_code == 204:
            return None
        if not response.text:
            return None
        return response.json()

    def create_user(self, email: str, password: str, display_name: str) -> Dict[str, str]:
        """Create a new user in Auth0 database connection."""
        if not AUTH0_DB_CONNECTION:
            raise Auth0ManagementError(
                "AUTH0_DB_CONNECTION is required to create users"
            )

        payload = {
            "connection": AUTH0_DB_CONNECTION,
            "email": email,
            "password": password,
            "name": display_name,
            "email_verified": False,
        }
        data = self._request("POST", "/users", json=payload)
        user_id = data.get("user_id")
        if not user_id:
            raise Auth0ManagementError("Auth0 did not return user_id for created user")

        return {
            "user_id": user_id,
            "email": data.get("email", email),
            "display_name": data.get("name", display_name),
        }

    def _list_roles(self) -> List[dict]:
        data = self._request("GET", "/roles")
        if not isinstance(data, list):
            raise Auth0ManagementError("Unexpected roles response from Auth0")
        return data

    def _get_role_ids_map(self) -> Dict[str, str]:
        """Map allowed role names to Auth0 role IDs."""
        now = time.time()
        with self._token_lock:
            if self._role_ids_cache and now < self._role_ids_cache_expires_at:
                return dict(self._role_ids_cache)

        roles = self._list_roles()
        role_ids: Dict[str, str] = {}
        for role in roles:
            name = str(role.get("name", "")).strip().lower()
            role_id = role.get("id")
            if name in AUTH0_ALLOWED_ROLES and role_id:
                role_ids[name] = role_id

        missing = [r for r in AUTH0_ALLOWED_ROLES if r not in role_ids]
        if missing:
            raise Auth0ManagementError(
                f"Missing required Auth0 roles in tenant: {', '.join(sorted(missing))}"
            )

        with self._token_lock:
            self._role_ids_cache = dict(role_ids)
            self._role_ids_cache_expires_at = now + self._role_ids_cache_ttl_seconds

        return role_ids

    def get_user_role(self, auth0_user_id: str) -> str:
        """Return effective app role for a user based on Auth0 role assignments."""
        now = time.time()
        with self._token_lock:
            cached = self._user_role_cache.get(auth0_user_id)
            if cached and now < cached[1]:
                return cached[0]

        encoded_user_id = quote(auth0_user_id, safe="")
        roles = self._request("GET", f"/users/{encoded_user_id}/roles")
        if not isinstance(roles, list):
            raise Auth0ManagementError("Unexpected user roles response from Auth0")

        names = {str(r.get("name", "")).strip().lower() for r in roles}
        resolved_role = "unassigned"
        if "admin" in names:
            resolved_role = "admin"
        elif "user" in names:
            resolved_role = "user"

        with self._token_lock:
            self._user_role_cache[auth0_user_id] = (
                resolved_role,
                now + self._user_role_cache_ttl_seconds,
            )

        return resolved_role

    def set_user_role(self, auth0_user_id: str, target_role: str) -> None:
        """Set user role to exactly one of allowed roles in Auth0."""
        role = target_role.strip().lower()
        if role not in AUTH0_ALLOWED_ROLES:
            raise Auth0ManagementError(f"Invalid target role: {target_role}")

        role_ids = self._get_role_ids_map()
        target_role_id = role_ids[role]
        encoded_user_id = quote(auth0_user_id, safe="")

        existing_roles = self._request("GET", f"/users/{encoded_user_id}/roles")
        if not isinstance(existing_roles, list):
            raise Auth0ManagementError("Unexpected user roles response from Auth0")

        existing_role_ids = []
        for assigned in existing_roles:
            assigned_name = str(assigned.get("name", "")).strip().lower()
            assigned_id = assigned.get("id")
            if assigned_name in AUTH0_ALLOWED_ROLES and assigned_id:
                existing_role_ids.append(assigned_id)

        remove_ids = [rid for rid in existing_role_ids if rid != target_role_id]
        if remove_ids:
            self._request(
                "DELETE",
                f"/users/{encoded_user_id}/roles",
                json={"roles": remove_ids},
            )

        if target_role_id not in existing_role_ids:
            self._request(
                "POST",
                f"/users/{encoded_user_id}/roles",
                json={"roles": [target_role_id]},
            )

        with self._token_lock:
            self._user_role_cache[auth0_user_id] = (
                role,
                time.time() + self._user_role_cache_ttl_seconds,
            )

    def delete_user(self, auth0_user_id: str) -> None:
        """Delete a user from Auth0 Management API."""
        encoded_user_id = quote(auth0_user_id, safe="")
        self._request("DELETE", f"/users/{encoded_user_id}")
        with self._token_lock:
            self._user_role_cache.pop(auth0_user_id, None)


_auth0_management_service = Auth0ManagementService()


def create_auth0_user(email: str, password: str, display_name: str) -> Dict[str, str]:
    """Create user in Auth0."""
    return _auth0_management_service.create_user(email, password, display_name)


def set_auth0_user_role(auth0_user_id: str, role: str) -> None:
    """Set effective role in Auth0."""
    _auth0_management_service.set_user_role(auth0_user_id, role)


def get_auth0_user_role(auth0_user_id: str) -> str:
    """Read effective role from Auth0."""
    return _auth0_management_service.get_user_role(auth0_user_id)


def delete_auth0_user(auth0_user_id: str) -> None:
    """Delete user from Auth0 tenant."""
    _auth0_management_service.delete_user(auth0_user_id)
