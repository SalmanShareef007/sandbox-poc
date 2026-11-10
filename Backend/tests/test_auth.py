import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.core import security


def authenticate(monkeypatch, claims):
	monkeypatch.setattr(security.settings, "ENTRA_TENANT_ID", "tenant")
	monkeypatch.setattr(security.settings, "ENTRA_API_AUDIENCE", "api")
	monkeypatch.setattr(security.settings, "ENTRA_ALLOWED_CLIENT_IDS", ["frontend"])
	client = SimpleNamespace(get_signing_key_from_jwt=lambda token: SimpleNamespace(key="key"))
	monkeypatch.setattr(security, "get_jwks_client", lambda tenant: client)
	monkeypatch.setattr(security.jwt, "decode", lambda *args, **kwargs: claims)
	credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="test-token")
	return asyncio.run(security.get_current_user(credentials))


def test_delegated_api_token_is_accepted(monkeypatch):
	claims = {"tid": "tenant", "oid": "user", "scp": "access_as_user", "azp": "frontend"}
	assert authenticate(monkeypatch, claims) == claims


@pytest.mark.parametrize("scopes", [None, "User.Read", ""])
def test_id_tokens_and_wrong_scopes_are_rejected(monkeypatch, scopes):
	with pytest.raises(HTTPException) as error:
		authenticate(monkeypatch, {"tid": "tenant", "oid": "user", "scp": scopes, "azp": "frontend"})
	assert error.value.status_code == 403


def test_unapproved_client_is_rejected(monkeypatch):
	with pytest.raises(HTTPException) as error:
		authenticate(monkeypatch, {"tid": "tenant", "oid": "user", "scp": "access_as_user", "azp": "other"})
	assert error.value.status_code == 403


def test_wrong_tenant_is_rejected(monkeypatch):
	with pytest.raises(HTTPException) as error:
		authenticate(monkeypatch, {"tid": "other", "oid": "user", "scp": "access_as_user", "azp": "frontend"})
	assert error.value.status_code == 401


@pytest.mark.parametrize("invalid_claim", [None, "aud", "iss", "exp"])
def test_signed_token_validation(monkeypatch, invalid_claim):
	import time
	from cryptography.hazmat.primitives.asymmetric import rsa

	private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
	monkeypatch.setattr(security.settings, "ENTRA_TENANT_ID", "tenant")
	monkeypatch.setattr(security.settings, "ENTRA_API_AUDIENCE", "api")
	monkeypatch.setattr(security.settings, "ENTRA_ALLOWED_CLIENT_IDS", ["frontend"])
	client = SimpleNamespace(get_signing_key_from_jwt=lambda token: SimpleNamespace(key=private_key.public_key()))
	monkeypatch.setattr(security, "get_jwks_client", lambda tenant: client)
	claims = {"tid": "tenant", "oid": "user", "azp": "frontend", "scp": "access_as_user", "aud": "api",
			  "iss": "https://login.microsoftonline.com/tenant/v2.0", "exp": int(time.time()) + 600}
	if invalid_claim:
		claims[invalid_claim] = 1 if invalid_claim == "exp" else "unexpected"
	token = security.jwt.encode(claims, private_key, algorithm="RS256")
	credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
	if invalid_claim:
		with pytest.raises(HTTPException) as error:
			asyncio.run(security.get_current_user(credentials))
		assert error.value.status_code == 401
	else:
		assert asyncio.run(security.get_current_user(credentials))["oid"] == "user"
