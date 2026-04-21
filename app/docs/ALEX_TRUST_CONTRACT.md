# Flask <-> Alex Delegated JWT Trust Contract

This document is the source of truth for service-to-service trust between the Flask app and Alex inference service.

## Scope
- Producer: Flask backend (`capsico-flask-backend`)
- Verifier: Alex inference service (`alex-llm-service`)
- Identity source: Auth0 (`sub` claim)

## Token Type
- JWT
- Signing algorithm: `RS256`
- Signed by Flask private key
- Verified by Alex public key

## Required Claims
- `iss`: must equal `capsico-flask-backend`
- `aud`: must equal `alex-llm-service`
- `sub`: must be Auth0 subject and start with `auth0|`
- `exp`: unix timestamp, strict expiry
- `iat`: unix timestamp
- `jti`: unique token ID (single use)

## Optional Claim
- `rid`: request correlation id

## Alex Verification Rules (Every Request)
1. Require `Authorization: Bearer <token>`.
2. Decode and verify signature with configured public key and `RS256` only.
3. Verify `iss` and `aud` exact match.
4. Require all mandatory claims.
5. Verify time claims:
   - `exp` must be in future (allow configured skew only).
   - `iat` must not be in the future beyond skew.
6. Enforce `sub` format (`auth0|...`).
7. Enforce replay protection:
   - reject previously seen `jti` within replay TTL window.
   - current replay cache is in-memory and valid for single-instance deployment only.
8. Reject request with `401` on any validation failure.

## Security Boundaries
- Auth0 authenticates end-user identity.
- Flask delegates trusted identity to Alex.
- Alex verifies only signed delegation token; does not trust body identity fields.

## Operational Defaults
- Token lifetime: `120` seconds
- Clock skew: `30` seconds
- Replay cache TTL: `300` seconds

## Rotation Contract
- Flask may set `kid` in JWT header.
- Alex must rotate verifier key with overlap to avoid downtime.