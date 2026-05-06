"""Minimal mock Alex service for security verification tests.

Run with: python mock_alex.py
Listens on port 8001 by default and implements the delegation verification
contract (RS256, kid required in production, replay protection via Redis).
"""
import os
import glob

# Load .env if available (same behavior as config.py)
try:
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    # project root .env
    project_env = os.path.join(os.path.dirname(__file__), '..', '.env')
    if os.path.exists(project_env):
        load_dotenv(project_env)
    if os.path.exists(env_path):
        load_dotenv(env_path)
except Exception:
    pass
import json
import argparse
from datetime import datetime, timezone

from flask import Flask, request, jsonify
from jose import jwt
from jose import JWTError, ExpiredSignatureError

try:
    import redis
except Exception:
    redis = None

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend


app = Flask(__name__)


def load_private_key_pem():
    # Read ALEX_DELEGATION_PRIVATE_KEY from env (escaped newlines allowed)
    raw = os.getenv("ALEX_DELEGATION_PRIVATE_KEY") or ""
    return raw.replace("\\n", "\n").strip()


def get_public_pem_from_private(raw_pem: str) -> str:
    p = raw_pem.encode("utf-8")
    priv = serialization.load_pem_private_key(p, password=None, backend=default_backend())
    pub = priv.public_key()
    return pub.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")


def init_jwks_mapping():
    kid = os.getenv("ALEX_DELEGATION_ACTIVE_KID") or os.getenv("ALEX_DELEGATION_KEY_ID")
    raw_priv = load_private_key_pem()
    if not raw_priv or not kid:
        return {}
    pub_pem = get_public_pem_from_private(raw_priv)
    return {kid: pub_pem}


JWKS = init_jwks_mapping()
if os.getenv("MOCK_ALEX_SHOW_JWKS", "false").lower() in ("1","true","yes"):
    print(f"[mock_alex] JWKS keys: {list(JWKS.keys())}")
    print("[mock_alex] ALEX_DELEGATION_ACTIVE_KID env:", repr(os.getenv('ALEX_DELEGATION_ACTIVE_KID')))
    # show whether private key is present (don't print raw key content)
    priv = os.getenv('ALEX_DELEGATION_PRIVATE_KEY')
    print("[mock_alex] ALEX_DELEGATION_PRIVATE_KEY present:", bool(priv))


def connect_redis():
    url = os.getenv("REDIS_URL")
    if not url:
        return None
    if redis is None:
        raise RuntimeError("redis package not installed in environment")
    return redis.from_url(url)


@app.route("/guidance/generate", methods=["POST"])
def guidance_generate():
    auth = request.headers.get("Authorization", "")

    # 1) missing token
    if not auth or not auth.lower().startswith("bearer "):
        return jsonify({"message": "Missing Authorization token"}), 401

    token = auth.split(None, 1)[1].strip()

    # parse header to get kid
    try:
        unverified = jwt.get_unverified_header(token)
    except Exception:
        return jsonify({"message": "Malformed token"}), 401

    kid = unverified.get("kid")

    # In production we require explicit kid
    require_kid = os.getenv("MOCK_ALEX_PRODUCTION", "true").lower() in ("1", "true", "yes")
    if require_kid and not kid:
        return jsonify({"message": "Missing kid in production"}), 401

    # unknown kid
    if kid and kid not in JWKS:
        return jsonify({"message": "Unknown kid"}), 401

    pubkey = JWKS.get(kid) if kid else None

    # Verify token signature and claims
    try:
        payload = jwt.decode(
            token,
            pubkey,
            algorithms=["RS256"],
            audience=os.getenv("ALEX_DELEGATION_AUDIENCE", "alex-llm-service"),
            issuer=os.getenv("ALEX_DELEGATION_ISSUER", "capsico-flask-backend"),
        )
    except ExpiredSignatureError:
        return jsonify({"message": "Token expired"}), 401
    except JWTError as exc:
        return jsonify({"message": f"Invalid token: {exc}"}), 401
    except Exception as exc:
        return jsonify({"message": f"Token decode error: {exc}"}), 401

    # future iat beyond skew (allow small skew)
    now = int(datetime.now(timezone.utc).timestamp())
    iat = int(payload.get("iat", 0))
    if iat - now > int(os.getenv("ALLOWED_IAT_SKEW_SECONDS", "5")):
        return jsonify({"message": "iat too far in future"}), 401

    # replay protection using Redis if configured
    jti = payload.get("jti")
    if not jti:
        return jsonify({"message": "Missing jti"}), 401

    r = None
    try:
        r = connect_redis()
    except Exception:
        r = None

    if r:
        try:
            # NX set with TTL
            added = r.set(name=f"replay:{jti}", value=1, ex=int(os.getenv("ALEX_REPLAY_TTL", "300")), nx=True)
            if not added:
                return jsonify({"message": "Token replay"}), 401
        except Exception:
            # Redis failure
            if require_kid:
                # Fail closed in production
                return jsonify({"message": "Redis failure - fail closed"}), 500
    else:
        # No Redis configured; use in-memory simple replay cache (single-instance only)
        if not hasattr(app, "_replay_cache"):
            app._replay_cache = set()
        if jti in app._replay_cache:
            return jsonify({"message": "Token replay"}), 401
        app._replay_cache.add(jti)

    # All good - return mock guidance (business-level response)
    return jsonify({"ok": True, "answer": "mock guidance from Alex", "request_id": payload.get("rid")}), 200


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    app.run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
