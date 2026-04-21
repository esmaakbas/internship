"""Delegated JWT creation for secure Flask -> Alex service calls."""

import hashlib
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Dict

from jose import jwt

from config import (
    ALEX_DELEGATION_ALGORITHM,
    ALEX_DELEGATION_ACTIVE_KID,
    ALEX_DELEGATION_AUDIENCE,
    ALEX_DELEGATION_ISSUER,
    ALEX_DELEGATION_PRIVATE_KEY,
    ALEX_SECURITY_AUDIT_HASH_SALT,
    ALEX_SECURITY_AUDIT_LOG_ENABLED,
    ALEX_DELEGATION_TTL_SECONDS,
)


logger = logging.getLogger(__name__)


class DelegationTokenError(ValueError):
    """Raised when a delegated token cannot be created safely."""


def _normalise_private_key(raw_key: str) -> str:
    """Allow PEM keys passed via env using escaped newlines."""
    return raw_key.replace("\\n", "\n").strip()


def _stable_hash(value: str) -> str:
    raw = f"{ALEX_SECURITY_AUDIT_HASH_SALT}:{value}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _emit_security_log(payload: Dict[str, object]) -> None:
    if not ALEX_SECURITY_AUDIT_LOG_ENABLED:
        return
    logger.info(json.dumps(payload, sort_keys=True))


def _validate_user_context(user_context: Dict[str, object]) -> None:
    auth0_sub = str(user_context.get("auth0_sub") or "").strip()

    if not auth0_sub.startswith("auth0|"):
        raise DelegationTokenError("Authenticated Auth0 subject is required for delegation")


def build_alex_delegation_token(
    user_context: Dict[str, object],
    request_id: str,
) -> str:
    """Create a short-lived delegated JWT for Alex's service.

    The token encodes only minimal trusted identity and authorization claims.
    """
    if not isinstance(user_context, dict):
        raise DelegationTokenError("Authenticated user context is required")

    _validate_user_context(user_context)

    if not ALEX_DELEGATION_PRIVATE_KEY:
        raise DelegationTokenError("ALEX_DELEGATION_PRIVATE_KEY is required")
    if not ALEX_DELEGATION_ACTIVE_KID:
        raise DelegationTokenError("ALEX_DELEGATION_ACTIVE_KID is required")

    ttl_seconds = max(30, min(int(ALEX_DELEGATION_TTL_SECONDS), 300))
    now = int(time.time())
    jti = uuid.uuid4().hex

    claims = {
        "iss": ALEX_DELEGATION_ISSUER,
        "sub": str(user_context["auth0_sub"]),
        "user_id": str(user_context["auth0_sub"]),
        "aud": ALEX_DELEGATION_AUDIENCE,
        "iat": now,
        "exp": now + ttl_seconds,
        "jti": jti,
        "rid": request_id,
    }

    headers = {
        "typ": "JWT",
        "kid": ALEX_DELEGATION_ACTIVE_KID,
    }

    private_key = _normalise_private_key(ALEX_DELEGATION_PRIVATE_KEY)
    encoded = jwt.encode(claims, private_key, algorithm=ALEX_DELEGATION_ALGORITHM, headers=headers)

    _emit_security_log(
        {
            "event": "delegation_token_issued",
            "request_id": request_id,
            "iss": claims["iss"],
            "aud": claims["aud"],
            "kid": headers["kid"],
            "sub_hash": _stable_hash(str(claims["sub"])),
            "jti_hash": _stable_hash(jti),
            "outcome": "allow",
            "reason_code": "token_issued",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )

    return encoded
