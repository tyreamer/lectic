import hashlib
import json
import os
from pathlib import Path
import time
from typing import Literal
from uuid import UUID
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Request, HTTPException, Header
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select, update
from .config import Settings, ROOT
from .db import Database, accounts, captures, packs, results, jobs, shares, backups, events, Conflict, uid, hash_json
from .auth import identity
from .storage import asset_path
from .suggestions import GUIDANCE_VERSION


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Capture(Input):
    title: str = Field(default="Untitled source", min_length=1, max_length=160)
    kind: Literal["note", "url", "upload"]
    text: str = Field(default="", max_length=200000)
    url: str = Field(default="", max_length=2048)
    filename: str = Field(default="", max_length=200)
    size: int = Field(default=0, ge=0)
    parent_id: UUID | None = None


class Assembly(Input):
    title: str = Field(min_length=1, max_length=120)
    source_ids: list[UUID] = Field(min_length=1, max_length=20)


class Creation(Input):
    pack_id: UUID
    format: Literal["Plan", "Checklist", "Lesson", "Review", "Proposal", "Your Idea", "Agent skill", "Prompt", "MCP server"]
    brief: str = Field(min_length=5, max_length=12000)


class SuggestionContext(Input):
    context: str = Field(default="", max_length=1000)


class Telemetry(Input):
    name: Literal["first_visit", "result_useful", "result_copied", "return_visit", "capture_fallback"]
    result_id: UUID | None = None


def starters():
    return json.loads((ROOT / "fixtures/pilot/catalog.json").read_text(encoding="utf-8"))


def create_app(settings=None, auth=None):
    settings = settings or Settings()
    settings.validate()
    db = Database(settings)
    @asynccontextmanager
    async def lifespan(app):
        if settings.dev: db.initialize()
        yield
        db.engine.dispose()
    app = FastAPI(title="Lectic pilot", version="1", lifespan=lifespan)
    app.state.settings, app.state.db = settings, db
    if auth: app.dependency_overrides[identity] = auth

    @app.middleware("http")
    async def headers(request, call_next):
        if settings.dev and request.headers.get("host", "").split(":")[0] not in {"127.0.0.1", "localhost", "testserver"}:
            return JSONResponse({"detail": "Local preview only"}, 403)
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            if origin and not settings.allows_origin(origin): return JSONResponse({"detail": "Origin not allowed"}, 403)
            if not request.url.path.endswith("/content"):
                chunks, size = [], 0
                async for chunk in request.stream():
                    size += len(chunk)
                    if size > 2*1024**2: return JSONResponse({"detail": "Request is too large."}, 413)
                    chunks.append(chunk)
                request._body = b"".join(chunks)
        response = await call_next(request)
        response.headers.update({"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
                                 "Referrer-Policy": "no-referrer", "X-Frame-Options": "DENY"})
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self' " + settings.supabase_url + "; frame-ancestors 'none'; base-uri 'self'; object-src 'none'"
        return response

    @app.exception_handler(Conflict)
    async def conflict(_, exc): return JSONResponse({"detail": str(exc)}, 409)

    def owned(tab, ident, owner):
        row = db.get(tab, str(ident), owner)
        if not row: raise HTTPException(404, "Not found")
        return row

    def key(value):
        if not value or len(value) > 128: raise HTTPException(400, "A retry key is required.")
        return hashlib.sha256(value.encode()).hexdigest()

    def enqueue(owner, kind, payload, retry_key, priority=5):
        return {"operation_id": db.enqueue(owner, kind, payload, key(retry_key), priority)["id"]}

    @app.get("/healthz")
    def health():
        with db.engine.connect() as c: c.execute(select(1))
        return {"ok": True}

    @app.get("/api/v1/config")
    def config():
        return {"supabaseUrl": settings.supabase_url, "publishableKey": settings.publishable_key,
                "dev": settings.dev, "maxUpload": settings.max_upload, "maxSources": settings.max_sources}

    @app.get("/api/v1/starters")
    def catalog(): return starters()

    @app.get("/api/v1/library")
    def library(owner=Depends(identity)):
        def items(tab):
            return [{"id": r["id"], "title": r["title"], "created": r["created"],
                     **({"state": r["state"], "kind": r["data"]["kind"], "reason": r["data"].get("reason"),
                         "needs_upload": r["data"]["kind"] == "upload" and not r["data"].get("sha256")} if tab is captures else
                        {"source_count": r["data"].get("source_count"), "format": r["data"].get("format"),
                         "starter": r["data"].get("starter")})} for r in db.listing(tab, owner)]
        return {"sources": items(captures), "packs": items(packs), "results": items(results),
                "operations": [{k: r.get(k) for k in ("id", "kind", "status", "result", "error", "created")} for r in db.listing(jobs, owner)[:30]]}

    @app.post("/api/v1/starters/{slug}/install", status_code=202)
    def install(slug: str, owner=Depends(identity), idempotency_key: str = Header(default="")):
        if slug not in {s["slug"] for s in starters()}: raise HTTPException(404, "Pack not found")
        return enqueue(owner, "install_starter", {"slug": slug}, idempotency_key, 0)

    @app.post("/api/v1/captures", status_code=202)
    def capture(body: Capture, owner=Depends(identity), idempotency_key: str = Header(default="")):
        payload = body.model_dump(mode="json")
        if body.parent_id: owned(captures, body.parent_id, owner)
        if body.kind == "note" and not body.text.strip(): raise HTTPException(422, "Add a note first.")
        if body.kind == "url":
            from .retrieval import validate_url
            try: validate_url(body.url, resolve=False)
            except ValueError as e: raise HTTPException(422, str(e))
        if body.size > settings.max_upload: raise HTTPException(413, "This file is larger than the upload limit.")
        retry_key = key(idempotency_key)
        with db.transaction() as c:
            account = c.execute(select(accounts).where(accounts.c.id == owner).with_for_update()).mappings().one()
            old = c.execute(select(jobs).where(jobs.c.owner == owner, jobs.c.key == retry_key)).mappings().first()
            if old:
                if old["payload"].get("request") != payload: raise Conflict("Retry key already used.")
                return {"capture_id": old["payload"]["capture_id"], "operation_id": old["id"]}
            size = body.size if body.kind == "upload" else len(body.text.encode())
            if account["used_bytes"] + size > settings.max_storage: raise HTTPException(413, "Your originals storage is full.")
            c.execute(update(accounts).where(accounts.c.id == owner).values(used_bytes=accounts.c.used_bytes+size))
            ident = uid()
            c.execute(captures.insert().values(id=ident, owner=owner, title=body.title, state="saved", data=payload, bytes=size))
            job = db.enqueue(owner, "capture", {"capture_id": ident, "request": payload}, retry_key, connection=c)
            if body.kind == "upload": c.execute(update(jobs).where(jobs.c.id == job["id"]).values(status="awaiting_upload"))
        return {"capture_id": ident, "operation_id": job["id"]}

    @app.put("/api/v1/captures/{ident}/content", status_code=202)
    async def upload(ident: UUID, request: Request, owner=Depends(identity)):
        row = owned(captures, ident, owner)
        if row["data"]["kind"] != "upload": raise HTTPException(409, "This source does not accept a file.")
        path = asset_path(settings, owner, str(ident))
        temporary = path.with_name(path.name + "." + uid() + ".part")
        count, digest = 0, hashlib.sha256()
        try:
            with temporary.open("xb") as stream:
                async for chunk in request.stream():
                    count += len(chunk)
                    if count > min(row["bytes"], settings.max_upload): raise HTTPException(413, "Upload exceeds its reserved size.")
                    stream.write(chunk); digest.update(chunk)
                stream.flush(); os.fsync(stream.fileno())
            if count != row["bytes"] or not count: raise HTTPException(400, "Upload interrupted. Retry the same file.")
            with db.transaction() as c:
                current = c.execute(select(captures).where(captures.c.id == str(ident), captures.c.owner == owner).with_for_update()).mappings().one()
                if current["data"].get("sha256") and current["data"]["sha256"] != digest.hexdigest():
                    raise HTTPException(409, "A different file was already saved for this upload.")
                # Move complete bytes into place before releasing the durable job.
                os.replace(temporary, path)
                data = {**current["data"], "sha256": digest.hexdigest()}
                c.execute(update(captures).where(captures.c.id == str(ident)).values(data=data))
                active = c.execute(select(jobs).where(jobs.c.owner == owner, jobs.c.kind == "capture")).mappings().all()
                job = next(j for j in active if j["payload"]["capture_id"] == str(ident))
                if job["status"] == "awaiting_upload": c.execute(update(jobs).where(jobs.c.id == job["id"]).values(status="saved"))
            return {"operation_id": job["id"]}
        finally:
            temporary.unlink(missing_ok=True)

    @app.get("/api/v1/captures/{ident}")
    def source(ident: UUID, owner=Depends(identity)):
        r = owned(captures, ident, owner)
        return {"id": r["id"], "title": r["title"], "state": r["state"], "data": r["data"]}

    @app.get("/api/v1/captures/{ident}/original")
    def original(ident: UUID, owner=Depends(identity)):
        r = owned(captures, ident, owner)
        path = asset_path(settings, owner, str(ident))
        if not path.exists(): raise HTTPException(404, "Original unavailable")
        return FileResponse(path, filename="original" + Path(r["data"].get("filename", "")).suffix[:10], media_type="application/octet-stream")

    @app.post("/api/v1/packs", status_code=202)
    def assemble(body: Assembly, owner=Depends(identity), idempotency_key: str = Header(default="")):
        ids = list(dict.fromkeys(str(i) for i in body.source_ids))
        if len(ids) > settings.max_sources: raise HTTPException(422, "Too many sources")
        if any(owned(captures, i, owner)["state"] != "ready" for i in ids): raise HTTPException(409, "Choose sources that are Ready.")
        return enqueue(owner, "assemble", {"title": body.title, "source_ids": ids}, idempotency_key, 2)

    @app.get("/api/v1/packs/{ident}")
    def pack(ident: UUID, context: str | None = None, owner=Depends(identity)):
        r = owned(packs, ident, owner)
        suggestions = r["data"].get("suggestions") if context is None else r["data"].get("suggestion_sets", {}).get(hash_json(context))
        if suggestions and suggestions.get("guidance_version") != GUIDANCE_VERSION: suggestions = None
        return {"id": r["id"], "title": r["title"], "preview": r["data"]["preview"], "source_count": r["data"]["source_count"],
                "suggestions": suggestions, "starter": r["data"].get("starter")}

    @app.post("/api/v1/packs/{ident}/suggestions", status_code=202)
    def suggest(ident: UUID, body: SuggestionContext | None = None, owner=Depends(identity)):
        r = owned(packs, ident, owner)
        context = body.context.strip() if body else ""
        return enqueue(owner, "suggest", {"pack_id": str(ident), "context": context},
                       "suggest-"+str(GUIDANCE_VERSION)+"-"+str(ident)+hash_json([r["data"]["ir_hash"], context]), 0)

    @app.get("/api/v1/packs/{ident}/context")
    def portable_context(ident: UUID, owner=Depends(identity)):
        from .bundles import context_from_pack, context_text
        p = owned(packs, ident, owner)
        raw = asset_path(settings, owner, p["id"], "lectic").read_bytes()
        return Response(context_text(context_from_pack(raw,p["title"])), media_type="text/plain",
                        headers={"Content-Disposition": 'attachment; filename="lectic-context.txt"'})

    @app.get("/api/v1/packs/{ident}/download")
    def download(ident: UUID, owner=Depends(identity)):
        owned(packs, ident, owner)
        return FileResponse(asset_path(settings, owner, str(ident), "lectic"), filename="knowledge.lectic", media_type="application/zip")

    @app.post("/api/v1/packs/import/{capture_id}", status_code=202)
    def import_pack(capture_id: UUID, owner=Depends(identity), idempotency_key: str = Header(default="")):
        r = owned(captures, capture_id, owner)
        if not r["data"].get("sha256"): raise HTTPException(409, "Upload the pack first.")
        return enqueue(owner, "import", {"capture_id": str(capture_id)}, idempotency_key, 1)

    @app.post("/api/v1/creations", status_code=202)
    def create(body: Creation, owner=Depends(identity), idempotency_key: str = Header(default="")):
        owned(packs, body.pack_id, owner)
        return enqueue(owner, "create", body.model_dump(mode="json"), idempotency_key, 0)

    @app.get("/api/v1/results/{ident}")
    def result(ident: UUID, owner=Depends(identity)):
        r = owned(results, ident, owner)
        return {"id": r["id"], "title": r["title"], **r["data"]}

    @app.get("/api/v1/results/{ident}/download")
    def result_download(ident: UUID, owner=Depends(identity)):
        r = owned(results, ident, owner)
        return Response(r["data"]["markdown"], media_type="text/markdown", headers={"Content-Disposition": 'attachment; filename="lectic-result.md"'})

    @app.get("/api/v1/results/{ident}/bundle")
    def result_bundle(ident: UUID, owner=Depends(identity)):
        from .bundles import context_from_pack, bundle
        r = owned(results, ident, owner)
        if r["data"].get("format") not in {"Agent skill", "Prompt", "MCP server"}: raise HTTPException(404, "No bundle for this result")
        p = owned(packs, r["data"]["pack_id"], owner)
        raw = asset_path(settings, owner, p["id"], "lectic").read_bytes()
        data = bundle(r["data"], context_from_pack(raw,p["title"]), raw)
        return Response(data, media_type="application/zip", headers={"Content-Disposition": 'attachment; filename="lectic-output.zip"'})

    @app.get("/api/v1/jobs/{ident}")
    def job(ident: UUID, owner=Depends(identity)):
        r = owned(jobs, ident, owner)
        return {k: r.get(k) for k in ("id", "status", "result", "error", "attempts", "kind")}

    @app.post("/api/v1/jobs/{ident}/cancel", status_code=202)
    def cancel(ident: UUID, owner=Depends(identity)):
        r = owned(jobs, ident, owner)
        if r["status"] in {"complete", "failed", "cancelled"}: return {"operation_id": str(ident)}
        db.mutate(jobs, str(ident), owner, cancelled=1, status="cancelled" if r["status"] != "processing" else "processing")
        return {"operation_id": str(ident)}

    @app.post("/api/v1/jobs/{ident}/retry", status_code=202)
    def retry(ident: UUID, owner=Depends(identity)):
        r = owned(jobs, ident, owner)
        if r["status"] not in {"failed", "cancelled"}: return {"operation_id": str(ident)}
        if r["attempts"] >= 3: raise HTTPException(409, "This operation reached its retry limit. Contact the pilot operator.")
        db.mutate(jobs, str(ident), owner, cancelled=0, status="saved", available=0, error=None)
        return {"operation_id": str(ident)}

    @app.post("/api/v1/packs/{ident}/shares", status_code=202)
    def share(ident: UUID, owner=Depends(identity), idempotency_key: str = Header(default="")):
        owned(packs, ident, owner)
        return enqueue(owner, "share", {"pack_id": str(ident)}, idempotency_key, 1)

    @app.get("/api/v1/shares")
    def my_shares(owner=Depends(identity)):
        return [{"id": r["id"], "title": r["data"]["title"], "revoked": bool(r["revoked"])} for r in db.listing(shares, owner)]

    @app.post("/api/v1/shares/{ident}/revoke", status_code=202)
    def revoke(ident: UUID, owner=Depends(identity), idempotency_key: str = Header(default="")):
        owned(shares, ident, owner)
        # Revoke access immediately; the operation records the durable action.
        db.mutate(shares, str(ident), owner, revoked=1)
        return enqueue(owner, "revoke", {"share_id": str(ident)}, idempotency_key, 0)

    def public_share(token):
        if len(token) != 43: raise HTTPException(404, "This share is unavailable.")
        with db.engine.connect() as c:
            r = c.execute(select(shares).where(shares.c.token_hash == hashlib.sha256(token.encode()).hexdigest(), shares.c.revoked == 0)).mappings().first()
        if not r: raise HTTPException(404, "This share is unavailable.")
        return r

    @app.get("/api/v1/shared/{token}")
    def preview(token: str):
        r = public_share(token)
        return {"title": r["data"]["title"], "preview": r["data"]["preview"], "source_count": r["data"]["source_count"]}

    @app.post("/api/v1/shared/{token}/copy", status_code=202)
    def copy(token: str, owner=Depends(identity), idempotency_key: str = Header(default="")):
        r = public_share(token)
        return enqueue(owner, "copy_share", {"share_id": r["id"]}, idempotency_key, 1)

    @app.post("/api/v1/backups", status_code=202)
    def backup(owner=Depends(identity), idempotency_key: str = Header(default="")):
        return enqueue(owner, "backup", {}, idempotency_key, 8)

    @app.get("/api/v1/backups")
    def backup_list(owner=Depends(identity)):
        return [{"id": r["id"], "created": r["created"], "sha256": r["data"]["sha256"]} for r in db.listing(backups, owner)]

    @app.get("/api/v1/backups/{ident}/download")
    def backup_download(ident: UUID, owner=Depends(identity)):
        owned(backups, ident, owner)
        return FileResponse(asset_path(settings, owner, str(ident), "zip"), filename="knowledge.lectic-home", media_type="application/zip")

    @app.post("/api/v1/backups/{ident}/restore", status_code=202)
    def backup_restore(ident: UUID, owner=Depends(identity), idempotency_key: str = Header(default="")):
        owned(backups, ident, owner)
        return enqueue(owner, "restore", {"backup_id": str(ident)}, idempotency_key, 1)

    @app.post("/api/v1/events", status_code=202)
    def event(body: Telemetry, owner=Depends(identity)):
        if body.result_id: owned(results, body.result_id, owner)
        with db.transaction() as c:
            ident = uid()
            c.execute(events.insert().values(id=ident, owner=owner, name=body.name, data={"result_id": str(body.result_id) if body.result_id else None}))
        return {"operation_id": ident}

    dist = ROOT / "apps/web/dist"
    if dist.is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="web-assets")
        @app.get("/{path:path}")
        def frontend(path: str):
            if path.startswith("api/"): raise HTTPException(404)
            return FileResponse(dist / "index.html")
    return app
