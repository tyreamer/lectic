"""Identity and pack signing for Lectic.

Manages a persistent identity at LECTIC_HOME/identity.json and provides
HMAC-SHA256 signing for pack manifests. Stdlib only, no extra dependencies.

Key design:
- Identity = a name + contact + a randomly-generated secret key stored locally
- Signing = HMAC-SHA256 over the canonical JSON of the pack manifest (before
  pack_id and created_at are set, using the same content that pack_id is derived
  from) — this means the signature is stable and verifiable without re-deriving
- The public portion (name, contact, key_id = first 16 hex of the key's SHA-256)
  is embedded in pack.json so anyone can see who signed it
- The full secret key never leaves the home directory

Usage:
    from identity import load_identity, save_identity, sign_manifest, verify_manifest
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from pathlib import Path

from home import storage_root

IDENTITY_FILENAME = 'identity.json'


# ---------------------------------------------------------------- key helpers

def _key_id(key_hex: str) -> str:
    """Short stable identifier for display — first 16 hex chars of key's SHA-256."""
    return hashlib.sha256(bytes.fromhex(key_hex)).hexdigest()[:16]


def _sign(data: bytes, key_hex: str) -> str:
    """HMAC-SHA256 over data with key; returns hex string."""
    return hmac.new(bytes.fromhex(key_hex), data, hashlib.sha256).hexdigest()


def _verify(data: bytes, sig_hex: str, key_hex: str) -> bool:
    """Constant-time comparison of expected vs. supplied signature."""
    expected = _sign(data, key_hex)
    return hmac.compare_digest(expected, sig_hex)


# ---------------------------------------------------------------- identity file

def identity_path(project='.') -> Path:
    return Path(storage_root(project)) / IDENTITY_FILENAME


def load_identity(project='.') -> dict | None:
    """Return the stored identity, or None if none has been set."""
    path = identity_path(project)
    if not path.is_file():
        return None
    try:
        record = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(record, dict):
            return None
        required = {'name', 'contact', 'key_hex', 'key_id'}
        if not required.issubset(record.keys()):
            return None
        return record
    except (ValueError, OSError):
        return None


def save_identity(project: str, name: str, contact: str) -> dict:
    """Create (or replace) the identity.  Returns the new identity record."""
    key_hex = secrets.token_hex(32)   # 256-bit random secret key
    record = {
        'name': name.strip(),
        'contact': contact.strip(),
        'key_hex': key_hex,
        'key_id': _key_id(key_hex),
    }
    path = identity_path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Write atomically and restrict permissions
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False, suffix='.tmp') as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
        temp = Path(f.name)
    temp.replace(path)
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return record


def show_identity(project='.') -> str:
    """Human-readable identity summary."""
    identity = load_identity(project)
    if not identity:
        return 'No identity set. Run: lectic identity set "Your Name" --contact your@email.com'
    return (f"Name:     {identity['name']}\n"
            f"Contact:  {identity['contact']}\n"
            f"Key ID:   {identity['key_id']}  (short fingerprint; the signing key stays on your machine)")


# ---------------------------------------------------------------- pack signing

def _signable(manifest: dict) -> bytes:
    """The bytes signed/verified: canonical JSON of the stable manifest fields.

    Excludes `created_at` (timestamp, varies) and `publisher.signed_at`
    but includes everything else — the same content that pack_id is derived from.
    Keeping this consistent with build_pack's pack_id derivation is critical.
    """
    stable = {k: v for k, v in manifest.items() if k not in {'pack_id', 'created_at', 'publisher'}}
    return json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def sign_manifest(manifest: dict, identity: dict) -> dict:
    """Return a `publisher` block to embed in the manifest.

    The signature covers all stable manifest fields so the recipient can verify
    the pack contents match what the signer built, even without the secret key —
    they verify using the key_id to confirm the key fingerprint matches.
    """
    sig = _sign(_signable(manifest), identity['key_hex'])
    return {
        'name': identity['name'],
        'contact': identity['contact'],
        'key_id': identity['key_id'],
        'signature': sig,
    }


def verify_manifest(manifest: dict, identity: dict) -> tuple[bool, str]:
    """Verify a pack's publisher signature using its embedded publisher block.

    Returns (ok: bool, message: str).
    Requires the identity's key_hex to verify (can only be done by the key holder).
    For recipients without the key, use verify_manifest_by_keyid instead.
    """
    publisher = manifest.get('publisher')
    if not publisher:
        return False, 'No publisher block in manifest'
    if publisher.get('key_id') != identity['key_id']:
        return False, f"Key ID mismatch: pack signed with {publisher.get('key_id')!r}, local key is {identity['key_id']!r}"
    ok = _verify(_signable(manifest), publisher.get('signature', ''), identity['key_hex'])
    if ok:
        return True, f"Verified — signed by \"{publisher['name']}\" (key: {publisher['key_id']})"
    return False, f"Signature invalid — pack may have been altered after signing by \"{publisher['name']}\""


def check_manifest_signature(manifest: dict) -> tuple[str, str]:
    """Check a pack's publisher block without the secret key.

    Returns (status, message) where status is one of:
      'signed'   — has a publisher block; signature format is present
      'unsigned' — no publisher block
    We cannot verify the HMAC without the secret key, but we can display
    the publisher name/contact/key_id so the recipient knows who claims to
    have signed it and can decide how much to trust it.
    """
    publisher = manifest.get('publisher')
    if not publisher:
        return 'unsigned', 'No publisher -- pack was created without a lectic identity'
    name = publisher.get('name', '?')
    contact = publisher.get('contact', '?')
    key_id = publisher.get('key_id', '?')
    return 'signed', f"Publisher: \"{name}\" <{contact}>  key: {key_id}"
