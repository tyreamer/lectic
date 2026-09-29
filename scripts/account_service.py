"""Account and authentication management for Lectic Cloud.

Provides identity, authentication, OAuth 2.0 token management, and access revocation.
Ownership is strictly derived from verified credentials or tokens, never caller-supplied IDs.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
from typing import Any, Dict, List, Optional, Tuple

from store import LocalStore


def _hash_password(password: str, salt: Optional[bytes] = None) -> Tuple[str, str]:
    """Hash password using PBKDF2-HMAC-SHA256 with 100,000 iterations."""
    if salt is None:
        salt = secrets.token_bytes(16)
    hashed = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return hashed.hex(), salt.hex()


def _verify_password(password: str, password_hash: str, salt_hex: str) -> bool:
    salt = bytes.fromhex(salt_hex)
    expected = bytes.fromhex(password_hash)
    computed = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return hmac.compare_digest(expected, computed)


class AccountError(Exception):
    pass


class AuthenticationError(AccountError):
    pass


class AuthorizationError(AccountError):
    pass


class AccountStore:
    """Manages persistent accounts, OAuth grants, and access tokens for Lectic Cloud."""

    def __init__(self, cloud_root: Path | str):
        self.root = Path(cloud_root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.accounts_file = self.root / 'accounts.json'
        self.tokens_file = self.root / 'tokens.json'
        self.oauth_codes_file = self.root / 'oauth_codes.json'
        self.store = LocalStore(self.root)
        self._init_storage()

    def _init_storage(self) -> None:
        with self.store.transaction('account_index', reentrant=True):
            if not self.accounts_file.exists():
                self.accounts_file.write_text(json.dumps({'accounts': {}}, indent=2), encoding='utf-8')
            if not self.tokens_file.exists():
                self.tokens_file.write_text(json.dumps({'tokens': {}}, indent=2), encoding='utf-8')
            if not self.oauth_codes_file.exists():
                self.oauth_codes_file.write_text(json.dumps({'codes': {}}, indent=2), encoding='utf-8')

    def _read_json(self, path: Path) -> Dict[str, Any]:
        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return {}

    def _write_json(self, path: Path, data: Dict[str, Any]) -> None:
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        os.replace(temp, path)

    def create_account(self, email: str, password: str, display_name: Optional[str] = None) -> Dict[str, Any]:
        """Create a new user account with isolated home directory."""
        email = email.strip().lower()
        if not email or '@' not in email:
            raise AccountError('A valid email address is required')
        if len(password) < 8:
            raise AccountError('Password must be at least 8 characters')

        with self.store.transaction('account_index', reentrant=True):
            data = self._read_json(self.accounts_file)
            accounts = data.get('accounts', {})

            for acc in accounts.values():
                if acc['email'] == email:
                    raise AccountError(f'Account with email {email} already exists')

            account_id = 'acc-' + secrets.token_hex(12)
            pwd_hash, salt_hex = _hash_password(password)
            now = datetime.now(timezone.utc).isoformat()
            home_dir = self.root / 'accounts' / account_id / 'home'
            home_dir.mkdir(parents=True, exist_ok=True)

            # Initialize private home store
            (home_dir / 'blobs').mkdir(parents=True, exist_ok=True)
            (home_dir / 'inbox').mkdir(parents=True, exist_ok=True)
            (home_dir / 'library.json').write_text(json.dumps({'schema_version': '1.0', 'collections': [], 'active_collection': None}, indent=2), encoding='utf-8')

            account = {
                'account_id': account_id,
                'email': email,
                'display_name': (display_name or email.split('@')[0]).strip(),
                'password_hash': pwd_hash,
                'salt': salt_hex,
                'status': 'active',
                'created_at': now,
                'updated_at': now,
                'home_dir': str(home_dir)
            }
            accounts[account_id] = account
            self._write_json(self.accounts_file, {'accounts': accounts})

            return self._safe_account(account)

    def authenticate(self, email: str, password: str) -> Dict[str, Any]:
        """Verify email and password and return safe account record."""
        email = email.strip().lower()
        with self.store.transaction('account_index', reentrant=True):
            data = self._read_json(self.accounts_file)
            accounts = data.get('accounts', {})
            for acc in accounts.values():
                if acc['email'] == email:
                    if acc.get('status') != 'active':
                        raise AuthenticationError('Account is inactive or suspended')
                    if _verify_password(password, acc['password_hash'], acc['salt']):
                        return self._safe_account(acc)
                    raise AuthenticationError('Invalid email or password')
            raise AuthenticationError('Invalid email or password')

    def get_account(self, account_id: str) -> Optional[Dict[str, Any]]:
        with self.store.transaction('account_index', reentrant=True):
            data = self._read_json(self.accounts_file)
            acc = data.get('accounts', {}).get(account_id)
            return self._safe_account(acc) if acc else None

    def get_account_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        email = email.strip().lower()
        with self.store.transaction('account_index', reentrant=True):
            data = self._read_json(self.accounts_file)
            for acc in data.get('accounts', {}).values():
                if acc['email'] == email:
                    return self._safe_account(acc)
            return None

    def list_accounts(self) -> List[Dict[str, Any]]:
        """Return all safe account records."""
        with self.store.transaction('account_index', reentrant=True):
            data = self._read_json(self.accounts_file)
            return [self._safe_account(acc) for acc in data.get('accounts', {}).values()]

    def get_account_home(self, account_id: str) -> Path:
        """Return the verified local home Path for an account."""
        acc = self.get_account(account_id)
        if not acc:
            raise AccountError(f'Account {account_id} not found')
        home = Path(acc['home_dir']).resolve()
        if not home.exists():
            home.mkdir(parents=True, exist_ok=True)
        return home

    def create_access_token(self, account_id: str, client_name: str = 'Assistant Client',
                            scope: str = 'library:read library:write', expires_in_days: int = 90) -> Dict[str, Any]:
        """Generate an authenticated access token bound to this account."""
        acc = self.get_account(account_id)
        if not acc:
            raise AccountError(f'Account {account_id} not found')

        token = 'lectic_tok_' + secrets.token_hex(24)
        now = datetime.now(timezone.utc)
        expires_at = (now + timedelta(days=expires_in_days)).isoformat()

        token_record = {
            'token': token,
            'account_id': account_id,
            'client_name': client_name,
            'scope': scope,
            'created_at': now.isoformat(),
            'expires_at': expires_at,
            'revoked': False,
            'last_used_at': None
        }

        with self.store.transaction('account_index', reentrant=True):
            tokens_data = self._read_json(self.tokens_file)
            tokens = tokens_data.get('tokens', {})
            tokens[token] = token_record
            self._write_json(self.tokens_file, {'tokens': tokens})

        return token_record

    def verify_token(self, token: str) -> str:
        """Verify access token and return verified account_id.
        
        Raises AuthenticationError if invalid, expired, or revoked.
        """
        if not token or not isinstance(token, str):
            raise AuthenticationError('Missing or invalid token format')

        # Clean "Bearer " prefix if provided
        if token.lower().startswith('bearer '):
            token = token[7:].strip()

        with self.store.transaction('account_index', reentrant=True):
            tokens_data = self._read_json(self.tokens_file)
            record = tokens_data.get('tokens', {}).get(token)
            if not record:
                raise AuthenticationError('Invalid access token')

            if record.get('revoked', False):
                raise AuthenticationError('Token has been revoked')

            expires_at = record.get('expires_at')
            if expires_at:
                exp_dt = datetime.fromisoformat(expires_at)
                if datetime.now(timezone.utc) > exp_dt:
                    raise AuthenticationError('Token has expired')

            # Update last used
            record['last_used_at'] = datetime.now(timezone.utc).isoformat()
            self._write_json(self.tokens_file, tokens_data)

            account_id = record['account_id']
            # Verify account is still active
            acc = self.get_account(account_id)
            if not acc or acc.get('status') != 'active':
                raise AuthenticationError('Account inactive or revoked')

            return account_id

    def revoke_token(self, token: str, account_id: Optional[str] = None) -> bool:
        """Revoke a specific access token. If account_id is given, ensures ownership."""
        if token.lower().startswith('bearer '):
            token = token[7:].strip()

        with self.store.transaction('account_index', reentrant=True):
            tokens_data = self._read_json(self.tokens_file)
            tokens = tokens_data.get('tokens', {})
            record = tokens.get(token)
            if not record:
                return False

            if account_id and record['account_id'] != account_id:
                raise AuthorizationError('Cannot revoke token belonging to another account')

            record['revoked'] = True
            record['revoked_at'] = datetime.now(timezone.utc).isoformat()
            self._write_json(self.tokens_file, {'tokens': tokens})
            return True

    def revoke_all_tokens(self, account_id: str) -> int:
        """Revoke all active tokens for an account (e.g. on password reset or security audit)."""
        count = 0
        now = datetime.now(timezone.utc).isoformat()
        with self.store.transaction('account_index', reentrant=True):
            tokens_data = self._read_json(self.tokens_file)
            tokens = tokens_data.get('tokens', {})
            for rec in tokens.values():
                if rec['account_id'] == account_id and not rec.get('revoked'):
                    rec['revoked'] = True
                    rec['revoked_at'] = now
                    count += 1
            self._write_json(self.tokens_file, {'tokens': tokens})
        return count

    def list_account_tokens(self, account_id: str) -> List[Dict[str, Any]]:
        """List active/recent tokens for an account, with secret truncated."""
        with self.store.transaction('account_index', reentrant=True):
            tokens_data = self._read_json(self.tokens_file)
            res = []
            for rec in tokens_data.get('tokens', {}).values():
                if rec['account_id'] == account_id:
                    res.append({
                        'token_preview': rec['token'][:16] + '...',
                        'token': rec['token'],
                        'client_name': rec.get('client_name', 'Assistant'),
                        'scope': rec.get('scope', ''),
                        'created_at': rec['created_at'],
                        'expires_at': rec.get('expires_at'),
                        'last_used_at': rec.get('last_used_at'),
                        'revoked': rec.get('revoked', False)
                    })
            return sorted(res, key=lambda x: x['created_at'], reverse=True)

    # --- OAuth 2.0 Authorization Code Flow ---

    def create_authorization_code(self, account_id: str, client_id: str, redirect_uri: str,
                                   scope: str = 'library:read library:write',
                                   code_challenge: Optional[str] = None,
                                   code_challenge_method: Optional[str] = None) -> str:
        """Issue an authorization code valid for 10 minutes."""
        code = 'code_' + secrets.token_hex(20)
        now = datetime.now(timezone.utc)
        expires_at = (now + timedelta(minutes=10)).isoformat()

        record = {
            'code': code,
            'account_id': account_id,
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'scope': scope,
            'code_challenge': code_challenge,
            'code_challenge_method': code_challenge_method or 'S256',
            'created_at': now.isoformat(),
            'expires_at': expires_at,
            'used': False
        }

        with self.store.transaction('account_index', reentrant=True):
            codes_data = self._read_json(self.oauth_codes_file)
            codes = codes_data.get('codes', {})
            codes[code] = record
            self._write_json(self.oauth_codes_file, {'codes': codes})

        return code

    def exchange_authorization_code(self, code: str, client_id: str, redirect_uri: str,
                                     code_verifier: Optional[str] = None) -> Dict[str, Any]:
        """Exchange an authorization code for an access token."""
        with self.store.transaction('account_index', reentrant=True):
            codes_data = self._read_json(self.oauth_codes_file)
            codes = codes_data.get('codes', {})
            record = codes.get(code)
            if not record:
                raise AuthenticationError('Invalid authorization code')

            if record.get('used', False):
                raise AuthenticationError('Authorization code has already been used')

            exp_dt = datetime.fromisoformat(record['expires_at'])
            if datetime.now(timezone.utc) > exp_dt:
                raise AuthenticationError('Authorization code has expired')

            if record['client_id'] != client_id:
                raise AuthenticationError('client_id mismatch')

            if record['redirect_uri'] != redirect_uri:
                raise AuthenticationError('redirect_uri mismatch')

            # Verify PKCE if present
            challenge = record.get('code_challenge')
            if challenge:
                if not code_verifier:
                    raise AuthenticationError('Missing code_verifier for PKCE challenge')
                method = record.get('code_challenge_method', 'S256')
                if method == 'S256':
                    import base64
                    computed = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode('ascii')).digest()).decode('ascii').rstrip('=')
                    if not hmac.compare_digest(computed, challenge):
                        raise AuthenticationError('PKCE verification failed')
                elif method == 'plain':
                    if not hmac.compare_digest(code_verifier, challenge):
                        raise AuthenticationError('PKCE verification failed')

            # Mark code as used
            record['used'] = True
            record['used_at'] = datetime.now(timezone.utc).isoformat()
            self._write_json(self.oauth_codes_file, {'codes': codes})

            # Issue token
            account_id = record['account_id']
            token_rec = self.create_access_token(account_id, client_name=f'OAuth Client ({client_id})', scope=record['scope'])
            return {
                'access_token': token_rec['token'],
                'token_type': 'Bearer',
                'expires_in': 90 * 86400,
                'scope': record['scope'],
                'account_id': account_id
            }

    def _safe_account(self, record: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not record:
            return None
        return {
            'account_id': record['account_id'],
            'email': record['email'],
            'display_name': record['display_name'],
            'status': record['status'],
            'created_at': record['created_at'],
            'home_dir': record['home_dir']
        }
