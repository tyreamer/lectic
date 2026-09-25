"""Ed25519 pack signatures. A signature proves key possession, not a person's identity.

Legacy HMAC packs remain readable but are unverified for recipients.
"""
from __future__ import annotations
import hashlib
import hmac
import json
from pathlib import Path
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from ec import require, write
from home import storage_root
from store import home_transaction

IDENTITY_FILENAME = 'identity.json'


def _key_id(key_hex):
    """Legacy HMAC identifier, for local legacy verification only."""
    return hashlib.sha256(bytes.fromhex(key_hex)).hexdigest()[:16]


def _sign(data, key_hex):
    return hmac.new(bytes.fromhex(key_hex), data, hashlib.sha256).hexdigest()


def _verify(data, sig_hex, key_hex):
    return hmac.compare_digest(_sign(data, key_hex), sig_hex)


def identity_path(project='.'):
    return Path(storage_root(project)) / IDENTITY_FILENAME


def load_identity(project='.'):
    path = identity_path(project)
    if not path.is_file():
        return None
    record = json.loads(path.read_text(encoding='utf-8'))
    require(isinstance(record, dict) and {'name', 'contact', 'key_hex', 'key_id'} <= record.keys(),
            'The local identity is invalid; restore it from your private backup')
    return record


@home_transaction
def save_identity(project, name, contact):
    """Update details without rotating keys; retain a private legacy migration copy."""
    require(name.strip(), 'Publisher name is required')
    previous = load_identity(project)
    private = (Ed25519PrivateKey.from_private_bytes(bytes.fromhex(previous['key_hex']))
               if previous else Ed25519PrivateKey.generate())
    public = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    record = {'name': name.strip(), 'contact': contact.strip(), 'algorithm': 'ed25519',
              'key_hex': private.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                                                serialization.NoEncryption()).hex(),
              'public_key': public.hex(), 'key_id': hashlib.sha256(public).hexdigest()}
    path = identity_path(project)
    if previous and previous.get('algorithm') != 'ed25519':
        backup = path.with_name('identity-legacy.json')
        if not backup.exists():
            write(backup, previous)
            backup.chmod(0o600)
    write(path, record)
    path.chmod(0o600)
    return record


def show_identity(project='.'):
    identity = load_identity(project)
    if not identity:
        return 'No identity set. Run: lectic identity set "Your Name" --contact your@email.com'
    return (f"Name:     {identity['name']}\nContact:  {identity['contact']}\n"
            f"Key ID:   {identity['key_id']}  (compare this fingerprint with recipients; the private key stays here)")


def _signable(manifest):
    payload = dict(manifest)
    payload['publisher'] = {k: v for k, v in manifest.get('publisher', {}).items() if k != 'signature'}
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def sign_manifest(manifest, identity):
    private = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(identity['key_hex']))
    public = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    publisher = {'name': identity['name'], 'contact': identity['contact'], 'algorithm': 'ed25519',
                 'public_key': public.hex(), 'key_id': hashlib.sha256(public).hexdigest()}
    publisher['signature'] = private.sign(_signable({**manifest, 'publisher': publisher})).hex()
    return publisher


def check_manifest_signature(manifest):
    publisher = manifest.get('publisher')
    if not publisher:
        return 'unsigned', 'No publisher signature (set one with lectic identity)'
    if publisher.get('algorithm') is None:
        return 'unverified', 'Legacy HMAC signature: recipients cannot verify it. Publisher details are unverified claims.'
    if publisher.get('algorithm') != 'ed25519':
        return 'invalid', 'Unsupported publisher signature algorithm'
    try:
        public = bytes.fromhex(publisher['public_key'])
        require(hashlib.sha256(public).hexdigest() == publisher['key_id'], 'Public key fingerprint differs')
        Ed25519PublicKey.from_public_bytes(public).verify(bytes.fromhex(publisher['signature']), _signable(manifest))
    except (InvalidSignature, ValueError, KeyError, TypeError):
        return 'invalid', 'Publisher signature is invalid; the manifest or publisher details were altered'
    return 'signed', (f"Valid Ed25519 signature for key {publisher['key_id']}. "
                      f"Claimed publisher: {publisher['name']} <{publisher['contact']}>. "
                      'Identity is not independently trusted; compare this fingerprint through a trusted channel.')


def verify_manifest(manifest, identity):
    publisher = manifest.get('publisher')
    if not publisher:
        return False, 'No publisher block in manifest'
    if publisher.get('algorithm') == 'ed25519':
        local_public = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(identity['key_hex'])).public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        if publisher.get('public_key') != local_public.hex():
            return False, 'Key ID mismatch: this pack uses another signing key'
        status, message = check_manifest_signature(manifest)
        return status == 'signed', message
    stable = {k: v for k, v in manifest.items() if k not in {'pack_id', 'created_at', 'publisher'}}
    raw = json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    ok = publisher.get('key_id') == _key_id(identity['key_hex']) and _verify(raw, publisher.get('signature', ''), identity['key_hex'])
    return ok, 'Legacy HMAC: content checked locally; publisher metadata was never authenticated' if ok else 'Legacy signature invalid'
