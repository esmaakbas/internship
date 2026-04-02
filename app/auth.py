"""Authentication module for Auth0 integration.

This module provides:
- Auth0 OAuth2 login/logout flow
- JWT token validation (proper signature verification with JWK)
- User synchronization with local database
- Protected route decorators
- Session management with secure cookies

ARCHITECTURE:
- Auth0 is used ONLY for authentication (identity verification)
- Authorization (roles) is managed ONLY in the local database
- New users get default role 'user'; admins are promoted manually in DB

SECURITY FEATURES:
- Proper JWT signature verification using Auth0's JWK
- CSRF protection via state parameter
- HTTPOnly, Secure, SameSite cookies
- Session regeneration after login (prevents session fixation)
- Deactivated users (is_active=False) cannot log in
- Atomic database transactions for user sync
"""

import secrets
import urllib.parse
import time
import threading
from functools import wraps
from typing import Optional, Callable, Any

import requests
from flask import (
    Flask,
    session,
    redirect,
    url_for,
    request,
    g,
    jsonify,
    current_app,
)
from jose import jwt, JWTError
from jose.exceptions import JWTClaimsError, ExpiredSignatureError

from config import (
    AUTH0_DOMAIN,
    AUTH0_CLIENT_ID,
    AUTH0_CLIENT_SECRET,
    AUTH0_CALLBACK_URL,
    AUTH0_AUDIENCE,
)
from database import get_or_create_user, get_user_by_id


# Auth0 URLs
AUTH0_BASE_URL = f"https://{AUTH0_DOMAIN}"
AUTH0_AUTHORIZE_URL = f"{AUTH0_BASE_URL}/authorize"
AUTH0_TOKEN_URL = f"{AUTH0_BASE_URL}/oauth/token"
AUTH0_USERINFO_URL = f"{AUTH0_BASE_URL}/userinfo"
AUTH0_JWKS_URL = f"{AUTH0_BASE_URL}/.well-known/jwks.json"


class AuthError(Exception):
    """Custom exception for authentication errors."""

    def __init__(self, message: str, status_code: int = 401):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class JWKSCache:
    """Thread-safe JWKS cache with TTL to prevent excessive Auth0 API calls.

    SECURITY: Caches Auth0's public keys for JWT verification to avoid:
    - Rate limiting from Auth0 JWKS endpoint
    - Performance degradation on every authentication
    - Single point of failure during Auth0 service issues
    """

    def __init__(self, ttl_seconds: int = 300):  # 5 minute TTL
        self.ttl_seconds = ttl_seconds
        self._cache = {}
        self._cache_time = 0
        self._lock = threading.RLock()

    def get_jwks(self) -> dict:
        """Get JWKS from cache or fetch from Auth0 if expired.

        Returns:
            dict: JWKS data from Auth0

        Raises:
            AuthError: If JWKS cannot be fetched
        """
        with self._lock:
            current_time = time.time()

            # Check if cache is valid
            if (self._cache and
                current_time - self._cache_time < self.ttl_seconds):
                return self._cache

            # Cache expired or empty - fetch new JWKS
            try:
                response = requests.get(AUTH0_JWKS_URL, timeout=10)
                response.raise_for_status()
                jwks = response.json()

                # Validate JWKS structure
                if not isinstance(jwks, dict) or 'keys' not in jwks:
                    raise AuthError("Invalid JWKS format from Auth0", 500)

                # Update cache
                self._cache = jwks
                self._cache_time = current_time

                return jwks

            except requests.RequestException as exc:
                # If we have stale cache, use it as fallback
                if self._cache:
                    current_app.logger.warning(
                        f"Auth0 JWKS fetch failed, using stale cache: {exc}"
                    )
                    return self._cache
                raise AuthError(f"Failed to fetch JWKS from Auth0: {exc}", 500) from exc

    def clear(self):
        """Clear the JWKS cache (useful for testing)."""
        with self._lock:
            self._cache = {}
            self._cache_time = 0


# Global JWKS cache instance
_jwks_cache = JWKSCache()


def get_jwks() -> dict:
    """Fetch Auth0's JSON Web Key Set (JWKS) for token validation.

    Uses caching to prevent excessive API calls to Auth0.
    This is used to verify JWT signatures.

    Returns:
        dict: JWKS data from Auth0

    Raises:
        AuthError: If JWKS cannot be fetched
    """
    return _jwks_cache.get_jwks()


def verify_jwt(token: str, expected_audience: Optional[str] = None) -> dict:
    """Verify and decode a JWT token from Auth0.

    SECURITY: This performs PROPER signature verification using Auth0's JWK,
    not just base64 decoding. It validates:
    - Signature is valid (using Auth0's public key)
    - Token is not expired
    - Issuer matches Auth0 domain
    - Audience matches expected audience

    Args:
        token: JWT token string
        expected_audience: Expected audience for the token.
                         For ID tokens, use AUTH0_CLIENT_ID.
                         For access tokens, use AUTH0_AUDIENCE or API identifier.
                         Defaults to AUTH0_CLIENT_ID for backward compatibility.

    Returns:
        dict: Decoded token payload with user claims

    Raises:
        AuthError: If token is invalid, expired, or signature verification fails
    """
    # Default to CLIENT_ID for ID token validation if no audience specified
    if expected_audience is None:
        expected_audience = AUTH0_CLIENT_ID

    try:
        # Get the signing key from Auth0's JWKS
        jwks = get_jwks()
        unverified_header = jwt.get_unverified_header(token)

        # Find the key used to sign this token
        rsa_key = {}
        for key in jwks.get("keys", []):
            if key["kid"] == unverified_header["kid"]:
                # Validate key is suitable for JWT verification
                if key.get("kty") != "RSA":
                    continue  # Skip non-RSA keys
                if key.get("use") and key.get("use") != "sig":
                    continue  # Skip keys not intended for signing
                if key.get("alg") and key.get("alg") != "RS256":
                    continue  # Skip keys not using RS256

                rsa_key = {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"],
                }
                break

        if not rsa_key:
            raise AuthError("Unable to find appropriate signing key", 401)

        # Verify the token signature and decode
        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            audience=expected_audience,
            issuer=f"{AUTH0_BASE_URL}/",
        )
        return payload

    except ExpiredSignatureError as exc:
        raise AuthError("Token has expired", 401) from exc
    except JWTClaimsError as exc:
        raise AuthError(f"Invalid token claims: {exc}", 401) from exc
    except JWTError as exc:
        raise AuthError(f"Invalid token: {exc}", 401) from exc
    except Exception as exc:
        raise AuthError(f"Token validation failed: {exc}", 500) from exc


# Role management is now handled locally in the database
# Auth0 is used only for authentication (identity verification)


def sync_auth0_user_to_db(userinfo: dict) -> int:
    """Synchronize Auth0 user to local database.

    Creates a new user or updates existing user in the `users` table.
    Auth0 is used only for authentication - roles are managed locally in the database.

    Args:
        userinfo: User information from Auth0 (ID token claims)

    Returns:
        int: User ID from database

    Raises:
        AuthError: If user sync fails, required claims missing, or user is deactivated
        SQLAlchemyError: If database operation fails
    """
    try:
        auth0_sub = userinfo.get("sub")
        email = userinfo.get("email")

        if not auth0_sub:
            raise AuthError("Missing 'sub' claim in Auth0 userinfo", 400)
        if not email:
            raise AuthError("Missing 'email' claim in Auth0 userinfo", 400)

        display_name = userinfo.get("name") or userinfo.get("nickname") or email

        user_id = get_or_create_user(
            auth0_sub=auth0_sub,
            email=email,
            display_name=display_name,
        )

        # Deactivated users return None from get_or_create_user
        if user_id is None:
            raise AuthError("Your account has been deactivated. Contact an administrator.", 403)

        return user_id

    except AuthError:
        raise
    except Exception as exc:
        raise AuthError(f"Failed to sync user to database: {exc}", 500) from exc


def login() -> Any:
    """Initiate Auth0 login flow.

    Generates a random state parameter for CSRF protection and redirects
    to Auth0's authorization endpoint.

    Returns:
        Redirect response to Auth0 login page
    """
    # Generate CSRF protection state
    state = secrets.token_urlsafe(32)
    session["oauth_state"] = state

    # DEBUG: Log state generation and session
    current_app.logger.info(f"Generated state: {state}")
    current_app.logger.info(f"Session after setting state: {dict(session)}")
    current_app.logger.info(f"Session ID: {getattr(session, 'sid', 'Unknown')}")
    current_app.logger.info(f"Request headers: {dict(request.headers)}")
    current_app.logger.info(f"Cookie being set with secure: {current_app.config.get('SESSION_COOKIE_SECURE', 'Not Set')}")
    current_app.logger.info(f"Flask Debug Mode: {current_app.debug}")

    # Build authorization URL
    params = {
        "client_id": AUTH0_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": AUTH0_CALLBACK_URL,
        "scope": "openid profile email",
        "state": state,
    }

    # Only include audience parameter if it's configured (for custom APIs)
    # Regular Web Applications without custom APIs don't need this parameter
    if AUTH0_AUDIENCE:
        params["audience"] = AUTH0_AUDIENCE

    auth_url = f"{AUTH0_AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"

    current_app.logger.info(f"Redirecting to: {auth_url}")

    return redirect(auth_url)


def callback() -> Any:
    """Handle Auth0 callback after login.

    Validates the OAuth2 callback, exchanges authorization code for tokens,
    verifies the ID token, syncs user to database, and establishes session.

    Returns:
        Redirect response to home page or error page

    Raises:
        AuthError: If callback validation fails
    """
    # DEBUG: Log all request parameters and session state
    current_app.logger.info(f"Callback request args: {dict(request.args)}")
    current_app.logger.info(f"Callback request headers: {dict(request.headers)}")
    current_app.logger.info(f"Callback cookies: {request.cookies}")
    current_app.logger.info(f"Session before validation: {dict(session)}")
    current_app.logger.info(f"Flask session config: secure={current_app.config.get('SESSION_COOKIE_SECURE')}, httponly={current_app.config.get('SESSION_COOKIE_HTTPONLY')}, samesite={current_app.config.get('SESSION_COOKIE_SAMESITE')}")

    # Check for Auth0 error responses FIRST (before state validation)
    # This prevents misleading "Invalid state parameter" when Auth0 returns errors
    auth0_error = request.args.get("error")
    if auth0_error:
        error_description = request.args.get("error_description", "")
        # Clear any oauth_state from session since login failed
        session.pop("oauth_state", None)
        raise AuthError(f"Auth0 authorization failed: {auth0_error} - {error_description}", 400)

    # Validate state parameter (CSRF protection)
    state_from_auth0 = request.args.get("state")
    state_from_session = session.get("oauth_state")

    # DEBUG: Log state comparison
    current_app.logger.info(f"State from Auth0: {state_from_auth0}")
    current_app.logger.info(f"State from session: {state_from_session}")
    current_app.logger.info(f"States match: {state_from_auth0 == state_from_session}")

    if not state_from_auth0 or not state_from_session:
        current_app.logger.error(f"Missing state parameter - Auth0: {bool(state_from_auth0)}, Session: {bool(state_from_session)}")
        raise AuthError("Missing state parameter (CSRF protection)", 400)

    if state_from_auth0 != state_from_session:
        current_app.logger.error(f"State mismatch - Auth0: '{state_from_auth0}' vs Session: '{state_from_session}'")
        raise AuthError("Invalid state parameter (CSRF protection)", 400)

    # Clear state from session
    session.pop("oauth_state", None)

    # Get authorization code
    code = request.args.get("code")
    if not code:
        raise AuthError("No authorization code received from Auth0", 400)

    # Exchange authorization code for tokens
    token_payload = {
        "grant_type": "authorization_code",
        "client_id": AUTH0_CLIENT_ID,
        "client_secret": AUTH0_CLIENT_SECRET,
        "code": code,
        "redirect_uri": AUTH0_CALLBACK_URL,
    }

    try:
        token_response = requests.post(
            AUTH0_TOKEN_URL, json=token_payload, timeout=10
        )
        token_response.raise_for_status()
        tokens = token_response.json()

        # Validate token response structure
        if not isinstance(tokens, dict):
            raise AuthError("Invalid token response format from Auth0", 500)

        # Check for error in response (Auth0 can return 200 with error payload)
        if "error" in tokens:
            error_desc = tokens.get("error_description", tokens.get("error"))
            raise AuthError(f"Auth0 token exchange failed: {error_desc}", 400)

    except requests.RequestException as exc:
        raise AuthError(f"Failed to exchange code for tokens: {exc}", 500) from exc

    # Extract ID token (access_token not needed - Auth0 used only for authentication)
    id_token = tokens.get("id_token")

    if not id_token:
        raise AuthError("No ID token received from Auth0", 500)

    # Verify and decode ID token for Auth0 authentication
    try:
        userinfo = verify_jwt(id_token, expected_audience=AUTH0_CLIENT_ID)
        current_app.logger.info(f"Auth0 authentication successful for: {userinfo.get('email')}")
    except AuthError:
        raise

    # Sync user to database (handles deactivated user check)
    user_id = sync_auth0_user_to_db(userinfo)

    # SECURITY: Clear session before setting authenticated state (prevents session fixation)
    session.clear()

    # Store user info in session
    session["user_id"] = user_id
    session["auth0_sub"] = userinfo["sub"]
    session["email"] = userinfo.get("email")
    session["display_name"] = userinfo.get("name")

    # Set session expiration (fixed 1-hour timeout)
    session["token_expires_at"] = time.time() + 3600

    current_app.logger.info(f"User logged in: {userinfo.get('email')} (ID: {user_id})")

    return redirect(url_for("home"))


def logout() -> Any:
    """Log out the current user.

    Clears the Flask session and redirects to Auth0 logout endpoint,
    which clears the Auth0 session as well.

    Returns:
        Redirect response to Auth0 logout page
    """
    # Clear Flask session
    session.clear()

    # Build Auth0 logout URL
    params = {
        "client_id": AUTH0_CLIENT_ID,
        "returnTo": url_for("home", _external=True),
    }
    logout_url = f"{AUTH0_BASE_URL}/v2/logout?{urllib.parse.urlencode(params)}"

    return redirect(logout_url)


def load_user_into_g() -> None:
    """Load current user into Flask's g object for request context.

    This function should be called before each request (via @app.before_request).
    It loads the user from the database based on the session and makes it
    available via `g.user` throughout the request.

    SECURITY: Checks token expiration, user existence, AND user active status.

    Sets:
        g.user (dict | None): Current user dictionary or None if not authenticated
        g.user_load_error (str | None): Error message if user loading failed
    """
    user_id = session.get("user_id")

    # Initialize both attributes
    g.user = None
    g.user_load_error = None

    if user_id:
        # Check if session has expired (based on token expiration)
        token_expires_at = session.get("token_expires_at")
        if token_expires_at and time.time() > token_expires_at:
            current_app.logger.info(f"Session expired for user {user_id}")
            session.clear()
            return

        try:
            user = get_user_by_id(user_id)
            if user is None:
                # User ID in session but not found in DB - session is stale
                current_app.logger.warning(f"User {user_id} in session but not found in DB")
                session.clear()
                return

            # Check if user is deactivated
            if not user.get("is_active", True):
                current_app.logger.warning(f"User {user_id} is deactivated, clearing session")
                session.clear()
                return

            g.user = user
        except Exception as exc:
            # Database error - don't clear session, set error flag
            current_app.logger.error(f"Failed to load user {user_id}: {exc}")
            g.user_load_error = "Database connectivity issue"


def login_required(f: Callable) -> Callable:
    """Decorator to require authentication for a route.

    Usage:
        @app.route('/protected')
        @login_required
        def protected_route():
            return f"Hello {g.user['email']}"

    Args:
        f: Flask route function

    Returns:
        Decorated function that checks authentication
    """

    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        # Check for database errors first
        if hasattr(g, 'user_load_error') and g.user_load_error:
            if request.is_json or request.accept_mimetypes.accept_json:
                return jsonify({"error": "Service temporarily unavailable"}), 503
            return (
                "<h1>503 Service Unavailable</h1>"
                "<p>Authentication service is temporarily unavailable. Please try again later.</p>"
                "<p><a href='/'>Back to Home</a></p>",
                503
            )

        # Check authentication
        if not session.get("user_id") or not g.user:
            # Return JSON for API routes, redirect for HTML routes
            if request.is_json or request.accept_mimetypes.accept_json:
                return jsonify({"error": "Authentication required"}), 401
            return redirect(url_for("auth_login"))
        return f(*args, **kwargs)

    return decorated_function


def admin_required(f: Callable) -> Callable:
    """Decorator to require admin role for a route.

    Usage:
        @app.route('/admin')
        @admin_required
        def admin_route():
            return "Admin only"

    Args:
        f: Flask route function

    Returns:
        Decorated function that checks admin role
    """

    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        # Check for database errors first
        if hasattr(g, 'user_load_error') and g.user_load_error:
            if request.is_json or request.accept_mimetypes.accept_json:
                return jsonify({"error": "Service temporarily unavailable"}), 503
            return (
                "<h1>503 Service Unavailable</h1>"
                "<p>Authentication service is temporarily unavailable. Please try again later.</p>"
                "<p><a href='/'>Back to Home</a></p>",
                503
            )

        # Check authentication first
        if not session.get("user_id") or not g.user:
            # Return JSON for API routes, redirect for HTML routes
            if request.is_json or request.accept_mimetypes.accept_json:
                return jsonify({"error": "Authentication required"}), 401
            return redirect(url_for("auth_login"))

        # Check admin role
        if g.user.get("role") != "admin":
            if request.is_json or request.accept_mimetypes.accept_json:
                return jsonify({"error": "Admin access required"}), 403
            return (
                "<h1>403 Forbidden</h1><p>You do not have permission to access this resource.</p>",
                403,
            )

        return f(*args, **kwargs)

    return decorated_function


def register_auth_routes(app: Flask) -> None:
    """Register authentication routes with the Flask app.

    This function should be called during app initialization to add
    login, logout, and callback routes.

    Args:
        app: Flask application instance
    """

    @app.route("/auth/login")
    def auth_login():
        """Login route - redirects to Auth0."""
        return login()

    @app.route("/auth/callback")
    def auth_callback():
        """OAuth2 callback route - handles Auth0 redirect after login."""
        try:
            return callback()
        except AuthError as exc:
            app.logger.error(f"Auth callback error: {exc.message}")
            return (
                f"<h1>Authentication Error</h1>"
                f"<p>{exc.message}</p>"
                f"<p><a href='/'>Back to Home</a></p>",
                exc.status_code,
            )

    @app.route("/auth/logout")
    def auth_logout():
        """Logout route - clears session and redirects to Auth0 logout."""
        return logout()

    @app.route("/auth/user")
    @login_required
    def auth_user():
        """Get current user info (for debugging/testing)."""
        return jsonify(g.user)

    # Register before_request handler to load user
    app.before_request(load_user_into_g)

    app.logger.info("Authentication routes registered")
