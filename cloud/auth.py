import httpx
import base64
import json
import time
from fastapi import HTTPException, Request
from sqlalchemy import select, func, text
from uuid import UUID
from .db import accounts, invites

DEV_USER = "00000000-0000-4000-8000-000000000001"


def live_session(db, session_id, owner):
    with db.engine.connect() as c:
        return bool(c.execute(text("SELECT 1 FROM auth.sessions WHERE id = CAST(:session AS uuid) AND user_id = CAST(:owner AS uuid) AND (not_after IS NULL OR not_after > now())"),
                              {"session": session_id, "owner": owner}).first())


async def authenticated_user(request: Request, *, chat=False):
    """Supabase verifies the signature; bind that verified token to this interface.

    Deliberately no development bypass here: an MCP request always needs OAuth.
    """
    settings, db = request.app.state.settings, request.app.state.db
    authorization = request.headers.get("authorization", "")
    if not authorization.startswith("Bearer ") or len(authorization) > 8192:
        raise HTTPException(401, "Please reconnect Lectic. Your saved work is safe.")
    try:
        async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
            response = await client.get(settings.supabase_url + "/auth/v1/user", headers={
                "Authorization": authorization, "apikey": settings.publishable_key})
        if response.status_code >= 500: raise HTTPException(503, "Sign-in is temporarily unavailable. Try again; your saved work is safe.")
        if response.status_code != 200: raise ValueError()
        user = response.json()
        owner, email = str(UUID(user["id"])), user["email"].lower()
        if not user.get("email_confirmed_at") or user.get("is_anonymous"): raise ValueError()
        encoded = authorization.removeprefix("Bearer ").split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        if claims["iss"] != settings.supabase_url + "/auth/v1" or claims["sub"] != owner: raise ValueError()
        if not isinstance(claims["exp"], (int, float)) or claims["exp"] <= time.time(): raise ValueError()
        if chat:
            # The dedicated project's token hook assigns this audience to OAuth tokens.
            # Ordinary browser tokens and ID tokens are not personal chat connections.
            if claims["aud"] != settings.mcp_resource or not claims.get("client_id"): raise ValueError()
            str(UUID(claims["client_id"]))
        elif claims.get("client_id") or claims["aud"] != "authenticated":
            raise ValueError()
        session_id = str(UUID(claims["session_id"]))
        if not live_session(db, session_id, owner): raise ValueError()
        return owner, email
    except httpx.HTTPError:
        raise HTTPException(503, "Sign-in is temporarily unavailable. Try again; your saved work is safe.")
    except (ValueError, TypeError, KeyError, IndexError):
        raise HTTPException(401, "Please reconnect Lectic. Your saved work is safe.")


def enroll(db, settings, owner, email, *, invited=True):
    with db.transaction() as c:
        if invited:
            allowed = c.execute(select(invites).where(invites.c.id == email, invites.c.enabled == 1).with_for_update()).first()
            if not allowed: raise HTTPException(403, "This pilot is invitation only. Ask for an invite using your sign-in email.")
        if not c.execute(select(accounts).where(accounts.c.id == owner)).first():
            if db.engine.dialect.name == "postgresql": c.exec_driver_sql("SELECT pg_advisory_xact_lock(713540)")
            if c.execute(select(func.count()).select_from(accounts)).scalar_one() >= settings.invite_limit:
                raise HTTPException(403, "The pilot is full. Your invitation will work when a space opens.")
            c.execute(accounts.insert().values(id=owner, email=email))
    return owner


async def chat_identity(request: Request):
    settings = request.app.state.settings
    if not settings.chat_enabled: raise HTTPException(503, "Personal chat connections have not been activated on this server.")
    try:
        owner, email = await authenticated_user(request, chat=True)
        return enroll(request.app.state.db, settings, owner, email)
    except HTTPException as exc:
        if exc.status_code == 401:
            exc.headers = {"WWW-Authenticate": 'Bearer resource_metadata="' + settings.origin + '/.well-known/oauth-protected-resource/mcp"'}
        raise


async def identity(request: Request):
    settings, db = request.app.state.settings, request.app.state.db
    if settings.dev:
        # No development header or query parameter is honored in production.
        if request.client.host not in {"127.0.0.1", "::1", "testclient"}:
            raise HTTPException(403, "Development preview is local only.")
        owner, email = DEV_USER, "local-preview@lectic.invalid"
    else:
        owner, email = await authenticated_user(request)
    return enroll(db, settings, owner, email, invited=not settings.dev)
