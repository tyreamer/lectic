"""One durable operation in a fresh process with a fixed, validated account home."""
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import sys
import time
from sqlalchemy import select
from .config import Settings, ROOT, VERSION
from .db import Database, jobs, captures, packs, results, shares, backups, uid, hash_json, accounts
from .storage import asset_path, upload_private, remove_private_backup


def execute(settings, db, job):
    owner, ident, payload, kind = job["owner"], job["id"], job["payload"], job["kind"]
    expected = settings.home(owner).resolve()
    if Path(os.environ.get("LECTIC_HOME", "")).resolve() != expected:
        raise RuntimeError("Compiler process has the wrong account home.")
    expected.mkdir(parents=True, exist_ok=True)
    project = settings.account_dir(owner) / "operations" / ident
    project.mkdir(parents=True, exist_ok=True)
    receipt = project / "committed.json"
    if receipt.exists(): return json.loads(receipt.read_text())
    from . import compiler
    from .models import Model
    from .retrieval import retrieve, NeedsContent
    from .media import process
    from ec import read, write
    model = None
    def ai():
        nonlocal model
        if model is None: model = Model(settings, db, owner, ident)
        return model
    def insert(tab, record):
        with db.transaction() as c:
            if not c.execute(select(tab).where(tab.c.id == record["id"])).first(): c.execute(tab.insert().values(**record))
    def own(tab, key):
        row = db.get(tab, key, owner)
        if not row: raise ValueError("Record is unavailable.")
        return row
    def install(raw, title, pack_id=ident):
        # Cloud imports are self-contained: never let a pack trigger arbitrary URL retrieval.
        from packs import open_pack
        manifest, members = open_pack(raw)
        if not manifest["sources_included"]: raise ValueError("This pack needs its source text included before cloud import.")
        location = asset_path(settings, owner, pack_id, "lectic")
        location.write_bytes(raw)
        checkpoint = project / "installed.json"
        if checkpoint.exists(): report = read(checkpoint)
        else:
            report = compiler.install_pack(project, str(location), name=title+" · "+pack_id[:6], retriever=lambda *_: None)
            write(checkpoint, report)
        if report["verification"] != "verified": raise ValueError("Pack verification was partial; no complete pack was added.")
        data = compiler.pack_snapshot(project, report["collection_id"], location)
        insert(packs, dict(id=pack_id, owner=owner, title=title, data=data))
        return {"pack_id": pack_id}
    if kind == "install_starter":
        catalog = read(ROOT / "fixtures/pilot/catalog.json")
        starter = next(s for s in catalog if s["slug"] == payload["slug"])
        # Deduplicate installing the same starter even with a different operation key.
        for row in db.listing(packs, owner):
            if row["data"].get("starter") == starter["slug"]: return {"pack_id": row["id"]}
        outcome = install((ROOT / "fixtures/pilot" / starter["file"]).read_bytes(), starter["title"])
        row = own(packs, ident); db.mutate(packs, ident, owner, data={**row["data"], "starter": starter["slug"]})
    elif kind == "capture":
        capture_id = payload["capture_id"]
        row = own(captures, capture_id)
        if row["state"] == "ready": return {"capture_id": capture_id}
        data = row["data"]
        db.mutate(captures, capture_id, owner, state="processing")
        try:
            processed_path = project / "processed.json"
            if processed_path.exists(): processed = read(processed_path)
            else:
                if data.get("acquired"):
                    items = [{"raw": asset_path(settings, owner, capture_id).read_bytes(), "filename": data["acquired"]["filename"]}]
                elif data["kind"] == "note": items = [{"raw": data["text"].encode(), "filename": "note.txt"}]
                elif data["kind"] == "url": items = retrieve(data["url"], settings)
                else: items = [{"raw": asset_path(settings, owner, capture_id).read_bytes(), "filename": data["filename"]}]
                if data["kind"] == "url" and not data.get("acquired"):
                    size = sum(len(x["raw"]) for x in items)
                    if len(items) != 1: raise NeedsContent("A complete source could not be retrieved. Add all its files.")
                    # Persist fetched bytes and the accounting checkpoint before any paid work.
                    asset_path(settings, owner, capture_id).write_bytes(items[0]["raw"])
                    data = {**data, "acquired": {"filename": items[0]["filename"], "sha256": hashlib.sha256(items[0]["raw"]).hexdigest()}}
                    from sqlalchemy import update
                    with db.transaction() as c:
                        allowed = c.execute(update(accounts).where(accounts.c.id == owner, accounts.c.used_bytes+size <= settings.max_storage)
                                            .values(used_bytes=accounts.c.used_bytes+size)).rowcount
                        if not allowed: raise NeedsContent("Your originals storage is full. The link was saved.")
                        c.execute(update(captures).where(captures.c.id == capture_id).values(bytes=size, data=data))
                processed = {"documents": [], "derivations": [], "limitations": []}
                for i, item in enumerate(items):
                    original = asset_path(settings, owner, capture_id) if i == 0 else project / ("original-"+str(i))
                    original.write_bytes(item["raw"])
                    upload_private(settings, owner, original)
                    part = process(item["raw"], item["filename"], ai(), settings, project / ("media-"+str(i)))
                    for doc in part["documents"]:
                        doc["metadata"]["url"] = data.get("url") or None
                    for field in processed: processed[field].extend(part[field])
                write(processed_path, processed)
                # Large ffmpeg scratch files are disposable after the processing checkpoint.
                for scratch in project.glob("media-*"):
                    if scratch.is_dir() and scratch.resolve().parent == project.resolve(): shutil.rmtree(scratch)
            db.mutate(captures, capture_id, owner, state="ready", data={**data, **processed, "version": VERSION})
        except NeedsContent as exc:
            db.mutate(captures, capture_id, owner, state="needs_content", data={**data, "reason": str(exc)})
        outcome = {"capture_id": capture_id}
    elif kind == "assemble":
        if db.get(packs, ident, owner): return {"pack_id": ident}
        source_dir = project / "sources"; source_dir.mkdir(exist_ok=True)
        metadata, derivations = {}, []
        for capture_id in payload["source_ids"]:
            row = own(captures, capture_id)
            if row["state"] != "ready": raise ValueError("A selected source is not ready.")
            for document in row["data"]["documents"]:
                # Names come from our processor; duplicate content deduplicates within a pack.
                name = document["filename"]
                (source_dir/name).write_text(document["text"], encoding="utf-8")
                metadata[name] = document["metadata"]
            derivations.extend(row["data"]["derivations"])
        metadata_path = project / "metadata.json"; write(metadata_path, metadata)
        checkpoint = project / "collection.json"
        if checkpoint.exists(): collection_id = read(checkpoint)["id"]
        else:
            library = compiler.Library(project)
            folder, collection = library.archive(str(source_dir), name=payload["title"]+" · "+ident[:6], metadata=metadata_path)
            collection_id = collection["collection_id"]; write(checkpoint, {"id": collection_id})
        library = compiler.Library(project); folder, collection = library.resolve(collection_id)
        run = library.run(folder, collection)
        if not (run/"ir.json").exists():
            compiler.extract(run, ai())
            prepared = compiler.work(project=project, collection=collection_id, action="prepare", reconciled=True)
            if prepared["phase"] != "knowledge_saved": raise ValueError("The sources contain no supported reusable knowledge.")
        write(run/"derivations.json", {"schema_version": "1.0", "records": list({r["filename"]: r for r in derivations}.values())})
        data = compiler.pack_snapshot(project, collection_id, asset_path(settings, owner, ident, "lectic"))
        data["capture_ids"] = payload["source_ids"]
        insert(packs, dict(id=ident, owner=owner, title=payload["title"], data=data))
        outcome = {"pack_id": ident}
    elif kind == "suggest":
        pack = own(packs, payload["pack_id"])
        context = payload.get("context", "")
        saved = pack["data"].get("suggestion_sets", {})
        cache_key = hash_json(context)
        from .suggestions import discover, GUIDANCE_VERSION
        if saved.get(cache_key, {}).get("guidance_version") != GUIDANCE_VERSION:
            library = compiler.Library(project)
            folder, collection = library.resolve(pack["data"]["collection_id"])
            ir = compiler.validate_ir(library.run(folder, collection))
            suggestions = discover(pack["title"], ir, ai(), context)
            db.mutate(packs, pack["id"], owner, data={**pack["data"], "suggestions": suggestions,
                      "suggestion_sets": {**saved, cache_key: suggestions}})
        outcome = {"suggestions_for": pack["id"]}
    elif kind == "create":
        if db.get(results, ident, owner): return {"result_id": ident}
        pack = own(packs, payload["pack_id"])
        complete = compiler.create(project, pack["data"]["collection_id"], payload["format"], payload["brief"], ai(),
                                   limitations=pack["data"].get("media_limitations", []))
        data = compiler.result_payload(complete, payload["format"])
        data.update(pack_id=pack["id"], model=ai().last_model)
        insert(results, dict(id=ident, owner=owner, title=payload["format"]+" · "+pack["title"], data=data))
        outcome = {"result_id": ident}
    elif kind == "share":
        pack = own(packs, payload["pack_id"])
        checkpoint = project / "share.json"
        if checkpoint.exists(): shared = read(checkpoint)
        else:
            shared = {"token": secrets.token_urlsafe(32)}; write(checkpoint, shared)
        target = asset_path(settings, owner, ident, "lectic")
        shutil.copyfile(asset_path(settings, owner, pack["id"], "lectic"), target)
        insert(shares, dict(id=ident, owner=owner, token_hash=hashlib.sha256(shared["token"].encode()).hexdigest(),
            data={"title": pack["title"], "preview": pack["data"]["preview"], "source_count": pack["data"]["source_count"],
                  "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}))
        outcome = {"share_id": ident, "url": settings.origin+"/s/"+shared["token"]}
    elif kind == "copy_share":
        shared = db.get(shares, payload["share_id"])
        if not shared or shared["revoked"]: raise ValueError("This share was revoked.")
        raw = asset_path(settings, shared["owner"], shared["id"], "lectic").read_bytes()
        if hashlib.sha256(raw).hexdigest() != shared["data"]["sha256"]: raise ValueError("Shared pack integrity check failed.")
        outcome = install(raw, shared["data"]["title"])
    elif kind == "import":
        row = own(captures, payload["capture_id"])
        outcome = install(asset_path(settings, owner, row["id"]).read_bytes(), row["title"])
    elif kind == "revoke": outcome = {"share_id": payload["share_id"], "revoked": True}
    elif kind == "backup":
        from home_archive import archive_home
        destination = asset_path(settings, owner, ident, "zip")
        destination.write_bytes(archive_home(expected))
        key = upload_private(settings, owner, destination, "backups")
        outcome = {"backup_id": ident, "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(), "stored": key is not None or settings.dev}
        insert(backups, dict(id=ident, owner=owner, data={**outcome, "object_key": key}))
        # Keep seven committed versions; only backup artifacts are eligible for pruning.
        from sqlalchemy import delete
        versions = db.listing(backups, owner)
        retained_keys = {r["data"].get("object_key") for r in versions[:7]}
        removed_keys = set()
        for old in versions[7:]:
            key = old["data"].get("object_key")
            if key and key not in retained_keys and key not in removed_keys:
                remove_private_backup(settings, owner, key); removed_keys.add(key)
            asset_path(settings, owner, old["id"], "zip").unlink(missing_ok=True)
            with db.transaction() as c: c.execute(delete(backups).where(backups.c.id == old["id"], backups.c.owner == owner))
    elif kind == "restore":
        from home_archive import restore
        backup = own(backups, payload["backup_id"])
        archive = asset_path(settings, owner, backup["id"], "zip")
        if hashlib.sha256(archive.read_bytes()).hexdigest() != backup["data"]["sha256"]: raise ValueError("Backup integrity check failed.")
        restored = restore(project, str(archive))
        outcome = {"backup_id": backup["id"], "restored": True, "report": restored}
    else: raise ValueError("Unknown operation")
    # Checkpoint before returning so a worker restart cannot repeat completed processing.
    write(receipt, outcome)
    if kind in {"assemble", "create", "install_starter", "copy_share", "import"}:
        db.enqueue(owner, "backup", {}, "backup-"+ident, priority=9)
    return outcome


def main():
    settings = Settings(); settings.validate(); db = Database(settings)
    job = db.get(jobs, sys.argv[1])
    if not job: raise ValueError("Unknown operation")
    try:
        from . import compiler
        from store import LocalStore
        # OS lock prevents an orphaned child from overlapping a replacement worker.
        with LocalStore(settings.home(job["owner"])).transaction("hosted-job"):
            result = execute(settings, db, job)
        print(json.dumps({"ok": True, "result": result}))
    except Exception as exc:
        # Never print raw provider errors, URLs, prompts, tokens or filesystem paths.
        from .db import SpendingLimit, UncertainCall, YieldJob
        if isinstance(exc, YieldJob):
            print(json.dumps({"yield": True})); return
        from .retrieval import NeedsContent
        safe = str(exc) if isinstance(exc, (SpendingLimit, UncertainCall, NeedsContent)) else "Processing could not finish. Your sources are saved; contact the pilot operator."
        print(json.dumps({"ok": False, "error": safe, "error_type": type(exc).__name__,
                          "retry": str(exc).startswith("Another hosted-job operation is active")}))
        if settings.dev:
            import traceback
            traceback.print_exc(file=sys.stderr)


if __name__ == "__main__": main()
