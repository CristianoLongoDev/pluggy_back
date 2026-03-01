import hashlib
import logging
import secrets
import time
import traceback

import jwt
import requests
from jwt import PyJWKClient

from config import (
    AUTH_ACCEPT_SUPABASE_TOKENS,
    AUTH_JWT_ACCESS_TTL_SECONDS,
    AUTH_JWT_AUDIENCE,
    AUTH_JWT_ISSUER,
    AUTH_JWT_SECRET,
    SUPABASE_JWKS_URL,
    SUPABASE_URL,
)

logger = logging.getLogger(__name__)

# Cache global para as chaves JWKS do Supabase (migração opcional)
_supabase_jwks_client = None


def create_refresh_token() -> str:
    # Token opaco (não é JWT). Armazene apenas o hash no banco.
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_access_token(*, user_id: str, email: str, account_id: str | None, role: str = "user") -> str:
    now = int(time.time())
    payload = {
        "sub": user_id,
        "email": email,
        "account_id": account_id,
        "role": role,
        "iss": AUTH_JWT_ISSUER,
        "aud": AUTH_JWT_AUDIENCE,
        "iat": now,
        "exp": now + AUTH_JWT_ACCESS_TTL_SECONDS,
        "typ": "access",
    }
    return jwt.encode(payload, AUTH_JWT_SECRET, algorithm="HS256")


def validate_local_jwt_token(token: str, *, required_type: str = "access") -> dict | None:
    try:
        payload = jwt.decode(
            token,
            AUTH_JWT_SECRET,
            algorithms=["HS256"],
            audience=AUTH_JWT_AUDIENCE,
            issuer=AUTH_JWT_ISSUER,
        )
        if required_type and payload.get("typ") != required_type:
            return None
        payload["_provider"] = "local"
        return payload
    except Exception:
        return None


def _get_supabase_jwks_client() -> PyJWKClient | None:
    global _supabase_jwks_client
    if _supabase_jwks_client is not None:
        return _supabase_jwks_client

    if not SUPABASE_JWKS_URL:
        return None

    try:
        _supabase_jwks_client = PyJWKClient(SUPABASE_JWKS_URL, cache_keys=True, max_cached_keys=10)
        # sanity check (não obrigatório)
        try:
            requests.get(SUPABASE_JWKS_URL, timeout=5)
        except Exception:
            pass
        return _supabase_jwks_client
    except Exception as e:
        logger.error(f"❌ Erro ao criar cliente JWKS: {e}")
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        return None


def validate_supabase_jwt_token(token: str) -> dict | None:
    """
    Valida token JWT do Supabase via JWKS (apenas para migração).
    """
    try:
        if not (SUPABASE_URL and SUPABASE_JWKS_URL):
            return None

        client = _get_supabase_jwks_client()
        if not client:
            return None

        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        if not kid:
            return None

        signing_key = client.get_signing_key(kid)
        public_key = signing_key.key

        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256", "ES256"],
            audience="authenticated",
            issuer=f"{SUPABASE_URL}/auth/v1",
        )
        payload["_provider"] = "supabase"
        return payload
    except Exception:
        return None


def validate_jwt_token(token: str, *, required_type: str = "access") -> dict | None:
    """
    Valida token JWT.
    - Primeiro tenta tokens locais (HS256).
    - Opcionalmente (migração), tenta Supabase JWKS se habilitado/configurado.
    """
    payload = validate_local_jwt_token(token, required_type=required_type)
    if payload:
        return payload

    if AUTH_ACCEPT_SUPABASE_TOKENS:
        # Tokens do Supabase não têm "typ" no mesmo formato; não exigir.
        payload = validate_supabase_jwt_token(token)
        if payload:
            return payload

    return None

