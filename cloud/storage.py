"""Server-owned locations; clients never supply filesystem paths or storage keys."""
import hashlib
from pathlib import Path
from uuid import UUID
import httpx


def storage_headers(settings):
    headers = {"apikey": settings.secret_key}
    # New secret keys are not JWTs; legacy service-role JWTs still need Bearer.
    if not settings.secret_key.startswith("sb_secret_"):
        headers["Authorization"] = "Bearer " + settings.secret_key
    return headers


def asset_path(settings, owner, ident, suffix="bin"):
    if suffix not in {"bin", "lectic", "json", "zip"}: raise ValueError("Invalid asset type")
    parent = settings.account_dir(owner) / "assets"
    parent.mkdir(parents=True, exist_ok=True)
    return parent / (str(UUID(ident)) + "." + suffix)


def upload_private(settings, owner, path: Path, category="originals"):
    if settings.dev: return
    if category not in {"originals", "backups"}: raise ValueError("Invalid storage category")
    # Content-addressed keys make retries safe and preserve previous backups.
    checksum = hashlib.sha256(path.read_bytes()).hexdigest()
    key = f"{UUID(owner)}/{category}/{checksum}"
    with path.open("rb") as stream, httpx.Client(timeout=120, trust_env=False) as client:
        response = client.post(settings.supabase_url + "/storage/v1/object/lectic-private/" + key,
            headers={**storage_headers(settings), "Content-Type": "application/octet-stream", "x-upsert": "false"}, content=stream)
    try: duplicate = response.status_code == 400 and response.json().get("error") in {"Duplicate", "Asset Already Exists"}
    except ValueError: duplicate = False
    if response.status_code not in {200, 201, 409} and not duplicate:
        raise RuntimeError("Private storage upload failed; local original retained.")
    return key


def remove_private_backup(settings, owner, key):
    prefix = str(UUID(owner)) + "/backups/"
    if not key.startswith(prefix) or len(key.removeprefix(prefix)) != 64:
        raise ValueError("Invalid private backup key")
    if settings.dev: return
    with httpx.Client(timeout=30, trust_env=False) as client:
        response = client.request("DELETE", settings.supabase_url + "/storage/v1/object/lectic-private",
            headers=storage_headers(settings), json={"prefixes": [key]})
        response.raise_for_status()
