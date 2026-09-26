import httpx
import base64
import json
from fastapi import HTTPException, Request
from sqlalchemy import select, func, text
from uuid import UUID
from .db import accounts, invites

DEV_USER = "00000000-0000-4000-8000-000000000001"


async def identity(request: Request):
    settings, db = request.app.state.settings, request.app.state.db
    if settings.dev:
        # No development header or query parameter is honored in production.
        if request.client.host not in {"127.0.0.1", "::1", "testclient"}:
            raise HTTPException(403, "Development preview is local only.")
        owner, email = DEV_USER, "local-preview@lectic.invalid"
    else:
        authorization = request.headers.get("authorization", "")
        if not authorization.startswith("Bearer ") or len(authorization) > 8192:
            raise HTTPException(401, "Please sign in again. Your saved work is safe.")
        # Auth server validates the bearer token and current user, rather than trusting client claims.
        try:
            async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
                response = await client.get(settings.supabase_url + "/auth/v1/user", headers={
                    "Authorization": authorization, "apikey": settings.publishable_key})
            if response.status_code != 200: raise ValueError()
            user = response.json()
            owner, email = str(UUID(user["id"])), user["email"].lower()
            if not user.get("email_confirmed_at") or user.get("is_anonymous"): raise ValueError()
            # getUser validates the signature; additionally reject a revoked session immediately.
            encoded = authorization.removeprefix("Bearer ").split(".")[1]
            claims = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
            session_id = str(UUID(claims["session_id"]))
            with db.engine.connect() as c:
                alive = c.execute(text("SELECT 1 FROM auth.sessions WHERE id = CAST(:session AS uuid) AND user_id = CAST(:owner AS uuid) AND (not_after IS NULL OR not_after > now())"),
                                  {"session": session_id, "owner": owner}).first()
            if not alive: raise ValueError()
        except (ValueError, KeyError, IndexError, httpx.HTTPError):
            raise HTTPException(401, "Please sign in again. Your saved work is safe.")
    with db.transaction() as c:
        # Lock the invitation row to make enrollment and the ten-seat cap deterministic.
        if not settings.dev:
            allowed = c.execute(select(invites).where(invites.c.id == email, invites.c.enabled == 1).with_for_update()).first()
            if not allowed: raise HTTPException(403, "This pilot is invitation only. Ask for an invite using your sign-in email.")
        if not c.execute(select(accounts).where(accounts.c.id == owner)).first():
            # Advisory transaction lock serializes enrollment across different invites.
            if db.engine.dialect.name == "postgresql": c.exec_driver_sql("SELECT pg_advisory_xact_lock(713540)")
            if c.execute(select(func.count()).select_from(accounts)).scalar_one() >= settings.invite_limit:
                raise HTTPException(403, "The pilot is full. Your invitation will work when a space opens.")
            c.execute(accounts.insert().values(id=owner, email=email))
    return owner
